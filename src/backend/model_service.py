import os
import sys
import yaml
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ML_MODEL_DIR = os.path.join(PROJECT_ROOT, "src/ml_model")
sys.path.append(ML_MODEL_DIR)

class ModelService:
    def __init__(self):
        self.predictor = None
        self.config = None
        self._load_predictor()

    def _load_predictor(self):
        config_path = os.path.join(ML_MODEL_DIR, "config.yaml")
        model_path = os.path.join(PROJECT_ROOT, "results/models/latest_model.pkl")
        
        if os.path.exists(config_path) and os.path.exists(model_path):
            try:
                from predict import TierPredictor
                from preprocessing import load_config
                self.config = load_config(config_path)
                self.predictor = TierPredictor(self.config, model_path)
                print("[ModelService] Successfully loaded trained TierPredictor.")
            except Exception as e:
                print(f"[ModelService] Failed to load TierPredictor: {e}")
                self.predictor = None
        else:
            print("[ModelService] Model artifact not found. Using algorithmic cost decision rule.")

    def predict_scan(self, scan_dict: Dict[str, Any], size_gb: float = 0.015) -> Dict[str, Any]:
        """
        Run two-stage recommendation for a scan:
        Stage 1: Predict P(retrieval)
        Stage 2: Argmin expected cost over S3 tiers
        """
        if self.predictor is not None:
            try:
                # Build feature dataframe
                feat = {
                    'Patient Age': scan_dict.get('patient_age', 50),
                    'Follow-up #': scan_dict.get('follow_up_number', 0),
                    'prior_study_count': scan_dict.get('follow_up_number', 0),
                    'Original Image Width': 1024,
                    'Original Image Height': 1024,
                    'Original Image Pixel Spacing x': 0.143,
                    'Original Image Pixel Spacing y': 0.143,
                    'gender_M': 1 if scan_dict.get('patient_gender') == 'M' else 0,
                    'view_PA': 1 if scan_dict.get('view_position') == 'PA' else 0,
                }
                
                # Findings
                finding_labels = scan_dict.get('finding_labels', '')
                for f in ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 'Emphysema', 
                          'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 'Pleural_Thickening', 
                          'Pneumonia', 'Pneumothorax', 'No_Finding']:
                    feat[f'finding_{f}'] = 1 if f.replace('_', ' ') in finding_labels else 0

                # 128 embedding features
                for i in range(128):
                    feat[f'emb_{i}'] = 0.0

                df_feat = pd.DataFrame([feat])
                result = self.predictor.predict_single(df_feat, size_gb=size_gb)
                
                # Map to standard AWS class names
                tier_mapping = {
                    's3_standard': 'STANDARD',
                    's3_standard_ia': 'STANDARD_IA',
                    's3_glacier': 'GLACIER',
                    's3_deep_archive': 'DEEP_ARCHIVE'
                }
                
                optimal_tier = tier_mapping.get(result['optimal_tier'], result['optimal_tier'].upper())
                p_val = result['p_retrieve']
                
                costs_formatted = {
                    tier_mapping.get(k, k): round(v, 5) for k, v in result['expected_costs'].items()
                }
                
                reason = (
                    f"Predicted retrieval probability P={p_val:.3f}. "
                    f"Expected 12-month cost minimized in {optimal_tier} (${costs_formatted.get(optimal_tier, 0):.4f}/year) "
                    f"accounting for storage, transition, retrieval fees, and clinical safety penalty."
                )
                
                return {
                    'predicted_class': optimal_tier,
                    'probability': float(p_val),
                    'reason': reason,
                    'cost_breakdown': costs_formatted
                }
            except Exception as e:
                print(f"[ModelService] Inference error ({e}), falling back to heuristic.")

        # Algorithmic fallback rule (Stage 2 explicit calculation)
        follow_ups = scan_dict.get('follow_up_number', 0)
        has_finding = scan_dict.get('finding_labels', 'No Finding') != 'No Finding'
        
        # Clinical retrieval probability proxy
        base_p = 0.10
        if has_finding:
            base_p += 0.35
        if follow_ups > 0:
            base_p += 0.25
        p_val = min(0.95, max(0.02, base_p))
        
        # Expected costs per tier for 15MB file (annual)
        costs = {
            'STANDARD': round(0.023 * size_gb * 12, 5),
            'STANDARD_IA': round(0.0125 * max(size_gb, 0.000125) * 12 + p_val * (0.01 * size_gb) + p_val * 0.002, 5),
            'GLACIER': round(0.0036 * max(size_gb + 0.00004, 0.000125) * 12 + 0.00003 + p_val * (0.01 * size_gb) + p_val * 0.008, 5),
            'DEEP_ARCHIVE': round(0.00099 * max(size_gb + 0.00004, 0.000125) * 12 + 0.00005 + p_val * (0.02 * size_gb) + p_val * 0.020, 5)
        }
        
        optimal_tier = min(costs, key=costs.get)
        reason = (
            f"Calculated retrieval probability P={p_val:.2f}. "
            f"Expected total cost is minimized in {optimal_tier} (${costs[optimal_tier]:.5f}/yr) "
            f"balancing rapid access vs long-term storage fees."
        )
        
        return {
            'predicted_class': optimal_tier,
            'probability': float(p_val),
            'reason': reason,
            'cost_breakdown': costs
        }

model_service = ModelService()
