"""
High-Accuracy BottleNet Graph Neural Network with Residual Connections & Batch Normalization.
"""

from typing import Tuple, Dict, Any, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GCNConv
except ImportError:
    GCNConv = None

class BottleNet(nn.Module):
    """
    Advanced BottleNet GNN Model with Residual Skip-Connections & Batch Normalization.
    Input Channels: 10
    Hidden Channels: 128
    Classes: 2 (Binary Bottleneck Classification)
    """
    def __init__(
        self, 
        in_channels: int = 10, 
        hidden_channels: int = 128, 
        num_classes: int = 2,
        dropout: float = 0.2
    ):
        super(BottleNet, self).__init__()
        
        if GCNConv is None:
            raise ImportError(
                "torch_geometric is required to instantiate BottleNet. "
                "Please run: pip install torch-geometric"
            )
            
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.bn1 = nn.BatchNorm1d(hidden_channels)
        
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.bn2 = nn.BatchNorm1d(hidden_channels)
        
        self.conv3 = GCNConv(hidden_channels, hidden_channels)
        self.bn3 = nn.BatchNorm1d(hidden_channels)
        
        self.fc1 = nn.Linear(hidden_channels, 64)
        self.bn_fc = nn.BatchNorm1d(64)
        self.fc2 = nn.Linear(64, num_classes)
        
        self.dropout_rate = dropout
        self.relu = nn.ReLU()

    def forward(
        self, 
        x: torch.Tensor, 
        edge_index: torch.Tensor, 
        edge_weight: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass with residual connections.
        
        Args:
            x (torch.Tensor): Feature tensor [N, in_channels].
            edge_index (torch.Tensor): Edge indices [2, E].
            edge_weight (torch.Tensor, optional): Edge weights [E].
            
        Returns:
            torch.Tensor: Class logits [N, num_classes].
        """
        # Layer 1
        h1 = self.conv1(x, edge_index, edge_weight=edge_weight)
        h1 = self.bn1(h1)
        h1 = self.relu(h1)
        h1 = F.dropout(h1, p=self.dropout_rate, training=self.training)
        
        # Layer 2 + Residual Connection
        h2 = self.conv2(h1, edge_index, edge_weight=edge_weight)
        h2 = self.bn2(h2)
        h2 = self.relu(h2 + h1)  # Skip Connection
        h2 = F.dropout(h2, p=self.dropout_rate, training=self.training)
        
        # Layer 3 + Residual Connection
        h3 = self.conv3(h2, edge_index, edge_weight=edge_weight)
        h3 = self.bn3(h3)
        h3 = self.relu(h3 + h2)  # Skip Connection
        
        # Dense Classifier Layers
        out = self.fc1(h3)
        out = self.bn_fc(out)
        out = self.relu(out)
        out = F.dropout(out, p=self.dropout_rate, training=self.training)
        
        logits = self.fc2(out)
        return logits


def matrix_to_edge_index(adj_matrix: Any) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Convert dense numpy adjacency matrix to PyTorch Geometric edge_index and edge_weight format.
    
    Returns:
        Tuple[torch.Tensor, torch.Tensor]: (edge_index [2, E], edge_weight [E])
    """
    import numpy as np
    if isinstance(adj_matrix, torch.Tensor):
        adj_matrix = adj_matrix.cpu().numpy()
        
    src, dst = np.where(adj_matrix > 0)
    weights = adj_matrix[src, dst]
    
    edge_index = torch.tensor(np.vstack([src, dst]), dtype=torch.long)
    edge_weight = torch.tensor(weights, dtype=torch.float32)
    
    return edge_index, edge_weight
