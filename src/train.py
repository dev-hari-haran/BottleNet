"""
Enhanced PyTorch Geometric Training & Evaluation Module for BottleNet GNN.
Handles mini-batched graph snapshots, class-weighted cross-entropy loss,
validation-loss based checkpointing, ReduceLROnPlateau scheduling, test-set ROC-AUC evaluation,
and complete 300 DPI publication visual graphs + interactive Folium map generation.
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Dict, List, Tuple, Any
from tqdm import tqdm
from sklearn.metrics import roc_curve, precision_recall_curve, auc

from config import LEARNING_RATE, WEIGHT_DECAY, TRAIN_EPOCHS, CHECKPOINT_DIR
from src.evaluate import (
    plot_training_loss, plot_roc_curve, plot_precision_recall,
    plot_confusion_matrix_heatmap, plot_rank_stability, plot_coverage_evolution,
    plot_component_size, plot_score_distribution, generate_bottleneck_map
)
from src.report import generate_pdf_report
from src.graph import extract_bottleneck_components


def compute_accuracy_metrics(logits: torch.Tensor, y_true: torch.Tensor) -> Tuple[float, float]:
    """
    Compute node-level classification accuracy (%) and F1 score.
    
    Args:
        logits (torch.Tensor): Output class logits of shape [N, 2].
        y_true (torch.Tensor): Ground-truth binary labels of shape [N].
        
    Returns:
        Tuple[float, float]: (Accuracy %, F1 Score [0-1])
    """
    preds = torch.argmax(logits, dim=-1)
    correct = (preds == y_true).sum().item()
    total = y_true.size(0)
    acc = (correct / max(1, total)) * 100.0
    
    tp = ((preds == 1) & (y_true == 1)).sum().item()
    fp = ((preds == 1) & (y_true == 0)).sum().item()
    fn = ((preds == 0) & (y_true == 1)).sum().item()
    
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall / max(1e-5, precision + recall)) if (precision + recall) > 0 else 0.0
    
    return float(acc), float(f1)


def train_epoch(
    model: nn.Module, 
    loader: Any,
    optimizer: optim.Optimizer, 
    criterion: nn.Module,
    device: torch.device
) -> Tuple[float, float, float]:
    """
    Run a single training epoch over a PyTorch Geometric DataLoader.
    
    Returns:
        Tuple[float, float, float]: (Average Epoch Loss, Train Acc %, Train F1 Score)
    """
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_nodes = 0
    all_preds = []
    all_targets = []
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        # Forward pass
        logits = model(batch.x, batch.edge_index, edge_weight=batch.edge_weight)
        
        # Assert logit and label tensor shape alignment
        assert logits.dim() == 2 and logits.size(1) == 2, f"Expected logits shape [N, 2], got {logits.shape}"
        assert batch.y.dim() == 1, f"Expected 1D target tensor, got {batch.y.shape}"
        assert logits.size(0) == batch.y.size(0), f"Size mismatch: logits {logits.size(0)} vs targets {batch.y.size(0)}"
        
        loss = criterion(logits, batch.y)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item() * batch.num_graphs
        preds = torch.argmax(logits, dim=-1)
        
        total_correct += (preds == batch.y).sum().item()
        total_nodes += batch.y.size(0)
        
        all_preds.extend(preds.cpu().numpy())
        all_targets.extend(batch.y.cpu().numpy())
        
    avg_loss = total_loss / max(1, len(loader.dataset))
    acc = (total_correct / max(1, total_nodes)) * 100.0
    
    preds_arr = np.array(all_preds)
    targets_arr = np.array(all_targets)
    tp = np.sum((preds_arr == 1) & (targets_arr == 1))
    fp = np.sum((preds_arr == 1) & (targets_arr == 0))
    fn = np.sum((preds_arr == 0) & (targets_arr == 1))
    
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall / max(1e-5, precision + recall)) if (precision + recall) > 0 else 0.0
    
    return avg_loss, acc, float(f1)


def evaluate_epoch(
    model: nn.Module, 
    loader: Any,
    criterion: nn.Module,
    device: torch.device
) -> Tuple[float, float, float, np.ndarray, np.ndarray]:
    """
    Run evaluation epoch over a PyTorch Geometric DataLoader without gradient updates.
    
    Returns:
        Tuple[float, float, float, np.ndarray, np.ndarray]: 
        (Avg Loss, Accuracy %, F1 Score, Y_True array, Y_Probabilities array)
    """
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_nodes = 0
    
    all_y_true = []
    all_y_probs = []
    
    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            logits = model(batch.x, batch.edge_index, edge_weight=batch.edge_weight)
            
            loss = criterion(logits, batch.y)
            total_loss += loss.item() * batch.num_graphs
            
            probs = torch.softmax(logits, dim=-1)[:, 1]  # Bottleneck probability
            preds = torch.argmax(logits, dim=-1)
            
            total_correct += (preds == batch.y).sum().item()
            total_nodes += batch.y.size(0)
            
            all_y_true.extend(batch.y.cpu().numpy())
            all_y_probs.extend(probs.cpu().numpy())
            
    avg_loss = total_loss / max(1, len(loader.dataset))
    acc = (total_correct / max(1, total_nodes)) * 100.0
    
    y_true = np.array(all_y_true)
    y_probs = np.array(all_y_probs)
    y_pred = (y_probs > 0.5).astype(int)
    
    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))
    
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall / max(1e-5, precision + recall)) if (precision + recall) > 0 else 0.0
    
    return avg_loss, acc, float(f1), y_true, y_probs


def train_bottlenet(
    model: nn.Module,
    train_loader: Any,
    val_loader: Any,
    test_loader: Any,
    epochs: int = TRAIN_EPOCHS,
    lr: float = LEARNING_RATE,
    weight_decay: float = WEIGHT_DECAY,
    device_str: str = "auto",
    checkpoint_dir: str = CHECKPOINT_DIR,
    dataset_name: str = "metr-la",
    adj_matrix: np.ndarray = None,
    scores_sequence: list = None
) -> Dict[str, Any]:
    """
    Execute full BottleNet mini-batched GNN training, validation loss checkpointing,
    and test-set ROC-AUC evaluation with complete publication graph generation.
    """
    if device_str == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str)
        
    print(f"[BottleNet] Training initialized on compute device: {device}")
    model = model.to(device)
    
    # Calculate Class Imbalance Weights over training dataset
    all_train_y = []
    for batch in train_loader:
        all_train_y.extend(batch.y.numpy())
    all_train_y = np.array(all_train_y)
    
    num_bottlenecks = np.sum(all_train_y == 1)
    num_normals = np.sum(all_train_y == 0)
    pos_weight = float(num_normals) / max(1.0, float(num_bottlenecks))
    print(f"[BottleNet] Dataset Class Distribution: Normal={num_normals}, Bottleneck={num_bottlenecks} (Loss Weight = {pos_weight:.2f})")
    
    weights = torch.tensor([1.0, pos_weight], dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    
    # AdamW Optimizer + ReduceLROnPlateau Scheduler on Validation Loss
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=5, factor=0.5)
    
    os.makedirs(checkpoint_dir, exist_ok=True)
    best_ckpt = os.path.join(checkpoint_dir, "best.pt")
    
    history = {
        "train_loss": [], "val_loss": [], "val_acc": [], "val_f1": [], 
        "best_epoch": 0, "best_val_loss": float("inf")
    }
    best_val_loss = float("inf")
    
    pbar = tqdm(range(1, epochs + 1), desc="[BottleNet] Training GNN Epochs")
    for epoch in pbar:
        train_loss, train_acc, train_f1 = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, val_f1, _, _ = evaluate_epoch(model, val_loader, criterion, device)
        
        # Step LR scheduler on validation loss
        scheduler.step(val_loss)
        
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)
        
        # Save best checkpoint by Validation Loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            history["best_val_loss"] = val_loss
            history["best_epoch"] = epoch
            torch.save(model.state_dict(), best_ckpt)
            
        pbar.set_postfix({
            "Tr Loss": f"{train_loss:.4f}",
            "Val Loss": f"{val_loss:.4f}",
            "Val F1": f"{val_f1:.3f}",
            "Best VLoss": f"{best_val_loss:.4f}"
        })
        
    print(f"\n[BottleNet] Training loop completed. Best Validation Loss: {best_val_loss:.4f} at Epoch {history['best_epoch']}")
    
    # Post-Training Evaluation on Unseen TEST Set
    print("\n[BottleNet] Executing Evaluation on Chronological TEST Set...")
    if os.path.exists(best_ckpt):
        model.load_state_dict(torch.load(best_ckpt, map_location=device))
        print(f"[BottleNet] Loaded best model checkpoint from {best_ckpt}")
        
    test_loss, test_acc, test_f1, y_test_true, y_test_probs = evaluate_epoch(model, test_loader, criterion, device)
    
    # Calculate TEST ROC-AUC & PR-AUC
    fpr, tpr, _ = roc_curve(y_test_true, y_test_probs)
    test_auc = float(auc(fpr, tpr))
    
    precision, recall, _ = precision_recall_curve(y_test_true, y_test_probs)
    test_pr_auc = float(auc(recall, precision))
    
    print("==================================================")
    print(f"  TEST SET EVALUATION RESULTS ({dataset_name.upper()})")
    print("==================================================")
    print(f"  Test Loss     : {test_loss:.4f}")
    print(f"  Test Accuracy : {test_acc:.2f}%")
    print(f"  Test F1 Score : {test_f1:.4f}")
    print(f"  Test ROC-AUC  : {test_auc:.4f}")
    print(f"  Test PR-AUC   : {test_pr_auc:.4f}")
    print("==================================================\n")
    
    # Save All 300 DPI Publication-Ready Plots
    plot_training_loss(history["train_loss"], history["val_loss"])
    plot_roc_curve(y_test_true, y_test_probs)
    plot_precision_recall(y_test_true, y_test_probs)
    plot_confusion_matrix_heatmap(y_test_true, (y_test_probs > 0.5).astype(int))
    plot_score_distribution(y_test_probs)
    
    # 5. Additional Spatial & Temporal Graphs
    spearman_rho = 1.0
    if scores_sequence is not None and len(scores_sequence) > 1:
        spearman_rho = plot_rank_stability(scores_sequence)
        
        # Calculate coverage evolution (coverage in km = count of bottleneck sensors * 0.5 km)
        coverage_seq = [np.sum(s >= np.quantile(s, 0.90)) * 0.5 for s in scores_sequence]
        plot_coverage_evolution(coverage_seq)
        
        # Connected components extraction if adj_matrix provided
        if adj_matrix is not None:
            component_sizes = []
            for s in scores_sequence[::10]:  # Sample every 10th window for speed
                b_mask = (s >= np.quantile(s, 0.90)).astype(int)
                comps = extract_bottleneck_components(adj_matrix, b_mask)
                for c in comps:
                    component_sizes.append(c["size"])
            plot_component_size(component_sizes)
            
    # Generate Interactive HTML Map
    generate_bottleneck_map(dataset_name, y_test_probs)
    
    # Generate Comprehensive PDF Report
    generate_pdf_report(dataset_name, {
        "best_epoch": history["best_epoch"],
        "roc_auc": test_auc,
        "pr_auc": test_pr_auc,
        "spearman": spearman_rho,
        "best_val_loss": best_val_loss
    })
    
    return history
