"""CLI for inference-only storage-tier recommendation."""

import argparse
import json
from pathlib import Path

from decision_engine import DecisionEngine


def load_json(path):
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    parser = argparse.ArgumentParser(
        description="Recommend an S3 tier from metadata and pretrained pathology scores"
    )
    parser.add_argument("--metadata", help="JSON object containing scan metadata")
    parser.add_argument(
        "--features",
        help="JSON created by extract_pretrained_features.py, or a pathology-score map",
    )
    parser.add_argument("--size-bytes", type=int, required=True)
    parser.add_argument("--horizon-months", type=float, default=12)
    args = parser.parse_args()

    metadata = load_json(args.metadata)
    feature_payload = load_json(args.features)
    pathology_scores = feature_payload.get("pathology_scores", feature_payload)
    result = DecisionEngine().recommend(
        metadata,
        pathology_scores,
        size_bytes=args.size_bytes,
        horizon_months=args.horizon_months,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
