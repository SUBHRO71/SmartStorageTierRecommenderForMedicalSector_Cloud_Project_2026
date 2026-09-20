"""S3 event handler using precomputed, pretrained chest X-ray scores."""

import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HERE = Path(__file__).resolve().parent
PROJECT_ENGINE = HERE.parents[2] / "src" / "ml_model"
for candidate in (HERE, PROJECT_ENGINE):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from decision_engine import DecisionEngine  # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "ScanFeatures")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
POLICY_PATH = os.environ.get(
    "POLICY_PATH", str(HERE / "retrieval_policy_weights.json")
)


def _engine():
    path = POLICY_PATH if Path(POLICY_PATH).exists() else None
    return DecisionEngine(path)


def _aws_resources():
    """Create clients only during invocation; IAM roles supply credentials in AWS."""
    return {
        "s3": boto3.client("s3"),
        "table": boto3.resource("dynamodb").Table(TABLE_NAME),
        "cloudwatch": boto3.client("cloudwatch"),
        "sns": boto3.client("sns"),
    }


def _decimal(value):
    return Decimal(str(value))


def _merge_tier_tag(s3, bucket, key, tier):
    current = s3.get_object_tagging(Bucket=bucket, Key=key).get("TagSet", [])
    merged = {tag["Key"]: tag["Value"] for tag in current}
    merged["tier"] = tier
    s3.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in merged.items()]},
    )


def _emit_metric(cloudwatch, name, value=1, dimensions=None):
    metric = {"MetricName": name, "Value": value, "Unit": "Count"}
    if dimensions:
        metric["Dimensions"] = dimensions
    try:
        cloudwatch.put_metric_data(Namespace="SmartStorage", MetricData=[metric])
    except Exception as exc:  # The decision must remain valid if telemetry fails.
        logger.warning("CloudWatch metric failed: %s", exc)


def process_record(record, resources, engine):
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    size = int(record["s3"]["object"]["size"])
    scan_id = key
    table = resources["table"]

    response = table.get_item(Key={"scan_id": scan_id}, ConsistentRead=True)
    item = response.get("Item")
    timestamp = datetime.now(timezone.utc).isoformat()
    if not item:
        logger.warning("No registered features for %s; retaining S3 Standard", scan_id)
        table.update_item(
            Key={"scan_id": scan_id},
            UpdateExpression=(
                "SET decision_status=:status, requested_tier=:tier, "
                "decision_timestamp=:time, object_size_bytes=:size, object_key=:key"
            ),
            ExpressionAttributeValues={
                ":status": "BLOCKED_MISSING_FEATURES",
                ":tier": "STANDARD",
                ":time": timestamp,
                ":size": size,
                ":key": key,
            },
        )
        _emit_metric(resources["cloudwatch"], "DecisionBlockedMissingFeatures")
        return {"scan_id": scan_id, "status": "BLOCKED_MISSING_FEATURES"}

    pathology_scores = item.get("pathology_scores") or {}
    result = engine.recommend(item, pathology_scores, size_bytes=size)
    tier = result["predicted_class"]
    _merge_tier_tag(resources["s3"], bucket, key, tier)
    table.update_item(
        Key={"scan_id": scan_id},
        UpdateExpression=(
            "SET requested_tier=:tier, decision_status=:status, probability=:prob, "
            "decision_reason=:reason, decision_timestamp=:time, object_size_bytes=:size, "
            "policy_version=:version, object_key=:key"
        ),
        ExpressionAttributeValues={
            ":tier": tier,
            ":status": "PENDING_TRANSITION",
            ":prob": _decimal(result["probability"]),
            ":reason": result["reason"],
            ":time": timestamp,
            ":size": size,
            ":version": result["policy_version"],
            ":key": key,
        },
    )
    _emit_metric(
        resources["cloudwatch"],
        "TierRequested",
        dimensions=[{"Name": "Tier", "Value": tier}],
    )
    logger.info("Requested %s for %s using %s", tier, scan_id, result["policy_version"])
    return {"scan_id": scan_id, "status": "PENDING_TRANSITION", "tier": tier}


def lambda_handler(event, context):
    resources = _aws_resources()
    engine = _engine()
    processed = []
    for record in event.get("Records", []):
        try:
            processed.append(process_record(record, resources, engine))
        except Exception:
            logger.exception("Inference failed for an S3 event")
            _emit_metric(resources["cloudwatch"], "InferenceFailure")
            raise
    return {"statusCode": 200, "body": json.dumps({"processed": processed})}
