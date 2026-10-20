"""Register scan metadata and upload an image when AWS credentials are available."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ml_model"))

from decision_engine import stable_scan_id  # noqa: E402


def decimalize(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: decimalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decimalize(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description="Register features before uploading a scan")
    parser.add_argument("image")
    parser.add_argument("--metadata", help="Optional JSON object with non-identifying metadata")
    parser.add_argument("--features", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--table", default="ScanFeatures")
    parser.add_argument("--key")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    image = Path(args.image)
    key = args.key or f"scans/{image.name}"
    metadata = (
        json.loads(Path(args.metadata).read_text(encoding="utf-8"))
        if args.metadata else {}
    )
    features = json.loads(Path(args.features).read_text(encoding="utf-8"))
    scan_id = stable_scan_id(args.bucket, key)
    item = {
        "scan_id": scan_id,
        "bucket_name": args.bucket,
        "object_key": key,
        "object_size_bytes": image.stat().st_size,
        "current_tier": "STANDARD",
        "decision_status": "FEATURES_READY",
        "pathology_scores": features.get("pathology_scores", features),
        **metadata,
    }
    if args.dry_run:
        print(json.dumps(item, indent=2))
        return

    import boto3

    session = boto3.Session(region_name=args.region)
    session.resource("dynamodb").Table(args.table).put_item(Item=decimalize(item))
    session.client("s3").upload_file(
        str(image), args.bucket, key, ExtraArgs={"Metadata": {"scan-id": scan_id}}
    )
    print(json.dumps({"scan_id": scan_id, "bucket": args.bucket, "key": key}, indent=2))


if __name__ == "__main__":
    main()
