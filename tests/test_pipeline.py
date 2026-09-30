"""
Unit Test Suite for BottleNet Preprocessing, Voting, and GNN Modules.
"""

import unittest
import numpy as np
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.preprocess import impute_missing, normalize, build_feature_matrix
from src.voting import compute_scores, rank_links
from src.graph import get_top_n_bottlenecks


class TestBottleNetPipeline(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.raw_data = np.random.uniform(10.0, 65.0, size=(12, 10)).astype(np.float32)
        self.raw_data[2, 3] = np.nan
        self.raw_data[5, 7] = np.nan

    def test_impute_missing(self):
        imputed = impute_missing(self.raw_data)
        self.assertFalse(np.isnan(imputed).any(), "Imputed data should contain no NaN values.")
        self.assertEqual(imputed.shape, (12, 10))

    def test_normalize(self):
        imputed = impute_missing(self.raw_data)
        norm = normalize(imputed)
        self.assertTrue((norm >= 0.0).all() and (norm <= 1.0).all(), "Normalized values must be within [0, 1].")

    def test_build_feature_matrix(self):
        features = build_feature_matrix(self.raw_data)
        # Feature shape should be [T=12, N=10, 10]
        self.assertEqual(features.shape, (12, 10, 10))

    def test_voting_scores(self):
        imputed = impute_missing(self.raw_data)
        scores = compute_scores(imputed, max_iter=20)
        self.assertEqual(scores.shape, (10,))
        self.assertTrue((scores >= 0.0).all() and (scores <= 1.0).all(), "Scores must be normalized to [0, 1].")

    def test_top_n_bottlenecks(self):
        scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        bottlenecks = get_top_n_bottlenecks(scores, top_n_fraction=0.2)
        self.assertEqual(np.sum(bottlenecks), 2, "Top 20% of 10 items should yield exactly 2 bottlenecks.")


if __name__ == "__main__":
    unittest.main()
