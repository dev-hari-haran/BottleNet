"""
Road Network Graph Construction & Spatial Bottleneck Component Tracking Module.
"""

import os
import networkx as nx
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from config import LA_BBOX, GRAPHML_CACHE_FILE, TOP_N_FRACTION

def load_or_fetch_road_graph(cache_path: str = GRAPHML_CACHE_FILE) -> nx.MultiDiGraph:
    """
    Load cached OSMnx LA graph or fetch via OSMnx and project to UTM.
    
    Args:
        cache_path (str): Filepath to graphml cache.
        
    Returns:
        nx.MultiDiGraph: Project road network graph.
    """
    import osmnx as ox
    
    if os.path.exists(cache_path):
        print(f"[BottleNet] Loading cached road network graph from {cache_path}")
        return ox.load_graphml(cache_path)
        
    print(f"[BottleNet] Downloading OSMnx road graph for bbox: {LA_BBOX}")
    try:
        G = ox.graph_from_bbox(
            north=LA_BBOX["north"], south=LA_BBOX["south"],
            east=LA_BBOX["east"], west=LA_BBOX["west"],
            network_type="drive", simplify=True
        )
        G_proj = ox.project_graph(G)
        ox.save_graphml(G_proj, filepath=cache_path)
        return G_proj
    except Exception as e:
        raise RuntimeError(
            f"\n[BottleNet] OSMnx download failed: {e}\n"
            f"Check internet connection or place road graph at: {cache_path}"
        )


def get_top_n_bottlenecks(scores: np.ndarray, top_n_fraction: float = TOP_N_FRACTION) -> np.ndarray:
    """
    Identify bottleneck sensor indices thresholded at top-N fraction.
    
    Args:
        scores (np.ndarray): Congestion scores [N].
        top_n_fraction (float): Top percentile fraction (default 0.1 for top 10%).
        
    Returns:
        np.ndarray: Binary array where 1 = bottleneck link, 0 = normal link.
    """
    cutoff = np.quantile(scores, 1.0 - top_n_fraction)
    return (scores >= cutoff).astype(int)


def extract_bottleneck_components(
    adj_matrix: np.ndarray, 
    bottleneck_mask: np.ndarray,
    sensor_coords: pd.DataFrame = None
) -> List[Dict[str, Any]]:
    """
    Extract connected bottleneck components from adjacency matrix.
    
    Args:
        adj_matrix (np.ndarray): Binary or weighted adjacency matrix [N, N].
        bottleneck_mask (np.ndarray): Binary mask [N] where 1 = bottleneck link.
        sensor_coords (pd.DataFrame, optional): DataFrame with 'latitude' and 'longitude'.
        
    Returns:
        List[Dict[str, Any]]: Metadata per connected bottleneck component.
    """
    bottleneck_indices = np.where(bottleneck_mask == 1)[0]
    if len(bottleneck_indices) == 0:
        return []
        
    # Build subgraph of bottleneck nodes
    sub_adj = adj_matrix[np.ix_(bottleneck_indices, bottleneck_indices)]
    G_sub = nx.from_numpy_array(sub_adj > 0)
    
    # Mapping sub_graph nodes to original sensor indices
    node_map = {i: idx for i, idx in enumerate(bottleneck_indices)}
    
    components = []
    for comp_id, comp_nodes in enumerate(nx.connected_components(G_sub)):
        orig_nodes = [node_map[n] for n in comp_nodes]
        size = len(orig_nodes)
        
        centre_lat, centre_lon = 0.0, 0.0
        if sensor_coords is not None and not sensor_coords.empty:
            lats = sensor_coords.iloc[orig_nodes]['latitude'].values
            lons = sensor_coords.iloc[orig_nodes]['longitude'].values
            centre_lat = float(np.mean(lats))
            centre_lon = float(np.mean(lons))
            
        components.append({
            "component_id": comp_id,
            "size": size,
            "sensor_indices": orig_nodes,
            "coverage_m": size * 500.0, # Estimated coverage length (meters)
            "centre_lat": centre_lat,
            "centre_lon": centre_lon
        })
        
    return components
