"""Shared, inference-only retrieval scoring and S3 placement policy.

This module deliberately uses only the Python standard library so it can be copied
into the lightweight AWS Lambda package. Image inference happens offline with
published pretrained weights; Lambda receives the resulting pathology scores.
"""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

BYTES_PER_GB = 1024**3
LIFECYCLE_MINIMUM_OBJECT_BYTES = 128 * 1024
ARCHIVE_STANDARD_METADATA_BYTES = 8 * 1024
ARCHIVE_TIER_METADATA_BYTES = 32 * 1024


def stable_scan_id(bucket: str, object_key: str) -> str:
    """Return a URL-safe stable identifier without exposing the complete object key."""
    material = f"{bucket}/{object_key}".encode("utf-8")
    return f"scan-{hashlib.sha256(material).hexdigest()[:24]}"


class DecisionEngine:
    """Apply versioned fixed weights, followed by an explicit cost policy."""

    def __init__(self, artifact_path: Optional[str] = None):
        path = Path(artifact_path) if artifact_path else Path(__file__).with_name(
            "retrieval_policy_weights.json"
        )
        with path.open("r", encoding="utf-8") as handle:
            self.artifact = json.load(handle)
        self.version = self.artifact["version"]
        self.price_snapshot = self.artifact["price_snapshot"]

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _has_abnormal_finding(metadata: Mapping[str, Any]) -> float:
        labels = str(
            metadata.get("finding_labels")
            or metadata.get("Finding Labels")
            or ""
        ).strip()
        return float(bool(labels) and labels.lower() not in {"no finding", "none", "normal"})

    def build_features(
        self,
        metadata: Mapping[str, Any],
        pathology_scores: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, float]:
        age = self._number(metadata.get("patient_age", metadata.get("Patient Age", 50)), 50)
        follow_up = max(
            0.0,
            self._number(metadata.get("follow_up_number", metadata.get("Follow-up #", 0))),
        )
        prior_access = max(
            0.0,
            self._number(metadata.get("access_count", metadata.get("prior_access_count", 0))),
        )
        scores = [
            min(1.0, max(0.0, self._number(value)))
            for value in (pathology_scores or {}).values()
        ]
        return {
            "age_scaled": min(2.0, max(-2.0, (age - 50.0) / 25.0)),
            "follow_up_log": math.log1p(follow_up),
            "prior_access_log": math.log1p(prior_access),
            "abnormal_finding": self._has_abnormal_finding(metadata),
            "pathology_max": max(scores, default=0.0),
            "pathology_mean": sum(scores) / len(scores) if scores else 0.0,
        }

    def retrieval_probability(
        self,
        metadata: Mapping[str, Any],
        pathology_scores: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        features = self.build_features(metadata, pathology_scores)
        weights = self.artifact["weights"]
        contributions = {
            name: features[name] * float(weights[name]) for name in weights
        }
        logit = float(self.artifact["intercept"]) + sum(contributions.values())
        probability = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, logit))))
        return {
            "probability": probability,
            "features": features,
            "contributions": contributions,
            "policy_version": self.version,
        }

    def cost_breakdown(
        self,
        tier: str,
        probability: float,
        size_bytes: int,
        horizon_months: float = 12.0,
    ) -> Dict[str, float]:
        if size_bytes <= 0:
            raise ValueError("size_bytes must be positive")
        if horizon_months <= 0:
            raise ValueError("horizon_months must be positive")

        settings = self.price_snapshot["tiers"][tier]
        effective_months = max(
            float(horizon_months), float(settings["minimum_duration_days"]) / 30.0
        )
        data_bytes = max(size_bytes, int(settings["minimum_billable_bytes"]))
        metadata_bytes = int(settings["archive_metadata_bytes"])

        storage = data_bytes / BYTES_PER_GB * float(settings["storage_gb_month"]) * effective_months
        metadata_standard = 0.0
        metadata_archive = 0.0
        if metadata_bytes:
            metadata_standard = (
                ARCHIVE_STANDARD_METADATA_BYTES / BYTES_PER_GB
                * self.price_snapshot["tiers"]["STANDARD"]["storage_gb_month"]
                * effective_months
            )
            metadata_archive = (
                ARCHIVE_TIER_METADATA_BYTES / BYTES_PER_GB
                * float(settings["storage_gb_month"])
                * effective_months
            )
        transition = float(settings["transition_1000_requests"]) / 1000.0
        retrieval = probability * (
            size_bytes / BYTES_PER_GB * float(settings["retrieval_gb"])
            + float(settings["retrieval_1000_requests"]) / 1000.0
        )
        monetary = storage + metadata_standard + metadata_archive + transition + retrieval
        access_penalty = probability * float(settings["access_penalty"])
        return {
            "storage": storage,
            "archive_metadata_standard": metadata_standard,
            "archive_metadata_tier": metadata_archive,
            "transition": transition,
            "expected_retrieval": retrieval,
            "monetary_cost": monetary,
            "access_delay_penalty": access_penalty,
            "policy_score": monetary + access_penalty,
        }

    def recommend(
        self,
        metadata: Mapping[str, Any],
        pathology_scores: Optional[Mapping[str, Any]] = None,
        size_bytes: Optional[int] = None,
        horizon_months: float = 12.0,
        allowed_tiers: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        object_size = int(
            size_bytes
            if size_bytes is not None
            else self._number(metadata.get("object_size_bytes"), 15 * 1024 * 1024)
        )
        risk = self.retrieval_probability(metadata, pathology_scores)
        available = list(allowed_tiers or self.price_snapshot["tiers"].keys())
        unknown = set(available) - set(self.price_snapshot["tiers"])
        if unknown:
            raise ValueError(f"Unknown storage tiers: {sorted(unknown)}")

        # S3 Lifecycle blocks sub-128 KB transitions by default. Keep them hot.
        if object_size < LIFECYCLE_MINIMUM_OBJECT_BYTES:
            available = ["STANDARD"]

        breakdown = {
            tier: self.cost_breakdown(
                tier, risk["probability"], object_size, horizon_months
            )
            for tier in available
        }
        chosen = min(available, key=lambda tier: breakdown[tier]["policy_score"])
        return {
            "predicted_class": chosen,
            "probability": risk["probability"],
            "reason": (
                f"{chosen} has the lowest {horizon_months:g}-month policy score "
                f"for P(retrieval)={risk['probability']:.3f}."
            ),
            "cost_breakdown": breakdown,
            "feature_contributions": risk["contributions"],
            "policy_version": self.version,
            "price_snapshot": {
                key: self.price_snapshot[key]
                for key in ("currency", "region", "reviewed_on")
            },
            "horizon_months": horizon_months,
        }
