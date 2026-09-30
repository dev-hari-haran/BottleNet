"""
Evaluation & High-Quality Plot Generator for BottleNet.
Generates 300 DPI publication-ready graphs and interactive Folium HTML spatial maps.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr
from sklearn.metrics import roc_curve, precision_recall_curve, auc, confusion_matrix

try:
    import folium
except ImportError:
    folium = None

from config import OUTPUT_GRAPH_DIR, BASE_DIR

# Global Graph Aesthetics Setup
plt.rcParams.update({
    "figure.dpi": 300,
    "figure.figsize": (10, 6),
    "font.family": "sans-serif",
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "grid.alpha": 0.4,
})
sns.set_style("whitegrid")


def plot_training_loss(train_losses: list, val_losses: list, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Training and Validation Loss Curves."""
    plt.figure()
    epochs = range(1, len(train_losses) + 1)
    plt.plot(epochs, train_losses, label="Train Loss", color="#1f77b4", linewidth=2)
    plt.plot(epochs, val_losses, label="Validation Loss", color="#ff7f0e", linestyle="--", linewidth=2)
    
    best_epoch = int(np.argmin(val_losses)) + 1
    plt.axvline(best_epoch, color="red", linestyle=":", label=f"Best Epoch ({best_epoch})")
    
    plt.title("BottleNet Training & Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("CrossEntropy Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "train_loss.png"))
    plt.close()


def plot_roc_curve(y_true: np.ndarray, y_probs: np.ndarray, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot ROC Curve with annotated AUC."""
    fpr, tpr, _ = roc_curve(y_true, y_probs)
    roc_auc = auc(fpr, tpr)
    
    plt.figure()
    plt.plot(fpr, tpr, color="#2ca02c", lw=2, label=f"BottleNet GNN (AUC = {roc_auc:.3f})")
    plt.plot([0, 1], [0, 1], color="grey", lw=1.5, linestyle="--", label="Chance")
    plt.title("ROC Curve — Bottleneck Classification")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "roc_curve.png"))
    plt.close()


def plot_precision_recall(y_true: np.ndarray, y_probs: np.ndarray, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Precision-Recall Curve."""
    precision, recall, _ = precision_recall_curve(y_true, y_probs)
    pr_auc = auc(recall, precision)
    
    plt.figure()
    plt.plot(recall, precision, color="#d62728", lw=2, label=f"PR Curve (AP = {pr_auc:.3f})")
    plt.title("Precision-Recall Curve")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "pr_curve.png"))
    plt.close()


def plot_confusion_matrix_heatmap(y_true: np.ndarray, y_pred: np.ndarray, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Seaborn Confusion Matrix Heatmap."""
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["Normal", "Bottleneck"], yticklabels=["Normal", "Bottleneck"])
    plt.title("Bottleneck Classification Confusion Matrix")
    plt.xlabel("Predicted Class")
    plt.ylabel("True Class")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "confusion_matrix.png"))
    plt.close()


def plot_velocity_distribution(raw_speeds: np.ndarray, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Speed Distribution Histogram."""
    plt.figure()
    sns.histplot(raw_speeds.flatten(), kde=True, color="#9467bd", bins=50)
    plt.title("Traffic Velocity Distribution (mph)")
    plt.xlabel("Speed (mph)")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "velocity_distribution.png"))
    plt.close()


def plot_rank_stability(scores_sequence: list, save_dir: str = OUTPUT_GRAPH_DIR) -> float:
    """
    Plot Spearman rank correlation stability curve across consecutive time windows.
    
    Returns:
        float: Mean Spearman rank correlation coefficient.
    """
    if len(scores_sequence) < 2:
        return 1.0
        
    rhos = []
    for t in range(len(scores_sequence) - 1):
        s1 = scores_sequence[t]
        s2 = scores_sequence[t + 1]
        rho, _ = spearmanr(s1, s2)
        if not np.isnan(rho):
            rhos.append(rho)
            
    mean_rho = float(np.mean(rhos)) if len(rhos) > 0 else 1.0
    
    plt.figure()
    plt.plot(range(1, len(rhos) + 1), rhos, color="#17becf", lw=1.5, label=f"Mean Spearman ρ = {mean_rho:.3f}")
    plt.axhline(mean_rho, color="red", linestyle="--", alpha=0.7)
    plt.title("Bottleneck Rank Stability Across Consecutive Windows")
    plt.xlabel("Rolling Window Transition Index")
    plt.ylabel("Spearman Rank Correlation (ρ)")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "rank_stability.png"))
    plt.close()
    
    return mean_rho


def plot_coverage_evolution(coverage_sequence: list, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Spatial Bottleneck Coverage Length (km) Evolution Over Time."""
    plt.figure()
    time_steps = range(1, len(coverage_sequence) + 1)
    plt.plot(time_steps, coverage_sequence, color="#e377c2", lw=2)
    plt.title("Spatial Bottleneck Coverage Length Evolution")
    plt.xlabel("Rolling Window Index")
    plt.ylabel("Coverage Length (km)")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "coverage_evolution.png"))
    plt.close()


def plot_component_size(component_sizes: list, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Connected Bottleneck Component Size Distribution."""
    plt.figure()
    if len(component_sizes) == 0:
        component_sizes = [1]
    sns.histplot(component_sizes, discrete=True, color="#8c564b", alpha=0.8)
    plt.title("Connected Bottleneck Component Size Distribution")
    plt.xlabel("Component Size (Number of Sensor Nodes)")
    plt.ylabel("Component Frequency")
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "component_size.png"))
    plt.close()


def plot_score_distribution(scores: np.ndarray, save_dir: str = OUTPUT_GRAPH_DIR):
    """Plot Distribution of Congestion Scores / Probabilities."""
    plt.figure()
    sns.histplot(scores, kde=True, color="#bcbd22", bins=40)
    cutoff = float(np.quantile(scores, 0.90))
    plt.axvline(cutoff, color="red", linestyle="--", label=f"Top 10% Cutoff ({cutoff:.3f})")
    plt.title("Link Congestion Score Distribution")
    plt.xlabel("Congestion Score / Bottleneck Probability")
    plt.ylabel("Frequency")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "score_distribution.png"))
    plt.close()


def generate_bottleneck_map(
    dataset_name: str,
    scores: np.ndarray,
    save_dir: str = OUTPUT_GRAPH_DIR
) -> str:
    """
    Generate Folium interactive HTML map for specified dataset sensor coordinates.
    """
    data_dir = os.path.join(BASE_DIR, "Data")
    if dataset_name == "metr-la":
        loc_file = os.path.join(data_dir, "graph_sensor_locations.csv")
    else:
        loc_file = os.path.join(data_dir, "graph_sensor_locations_bay.csv")
        
    if not os.path.exists(loc_file):
        print(f"[Warning] Sensor location file missing at {loc_file}. Skipping interactive map.")
        return ""
        
    try:
        if dataset_name == "metr-la":
            df_loc = pd.read_csv(loc_file)
            lats = df_loc["latitude"].values
            lons = df_loc["longitude"].values
        else:
            df_loc = pd.read_csv(loc_file, header=None)
            lats = df_loc[1].values
            lons = df_loc[2].values
    except Exception as e:
        print(f"[Warning] Failed to parse locations file {loc_file}: {e}")
        return ""
        
    return generate_interactive_map(lats, lons, scores, save_dir=save_dir)


def generate_interactive_map(
    lats: np.ndarray, 
    lons: np.ndarray, 
    scores: np.ndarray, 
    save_dir: str = OUTPUT_GRAPH_DIR
) -> str:
    """
    Generate Folium spatial map of bottleneck sensor locations.
    
    Returns:
        str: Absolute filepath to HTML output.
    """
    if folium is None:
        print("[Warning] Folium library not installed. Skipping interactive HTML map generation.")
        return ""

    center_lat, center_lon = float(np.mean(lats)), float(np.mean(lons))
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
    
    top_cutoff = np.quantile(scores, 0.90)
    
    for lat, lon, score in zip(lats, lons, scores):
        is_bottleneck = score >= top_cutoff
        color = "red" if is_bottleneck else "blue"
        radius = 6 if is_bottleneck else 3
        
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=f"Congestion Score: {score:.3f}"
        ).add_to(m)
        
    map_path = os.path.join(save_dir, "bottleneck_map.html")
    m.save(map_path)
    print(f"[BottleNet] Interactive map generated successfully at: {map_path}")
    return map_path
