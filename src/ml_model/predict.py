import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from model import GradientBoostedTierModel
from preprocessing import load_config

class TierPredictor:
    """Predicts the optimal S3 storage tier based on retrieval probability and costs."""
    
    def __init__(self, config: Dict[str, Any], model_path: str):
        self.config = config
        self.model = GradientBoostedTierModel(config)
        self.model.load(model_path)
        self.prices = config['aws_prices']
        self.penalties = config['training']['clinical_penalty']
        
        self.tiers = list(self.prices.keys())
        
    def expected_cost(self, tier: str, p_retrieve: float, size_gb: float, horizon_months: float = 12) -> float:
        """
        Calculate expected cost over a time horizon for a single object.
        Cost terms:
        a. Storage cost
        b. Minimum billable size
        c. Metadata overhead
        d. Transition request fees (amortized per object)
        e. Retrieval cost
        f. Minimum duration penalties (simplified as forced min storage)
        + Clinical penalty
        """
        p = self.prices[tier]
        
        # Adjust size for minimums and overhead
        size_kb = size_gb * 1024 * 1024
        billable_size_kb = max(size_kb, p['min_billable_kb']) + p['overhead_kb']
        billable_size_gb = billable_size_kb / (1024 * 1024)
        
        # Storage cost over horizon (respecting minimum duration)
        effective_months = max(horizon_months, p['min_duration_days'] / 30.0)
        storage_cost = p['storage_gb_mo'] * billable_size_gb * effective_months
        
        # Transition cost (per object)
        transition_cost = p['transition_1000_req'] / 1000.0
        
        # Retrieval cost (expected)
        retrieval_cost = p_retrieve * (p['retrieval_gb'] * size_gb + p['retrieval_1000_req'] / 1000.0)
        
        # Clinical penalty (expected)
        clinical_penalty = p_retrieve * self.penalties[tier]
        
        return storage_cost + transition_cost + retrieval_cost + clinical_penalty

    def predict_single(self, features: pd.DataFrame, size_gb: float = 0.05, horizon_months: float = 12) -> Dict[str, Any]:
        """Predict optimal tier for a single scan."""
        p_retrieve = self.model.predict_proba(features)[0, 1]
        
        costs = {}
        for tier in self.tiers:
            costs[tier] = self.expected_cost(tier, p_retrieve, size_gb, horizon_months)
            
        optimal_tier = min(costs, key=costs.get)
        
        return {
            "p_retrieve": float(p_retrieve),
            "optimal_tier": optimal_tier,
            "expected_costs": costs,
            "reason": f"P(retrieve)={p_retrieve:.3f}, making {optimal_tier} the most cost-effective."
        }

    def predict_batch(self, features: pd.DataFrame, sizes_gb: np.ndarray, horizon_months: float = 12) -> pd.DataFrame:
        """Predict optimal tiers for a batch of scans."""
        p_retrieve_arr = self.model.predict_proba(features)[:, 1]
        
        results = []
        for i, p_retrieve in enumerate(p_retrieve_arr):
            costs = {}
            for tier in self.tiers:
                costs[tier] = self.expected_cost(tier, p_retrieve, sizes_gb[i], horizon_months)
            
            optimal_tier = min(costs, key=costs.get)
            results.append({
                "p_retrieve": p_retrieve,
                "optimal_tier": optimal_tier
            })
            
        return pd.DataFrame(results)

if __name__ == "__main__":
    # Simple test
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = load_config(config_path)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    model_path = os.path.join(project_root, config['paths']['model_dir'], "latest_model.pkl")
    
    if os.path.exists(model_path):
        predictor = TierPredictor(config, model_path)
        print("Model loaded successfully.")
    else:
        print(f"Model not found at {model_path}. Please run train.py first.")
