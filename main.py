"""
BottleNet Central Orchestrator & CLI Entrypoint.
Processes rolling window graph snapshots across all timesteps, enforces strict
chronological train/val/test splits, and executes GNN pipeline tasks.
"""

import sys
import os
import argparse
import numpy as np
import torch
from tqdm import tqdm
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from config import DATASETS, TRAIN_EPOCHS, TOP_N_FRACTION, CHECKPOINT_DIR, BATCH_SIZE, LEARNING_RATE
from src.preprocess import load_h5_data, load_adj_matrix, build_feature_matrix
from src.voting import compute_scores
from src.graph import get_top_n_bottlenecks, extract_bottleneck_components
from src.model import BottleNet, matrix_to_edge_index
from src.train import train_bottlenet, evaluate_epoch
from src.evaluate import (
    plot_roc_curve, plot_precision_recall, plot_confusion_matrix_heatmap, 
    plot_velocity_distribution, plot_rank_stability, plot_coverage_evolution,
    plot_component_size, plot_score_distribution, generate_bottleneck_map
)
from src.report import generate_pdf_report


def parse_args():
    parser = argparse.ArgumentParser(description="BottleNet Road Network Bottleneck Pipeline")
    parser.add_argument("--mode", type=str, required=True, choices=["vote", "train", "evaluate", "full"],
                        help="Execution mode: 'vote' (Phase 1), 'train' (Phase 2 GNN), 'evaluate', or 'full'")
    parser.add_argument("--dataset", type=str, default="metr-la", choices=["metr-la", "pems-bay"],
                        help="Dataset name to process")
    parser.add_argument("--epochs", type=int, default=TRAIN_EPOCHS, help="Number of GNN training epochs")
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE, help="Mini-batch size (number of graph windows)")
    parser.add_argument("--lr", type=float, default=LEARNING_RATE, help="Learning rate for AdamW")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to checkpoint file")
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cuda", "cpu"], help="Compute device")
    parser.add_argument("--top_n", type=float, default=TOP_N_FRACTION, help="Top-N bottleneck threshold fraction")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"\n==================================================")
    print(f"  BottleNet Orchestrator | Mode: {args.mode.upper()} | Dataset: {args.dataset.upper()}")
    print(f"==================================================\n")
    
    cfg = DATASETS.get(args.dataset)
    if cfg is None:
        raise ValueError(f"Unknown dataset configuration: {args.dataset}")
        
    # 1. Load Data (Raise FileNotFoundError if missing)
    raw_data = load_h5_data(cfg["h5_file"])
    sensor_ids, sensor_map, adj_mx = load_adj_matrix(cfg["adj_file"])
    
    T_total, num_sensors = raw_data.shape
    print(f"[BottleNet] Raw Dataset Loaded. Shape: {raw_data.shape} (Timesteps: {T_total}, Sensors: {num_sensors})")
    assert num_sensors == cfg["num_sensors"], f"Expected {cfg['num_sensors']} sensors, got {num_sensors}"
    
    # Plot overall speed distribution
    plot_velocity_distribution(raw_data[0:1000, :])
    
    # Compute static graph topology edge index and weights
    edge_index, edge_weight = matrix_to_edge_index(adj_mx)
    assert edge_index.dim() == 2 and edge_index.size(0) == 2, f"Invalid edge_index shape: {edge_index.shape}"
    
    # Mode 1: Pure Phase 1 Voting Baseline on Snapshot
    if args.mode == "vote":
        print("[BottleNet] Executing Phase 1: Iterative Weighted Voting Baseline on 1-Hour Snapshot...")
        snapshot_window = raw_data[0:12, :]
        scores = compute_scores(snapshot_window)
        bottleneck_mask = get_top_n_bottlenecks(scores, top_n_fraction=args.top_n)
        components = extract_bottleneck_components(adj_mx, bottleneck_mask)
        print(f"[BottleNet] Phase 1 Voting Complete. Detected {len(components)} connected bottleneck components.")
        plot_score_distribution(scores)
        generate_bottleneck_map(args.dataset, scores)
        print("[BottleNet] Exiting vote mode cleanly.")
        return

    # 2. Generate Rolling Window Graph Snapshots Across ALL Timesteps
    window_size = 12   # 12 intervals = 1 hour window
    rolling_step = 2   # 2 intervals = 10 minute rolling step
    
    window_indices = list(range(0, T_total - window_size + 1, rolling_step))
    print(f"[BottleNet] Generating {len(window_indices)} rolling window graph snapshots (Window Size T={window_size}, Step={rolling_step})...")
    
    dataset_snapshots = []
    scores_sequence = []
    for start_idx in tqdm(window_indices, desc="[BottleNet] Window Feature & Label Generation"):
        w_data = raw_data[start_idx : start_idx + window_size, :]  # Shape [12, N]
        
        # Build 10 engineered spatial-temporal features
        feat_matrix = build_feature_matrix(w_data, adj_mx=adj_mx)  # Shape [12, N, 10]
        x_node = torch.tensor(np.mean(feat_matrix, axis=0), dtype=torch.float32)  # Shape [N, 10]
        
        # Compute independent voting labels per window
        scores_win = compute_scores(w_data)  # Shape [N]
        scores_sequence.append(scores_win)
        y_node = torch.tensor(get_top_n_bottlenecks(scores_win, top_n_fraction=args.top_n), dtype=torch.long)  # Shape [N]
        
        # Wrap into PyTorch Geometric Data object
        graph_data = Data(x=x_node, y=y_node, edge_index=edge_index, edge_weight=edge_weight)
        dataset_snapshots.append(graph_data)
        
    # Tensor shape assertions
    num_windows = len(dataset_snapshots)
    assert num_windows > 0, "Window dataset generation yielded 0 snapshots!"
    assert dataset_snapshots[0].x.shape == (num_sensors, 10), f"Incorrect node feature shape: {dataset_snapshots[0].x.shape}"
    assert dataset_snapshots[0].y.shape == (num_sensors,), f"Incorrect label tensor shape: {dataset_snapshots[0].y.shape}"
    print(f"[BottleNet] Window Generation Complete. Total PyG Graph Snapshots: {num_windows}")

    # 3. Enforce Strict Chronological Train / Val / Test Split (70% / 10% / 20%)
    n_train = int(num_windows * 0.70)
    n_val = int(num_windows * 0.10)
    n_test = num_windows - n_train - n_val
    
    train_snapshots = dataset_snapshots[:n_train]
    val_snapshots = dataset_snapshots[n_train : n_train + n_val]
    test_snapshots = dataset_snapshots[n_train + n_val :]
    
    print(f"[BottleNet] Chronological Data Split:")
    print(f"  Train Set : {len(train_snapshots)} windows (70%)")
    print(f"  Val Set   : {len(val_snapshots)} windows (10%)")
    print(f"  Test Set  : {len(test_snapshots)} windows (20%)")

    # Create PyTorch Geometric DataLoaders
    train_loader = DataLoader(train_snapshots, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_snapshots, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_snapshots, batch_size=args.batch_size, shuffle=False)

    # 4. Instantiate BottleNet GNN Model
    model = BottleNet(in_channels=10, hidden_channels=128, num_classes=2)

    # 5. Mode Execution
    if args.mode in ["train", "full"]:
        print(f"\n[BottleNet] Executing Phase 2: High-Accuracy BottleNet GNN Training on {args.dataset.upper()}...")
        train_bottlenet(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            epochs=args.epochs,
            lr=args.lr,
            device_str=args.device,
            checkpoint_dir=CHECKPOINT_DIR,
            dataset_name=args.dataset,
            adj_matrix=adj_mx,
            scores_sequence=scores_sequence
        )

    elif args.mode == "evaluate":
        print(f"\n[BottleNet] Executing Standalone Evaluation Mode on TEST Set ({args.dataset.upper()})...")
        if args.device == "auto":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device(args.device)
            
        model = model.to(device)
        ckpt_path = args.checkpoint or os.path.join(CHECKPOINT_DIR, "best.pt")
        
        if os.path.exists(ckpt_path):
            model.load_state_dict(torch.load(ckpt_path, map_location=device))
            print(f"[BottleNet] Loaded checkpoint from {ckpt_path}")
        else:
            print(f"[Warning] Checkpoint not found at {ckpt_path}. Evaluating uninitialized model.")
            
        criterion = torch.nn.CrossEntropyLoss()
        test_loss, test_acc, test_f1, y_true, y_probs = evaluate_epoch(model, test_loader, criterion, device)
        
        plot_roc_curve(y_true, y_probs)
        plot_precision_recall(y_true, y_probs)
        plot_confusion_matrix_heatmap(y_true, (y_probs > 0.5).astype(int))
        plot_rank_stability(scores_sequence)
        coverage_seq = [np.sum(s >= np.quantile(s, 0.90)) * 0.5 for s in scores_sequence]
        plot_coverage_evolution(coverage_seq)
        plot_score_distribution(y_probs)
        generate_bottleneck_map(args.dataset, y_probs)
        generate_pdf_report(args.dataset, {"best_epoch": 1, "best_val_loss": test_loss})

    print("\n[BottleNet] Execution completed successfully.\n")


if __name__ == "__main__":
    main()
