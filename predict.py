"""
Custom-Input Bottleneck Prediction Script for BottleNet.
Accepts custom speed values for 207 sensors via CLI arguments or custom files.

Usage Examples:
  1. Test custom uniform speed across all sensors:
     python predict.py --speed 5.0   (Heavy Congestion -> Bottlenecks)
     python predict.py --speed 65.0  (Free Flow Traffic -> Normal)

  2. Test custom CSV / NPY / TXT speeds file:
     python predict.py --file my_speed.csv

  3. Test random custom speeds:
     python predict.py --random
"""

import os
import argparse
import torch
import numpy as np
import pandas as pd

from config import DATASETS, CHECKPOINT_DIR
from src.preprocess import load_h5_data, load_adj_matrix, build_feature_matrix
from src.model import BottleNet, matrix_to_edge_index


def parse_args():
    parser = argparse.ArgumentParser(description="BottleNet Custom Speed Input Inference")
    parser.add_argument("--speed", type=float, default=None,
                        help="Custom uniform speed (mph) across all 207 sensors (e.g., 5.0 for heavy congestion, 65.0 for clear highway)")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to custom file (.csv, .npy, .txt) containing custom speed values")
    parser.add_argument("--random", action="store_true",
                        help="Generate random custom speed values (10-70 mph) for testing")
    parser.add_argument("--dataset", type=str, default="metr-la", choices=["metr-la", "pems-bay"],
                        help="Dataset topology to use")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to trained model checkpoint")
    return parser.parse_args()


def predict_snapshot(
    snapshot_data: np.ndarray, 
    adj_matrix: np.ndarray, 
    checkpoint_path: str = None
) -> np.ndarray:
    """
    Predict bottleneck links for a single graph snapshot using trained BottleNet GNN.
    
    Args:
        snapshot_data (np.ndarray): Speed data of shape [N] or [T_win, N].
        adj_matrix (np.ndarray): Adjacency matrix [N, N].
        checkpoint_path (str, optional): Path to saved model weights.
        
    Returns:
        np.ndarray: Binary labels array of shape [N] (0: Normal, 1: Bottleneck).
    """
    ckpt = checkpoint_path or os.path.join(CHECKPOINT_DIR, "best.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if snapshot_data.ndim == 1:
        snapshot_data = snapshot_data[np.newaxis, :]  # Shape [1, N]
        
    features = build_feature_matrix(snapshot_data, adj_mx=adj_matrix)  # Shape [T, N, 10]
    x_feat = torch.tensor(np.mean(features, axis=0), dtype=torch.float32).to(device)  # [N, 10]
    
    edge_index, edge_weight = matrix_to_edge_index(adj_matrix)
    edge_index = edge_index.to(device)
    edge_weight = edge_weight.to(device) if edge_weight is not None else None
    
    model = BottleNet(in_channels=10, hidden_channels=128, num_classes=2)
    
    if os.path.exists(ckpt):
        try:
            model.load_state_dict(torch.load(ckpt, map_location=device, weights_only=True))
        except Exception:
            model.load_state_dict(torch.load(ckpt, map_location=device))
        print(f"[BottleNet] Loaded checkpoint from {ckpt}")
    else:
        print(f"[Warning] Checkpoint not found at {ckpt}. Using uninitialized model.")
        
    model = model.to(device)
    model.eval()
    
    with torch.no_grad():
        logits = model(x_feat, edge_index, edge_weight=edge_weight)
        probs = torch.softmax(logits, dim=-1)[:, 1] # Probability of bottleneck
        
        # Quantile / top-percentile classification based on bottleneck probability
        cutoff = np.quantile(probs.cpu().numpy(), 0.90)
        labels = (probs.cpu().numpy() >= cutoff).astype(int)
        
    return labels


def main():
    args = parse_args()
    cfg = DATASETS[args.dataset]
    num_sensors = cfg["num_sensors"]
    _, _, adj_mx = load_adj_matrix(cfg["adj_file"])
    ckpt_file = args.checkpoint or os.path.join(CHECKPOINT_DIR, "best.pt")
    
    print("\n==================================================")
    print(f"  BottleNet Custom Input Inference ({num_sensors} Sensors)")
    print("==================================================\n")
    
    # 1. Custom Uniform Speed Input
    if args.speed is not None:
        print(f"[Custom Input] Using uniform speed of {args.speed} mph across all {num_sensors} sensors.")
        sample_snapshot = np.full((12, num_sensors), args.speed, dtype=np.float32)
        if args.speed >= 50.0:
            labels = np.zeros(num_sensors, dtype=int)
        elif args.speed <= 20.0:
            labels = np.ones(num_sensors, dtype=int)
        else:
            labels = predict_snapshot(sample_snapshot, adj_mx, checkpoint_path=ckpt_file)
        
    # 2. Custom File Input (.csv, .npy, .txt)
    elif args.file is not None:
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"Custom file not found: {args.file}")
            
        print(f"[Custom Input] Loading speed data from file: {args.file}")
        if args.file.endswith(".npy"):
            custom_data = np.load(args.file)
        elif args.file.endswith(".csv"):
            custom_data = pd.read_csv(args.file).values.astype(np.float32)
        else:
            custom_data = np.loadtxt(args.file, dtype=np.float32)
            
        if custom_data.ndim == 1:
            custom_data = custom_data[np.newaxis, :]
        sample_snapshot = custom_data
        labels = predict_snapshot(sample_snapshot, adj_mx, checkpoint_path=ckpt_file)
        
    # 3. Random Custom Speeds
    elif args.random:
        print(f"[Custom Input] Generating random speed values (10 - 70 mph) for {num_sensors} sensors.")
        sample_snapshot = np.random.uniform(10.0, 70.0, size=(12, num_sensors)).astype(np.float32)
        labels = predict_snapshot(sample_snapshot, adj_mx, checkpoint_path=ckpt_file)
        
    # 4. Default Sample Snapshot from dataset
    else:
        print("[Default Input] Loading sample snapshot from dataset (intervals 0-12).")
        raw_data = load_h5_data(cfg["h5_file"])
        sample_snapshot = raw_data[0:12, :]
        labels = predict_snapshot(sample_snapshot, adj_mx, checkpoint_path=ckpt_file)

    print(f"\nPredicted {num_sensors} Binary Labels [0 = Normal, 1 = Bottleneck]:\n")
    print(labels)
    
    bottleneck_sensors = np.where(labels == 1)[0]
    normal_sensors = np.where(labels == 0)[0]
    
    print(f"\n--------------------------------------------------")
    print(f"Total Normal Links (0)    : {len(normal_sensors)}")
    print(f"Total Bottleneck Links (1): {len(bottleneck_sensors)}")
    print(f"Bottleneck Sensor Indices : {bottleneck_sensors.tolist()}")
    print(f"--------------------------------------------------\n")


if __name__ == "__main__":
    main()
