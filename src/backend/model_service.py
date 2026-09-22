"""Application adapter for the shared, inference-only decision engine."""

import os
import sys
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ML_MODEL_DIR = os.path.join(PROJECT_ROOT, "src", "ml_model")
if ML_MODEL_DIR not in sys.path:
    sys.path.insert(0, ML_MODEL_DIR)

from decision_engine import DecisionEngine  # noqa: E402


class ModelService:
    def __init__(self):
        self.engine = DecisionEngine()
        self.predictor = self.engine  # Retained for the existing health endpoint.

    def predict_scan(
        self,
        scan_dict: Dict[str, Any],
        size_gb: float = 0.015,
    ) -> Dict[str, Any]:
        """Recommend a tier without fitting or loading a locally trained model."""
        pathology_scores = scan_dict.get("pathology_scores") or {}
        size_bytes = int(scan_dict.get("object_size_bytes") or size_gb * 1024**3)
        return self.engine.recommend(
            metadata=scan_dict,
            pathology_scores=pathology_scores,
            size_bytes=size_bytes,
            horizon_months=12,
        )


model_service = ModelService()
