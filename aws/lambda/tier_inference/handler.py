"""S3 event handler using precomputed, pretrained chest X-ray scores."""

import json
import logging
import os
import sys
import urllib.parse
import uuid
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

from decision_engine import DecisionEngine, stable_scan_id  # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "ScanFeatures")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME", "DecisionAudit")
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
        "audit": boto3.resource("dynamodb").Table(AUDIT_TABLE_NAME),
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


def _write_audit(resources, scan_id, event_type, details):
    created_at = datetime.now(timezone.utc).isoformat()
    resources["audit"].put_item(Item={
        "scan_id": scan_id,
        "event_id": f"{created_at}#{uuid.uuid4()}",
        "event_type": event_type,
        "actor": "tier-inference-lambda",
        "created_at": created_at,
        "details": json.loads(json.dumps(details), parse_float=Decimal),
    })


def process_record(record, resources, engine):
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    size = int(record["s3"]["object"]["size"])
    scan_id = stable_scan_id(bucket, key)
    table = resources["table"]

    response = table.get_item(Key={"scan_id": scan_id}, ConsistentRead=True)
    item = response.get("Item")
    timestamp = datetime.now(timezone.utc).isoformat()
    if not item:
        logger.warning("No registered features for %s; retaining S3 Standard", scan_id)
        table.update_item(
            Key={"scan_id": scan_id},
            UpdateExpression=(
                "SET decision_status=:status, requested_tier=:tier, decision_timestamp=:time, "
                "object_size_bytes=:size, object_key=:key, bucket_name=:bucket"
            ),
            ExpressionAttributeValues={
                ":status": "BLOCKED_MISSING_FEATURES",
                ":tier": "STANDARD",
                ":time": timestamp,
                ":size": size,
                ":key": key,
                ":bucket": bucket,
            },
        )
        _emit_metric(resources["cloudwatch"], "DecisionBlockedMissingFeatures")
        _write_audit(resources, scan_id, "DECISION_BLOCKED", {"reason": "missing_features"})
        return {"scan_id": scan_id, "status": "BLOCKED_MISSING_FEATURES"}

    # A copy made by an authorized manual override also emits ObjectCreated.
    # Keep the operator's requested tier until reconciliation confirms the copy.
    if item.get("override_reason") and item.get("decision_status") == "PENDING_TRANSITION":
        return {"scan_id": scan_id, "status": "PENDING_TRANSITION", "tier": item.get("requested_tier")}

    pathology_scores = item.get("pathology_scores") or {}
    result = engine.recommend(item, pathology_scores, size_bytes=size)
    tier = result["predicted_class"]
    _merge_tier_tag(resources["s3"], bucket, key, tier)
    table.update_item(
        Key={"scan_id": scan_id},
        UpdateExpression=(
            "SET requested_tier=:tier, decision_status=:status, probability=:prob, "
            "decision_reason=:reason, decision_timestamp=:time, object_size_bytes=:size, "
            "policy_version=:version, object_key=:key, bucket_name=:bucket"
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
            ":bucket": bucket,
        },
    )
    _emit_metric(
        resources["cloudwatch"],
        "TierRequested",
        dimensions=[{"Name": "Tier", "Value": tier}],
    )
    _write_audit(resources, scan_id, "TIER_RECOMMENDED", {
        "tier": tier, "probability": result["probability"], "policy_version": result["policy_version"],
    })
    logger.info("Requested %s for %s using %s", tier, scan_id, result["policy_version"])
    return {"scan_id": scan_id, "status": "PENDING_TRANSITION", "tier": tier}


def reconcile(resources):
    """Confirm requested storage and completed restores from actual S3 object state."""
    table, s3 = resources["table"], resources["s3"]
    items = []
    request = {}
    while True:
        page = table.scan(**request)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            break
        request["ExclusiveStartKey"] = key
    updated = 0
    for item in items:
        if item.get("decision_status") != "PENDING_TRANSITION" and item.get("restore_status") != "PENDING":
            continue
        bucket, key = item.get("bucket_name"), item.get("object_key")
        if not bucket or not key:
            continue
        head = s3.head_object(Bucket=bucket, Key=key)
        observed = head.get("StorageClass", "STANDARD")
        expressions = ["observed_tier=:observed", "last_reconciled_at=:time"]
        values = {":observed": observed, ":time": datetime.now(timezone.utc).isoformat()}
        if item.get("requested_tier") == observed:
            expressions.extend(["current_tier=:observed", "decision_status=:applied"])
            values[":applied"] = "APPLIED"
        restore_header = str(head.get("Restore", ""))
        if item.get("restore_status") == "PENDING" and 'ongoing-request="false"' in restore_header:
            expressions.extend(["restore_status=:complete", "restore_completed_at=:time"])
            values[":complete"] = "COMPLETE"
        table.update_item(
            Key={"scan_id": item["scan_id"]},
            UpdateExpression="SET " + ", ".join(expressions),
            ExpressionAttributeValues=values,
        )
        _write_audit(resources, item["scan_id"], "PLACEMENT_RECONCILED", {
            "observed_tier": observed,
            "decision_status": "APPLIED" if item.get("requested_tier") == observed else item.get("decision_status"),
        })
        updated += 1
    _emit_metric(resources["cloudwatch"], "ObjectsReconciled", value=updated)
    return {"reconciled": updated}


def lambda_handler(event, context):
    resources = _aws_resources()
    engine = _engine()
    if event.get("source") == "aws.events":
        return {"statusCode": 200, "body": json.dumps(reconcile(resources))}
    processed = []
    for record in event.get("Records", []):
        try:
            processed.append(process_record(record, resources, engine))
        except Exception:
            logger.exception("Inference failed for an S3 event")
            _emit_metric(resources["cloudwatch"], "InferenceFailure")
            raise
    return {"statusCode": 200, "body": json.dumps({"processed": processed})}
