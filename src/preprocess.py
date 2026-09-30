"""
Advanced Data Preprocessing & Feature Engineering Module for BottleNet.
Handles h5 loading, missing value imputation, normalization, and 10-feature node spatial-temporal engineering.
"""

import os
import pickle
import numpy as np
import pandas as pd
import h5py
from typing import Tuple, Dict, Any

def load_h5_data(filepath: str) -> np.ndarray:
    """Load speed data matrix [T, N] from h5 file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"\n[BottleNet] MISSING FILE: {filepath}\n"
            f"Please download the dataset from https://github.com/liyaguang/DCRNN "
            f"and place it at: {filepath}"
        )
    
    with h5py.File(filepath, 'r') as f:
        if 'df' in f and 'block0_values' in f['df']:
            data = np.array(f['df']['block0_values'])
        elif 'speed' in f:
            if hasattr(f['speed'], 'keys') and 'block0_values' in f['speed']:
                data = np.array(f['speed']['block0_values'])
            elif isinstance(f['speed'], h5py.Dataset):
                data = np.array(f['speed'])
            else:
                data = np.array(f['speed'])
        else:
            key = list(f.keys())[0]
            if hasattr(f[key], 'keys') and 'block0_values' in f[key]:
                data = np.array(f[key]['block0_values'])
            else:
                data = np.array(f[key])
            
    return data.astype(np.float32)


def load_adj_matrix(filepath: str) -> Tuple[list, dict, np.ndarray]:
    """Load sensor adjacency matrix and ID mapping from pickle file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"\n[BottleNet] MISSING FILE: {filepath}\n"
            f"Place adj_mx file at: {filepath}"
        )
    
    with open(filepath, 'rb') as f:
        try:
            sensor_ids, sensor_id_to_ind, adj_mx = pickle.load(f, encoding='latin1')
        except Exception:
            f.seek(0)
            sensor_ids, sensor_id_to_ind, adj_mx = pickle.load(f)
            
    return sensor_ids, sensor_id_to_ind, adj_mx.astype(np.float32)


def impute_missing(data: np.ndarray) -> np.ndarray:
    """Impute missing NaN values using per-sensor median across timesteps."""
    data_imputed = data.copy()
    nan_mask = np.isnan(data_imputed)
    
    if not np.any(nan_mask):
        return data_imputed
        
    sensor_medians = np.nanmedian(data_imputed, axis=0)
    global_median = np.nanmedian(sensor_medians)
    if np.isnan(global_median):
        global_median = 30.0
    sensor_medians = np.nan_to_num(sensor_medians, nan=global_median)
    
    inds = np.where(nan_mask)
    data_imputed[inds] = sensor_medians[inds[1]]
    return data_imputed


def normalize(data: np.ndarray) -> np.ndarray:
    """Min-max normalize link speeds per sensor to [0, 1]."""
    min_val = np.min(data, axis=0, keepdims=True)
    max_val = np.max(data, axis=0, keepdims=True)
    denom = max_val - min_val
    denom[denom == 0] = 1e-8
    return (data - min_val) / denom


def build_feature_matrix(data: np.ndarray, adj_mx: np.ndarray = None, hour_array: np.ndarray = None) -> np.ndarray:
    """
    Engineer 10 rich spatial-temporal node features for graph neural network:
    1. speed_mph
    2. normalized_speed
    3. inverse_speed (1 / (speed + 1e-5))
    4. hour (0-23)
    5. is_peak_hour (1 if 7-9am or 5-7pm, else 0)
    6. link_rank (placeholder / computed per window)
    7. rolling_mean_3 (15-min rolling mean speed)
    8. rolling_std_3 (15-min speed volatility/standard deviation)
    9. neighbor_avg_speed (spatial 1-hop neighbor average speed)
    10. speed_drop_ratio (drop relative to per-sensor historical median)
    
    Returns:
        np.ndarray: Feature matrix of shape [T, N, 10].
    """
    T, N = data.shape
    data_imputed = impute_missing(data)
    norm_speed = normalize(data_imputed)
    inv_speed = 1.0 / (data_imputed + 1e-5)
    
    if hour_array is None:
        total_minutes = np.arange(T) * 5
        hour_array = (total_minutes // 60) % 24
        
    hour_matrix = np.tile(hour_array[:, np.newaxis], (1, N))
    is_peak = (((hour_matrix >= 7) & (hour_matrix < 9)) | 
               ((hour_matrix >= 17) & (hour_matrix < 19))).astype(np.float32)
    
    link_rank = np.zeros((T, N), dtype=np.float32)
    
    # 7 & 8: Rolling temporal statistics (window size 3 intervals = 15 min)
    df_data = pd.DataFrame(data_imputed)
    rolling_mean_3 = df_data.rolling(window=3, min_periods=1).mean().values.astype(np.float32)
    rolling_std_3 = df_data.rolling(window=3, min_periods=1).std().fillna(0.0).values.astype(np.float32)
    
    # 9: Spatial neighbor average speed via adjacency matrix
    if adj_mx is not None and adj_mx.shape == (N, N):
        # Normalize adjacency weights per row
        adj_binary = (adj_mx > 0).astype(np.float32)
        row_sum = np.sum(adj_binary, axis=1, keepdims=True)
        row_sum[row_sum == 0] = 1.0
        norm_adj = adj_binary / row_sum
        neighbor_avg_speed = np.matmul(data_imputed, norm_adj.T)
    else:
        neighbor_avg_speed = data_imputed.copy()
        
    # 10: Speed drop ratio relative to sensor historical median
    sensor_medians = np.median(data_imputed, axis=0, keepdims=True)
    sensor_medians[sensor_medians == 0] = 1.0
    speed_drop_ratio = np.clip(1.0 - (data_imputed / sensor_medians), 0.0, 1.0)
    
    # Stack all 10 engineered features
    features = np.stack([
        data_imputed, norm_speed, inv_speed, 
        hour_matrix.astype(np.float32), is_peak, link_rank,
        rolling_mean_3, rolling_std_3, neighbor_avg_speed, speed_drop_ratio
    ], axis=-1)
    
    return features
