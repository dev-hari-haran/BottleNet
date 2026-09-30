"""
BottleNet Configuration File
Centralized path definitions and hyperparameter constants.
"""

import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW_DIR = os.path.join(BASE_DIR, "Data")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_GRAPH_DIR = os.path.join(BASE_DIR, "outputs", "graphs")
OUTPUT_LOG_DIR = os.path.join(BASE_DIR, "outputs", "logs")
CHECKPOINT_DIR = os.path.join(OUTPUT_LOG_DIR, "checkpoints")

# Ensure required output directories exist
for path in [DATA_PROCESSED_DIR, OUTPUT_GRAPH_DIR, OUTPUT_LOG_DIR, CHECKPOINT_DIR]:
    os.makedirs(path, exist_ok=True)

# Datasets
DATASETS = {
    "metr-la": {
        "h5_file": os.path.join(DATA_RAW_DIR, "metr-la.h5"),
        "adj_file": os.path.join(DATA_RAW_DIR, "adj_mx.pkl"),
        "num_sensors": 207,
    },
    "pems-bay": {
        "h5_file": os.path.join(DATA_RAW_DIR, "pems-bay.h5"),
        "adj_file": os.path.join(DATA_RAW_DIR, "adj_mx_bay.pkl"),
        "num_sensors": 325,
    }
}

# Default Hyperparameters & Constraints
TIME_INTERVAL_MINUTES = 5
TIME_DOMAIN_T = 12            # 12 intervals = 1 hour window
ROLLING_STEP_DELTA_T = 2      # 2 intervals = 10 min step
TOP_N_FRACTION = 0.1          # Top 10% threshold
VOTING_MAX_ITER = 50          # Convergence max iterations
VOTING_TOLERANCE = 1e-4       # Convergence threshold

# Advanced Model Hyperparameters (Accuracy Optimization)
GNN_HIDDEN_CHANNELS = 128     # Expanded capacity (up from 64)
GNN_IN_CHANNELS = 10          # Expanded node feature space
GNN_NUM_CLASSES = 2           # Binary classification: Bottleneck vs Normal
LEARNING_RATE = 2e-3          # Optimized learning rate
WEIGHT_DECAY = 1e-4           # L2 Regularization to prevent overfitting
BATCH_SIZE = 32
TRAIN_EPOCHS = 100
DROPOUT_RATE = 0.2            # Tuned dropout rate

# OSMnx Bounding Box (Los Angeles Sensor Area)
LA_BBOX = {
    "north": 34.2,
    "south": 33.7,
    "east": -117.9,
    "west": -118.7
}
GRAPHML_CACHE_FILE = os.path.join(DATA_RAW_DIR, "la_road_network.graphml")
