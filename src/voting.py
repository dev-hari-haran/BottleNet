"""
Iterative Weighted Voting & Link Congestion Ranking Module (Phase 1 Baseline).
"""

import numpy as np
from typing import Tuple
from config import VOTING_MAX_ITER, VOTING_TOLERANCE

def compute_scores(velocity_matrix: np.ndarray, max_iter: int = VOTING_MAX_ITER) -> np.ndarray:
    """
    Run iterative weighted voting over a time window.
    
    Args:
        velocity_matrix (np.ndarray): Window speed matrix of shape [T_win, N].
        max_iter (int): Maximum convergence iterations.
        
    Returns:
        np.ndarray: Link congestion scores normalized to [0, 1] of shape [N].
    """
    T_win, N = velocity_matrix.shape
    
    # Normalize speed to [0, 1], lower speed = higher congestion
    min_spd = np.min(velocity_matrix, axis=0, keepdims=True)
    max_spd = np.max(velocity_matrix, axis=0, keepdims=True)
    denom = max_spd - min_spd
    denom[denom == 0] = 1e-8
    norm_speed = (velocity_matrix - min_spd) / denom
    
    # Congestion intensity C_ij = 1 - norm_speed
    congestion = 1.0 - norm_speed
    
    # Interval importance weight tau_j based on congestion variance
    std_j = np.std(congestion, axis=1)
    mean_j = np.mean(congestion, axis=1) + 1e-5
    tau = std_j / mean_j  # Shape [T_win]
    
    # Initialize link scores s_k evenly
    s = np.ones(N, dtype=np.float32) / N
    
    for iteration in range(max_iter):
        s_old = s.copy()
        
        # Rank links per interval j
        # Higher congestion = higher rank
        ranks = np.argsort(np.argsort(-congestion, axis=1), axis=1).astype(np.float32)
        mean_ranks = np.mean(ranks, axis=0) # Average rank per link across window
        
        # Rank discrepancy delta_ij: deviation of link rank at interval j from mean rank
        rank_diff = np.abs(ranks - mean_ranks[np.newaxis, :])
        delta = 1.0 / (1.0 + rank_diff) # Shape [T_win, N]
        
        # Combined weight W_ij = tau_j * delta_ij
        weights = tau[:, np.newaxis] * delta
        
        # Weighted sum congestion score s_k
        s = np.sum(weights * congestion, axis=0)
        
        # Normalize s to [0, 1]
        s_min, s_max = np.min(s), np.max(s)
        if s_max > s_min:
            s = (s - s_min) / (s_max - s_min)
        else:
            s = np.zeros(N, dtype=np.float32)
            
        # Check convergence
        diff = np.max(np.abs(s - s_old))
        if diff < VOTING_TOLERANCE:
            break
            
    return s


def rank_links(scores: np.ndarray) -> np.ndarray:
    """
    Rank links by congestion score in descending order.
    
    Args:
        scores (np.ndarray): Congestion scores of shape [N].
        
    Returns:
        np.ndarray: Sensor indices sorted from most congested to least congested.
    """
    return np.argsort(-scores)
