"""Authenticated API Gateway Lambda for scan, decision, cost, and restore flows."""

from __future__ import annotations

import json
import logging
import os
import sys
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

from decision_engine import DecisionEngine  # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "ScanFeatures")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME", "DecisionAudit")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
POLICY_PATH = os.environ.get("POLICY_PATH", str(HERE / "retrieval_policy_weights.json"))
VALID_TIERS = ("STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE")
TIER_RANK = {tier: rank for rank, tier in enumerate(VALID_TIERS)}


def _resources():
    return {
        "table": boto3.resource("dynamodb").Table(TABLE_NAME),
        "audit": boto3.resource("dynamodb").Table(AUDIT_TABLE_NAME),
        "s3": boto3.client("s3"),
    }


def _engine():
    return DecisionEngine(POLICY_PATH if Path(POLICY_PATH).exists() else None)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def error(status, code, message):
    return response(status, {"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}})


def body(event):
    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON")
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def groups(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    raw = str(claims.get("cognito:groups", "")).strip("[]")
    return {part.strip().strip("'") for part in raw.split(",") if part.strip()}


def may_mutate(event):
    return bool(groups(event) & {"archive-admin", "operator"})


def actor(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    return claims.get("sub") or claims.get("email") or "unknown"


def write_audit(table, event, scan_id, event_type, details):
    created_at = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "scan_id": scan_id,
        "event_id": f"{created_at}#{uuid.uuid4()}",
        "event_type": event_type,
        "actor": actor(event),
        "created_at": created_at,
        "details": json.loads(json.dumps(details, cls=DecimalEncoder), parse_float=Decimal),
    })


def get_item(table, scan_id):
    return table.get_item(Key={"scan_id": scan_id}, ConsistentRead=True).get("Item")


def merge_tier_tag(s3, item, tier):
    bucket, key = item.get("bucket_name"), item.get("object_key")
    if not bucket or not key:
        raise ValueError("Scan does not have an S3 location")
    current = s3.get_object_tagging(Bucket=bucket, Key=key).get("TagSet", [])
    tags = {entry["Key"]: entry["Value"] for entry in current}
    tags["tier"] = tier
    s3.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": [{"Key": key, "Value": value} for key, value in tags.items()]},
    )


def scan_all(table):
    items = []
    request = {}
    while True:
        page = table.scan(**request)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        request["ExclusiveStartKey"] = key


def list_scans(event, table):
    params = event.get("queryStringParameters") or {}
    try:
        limit = int(params.get("limit", 20))
    except ValueError:
        return error(400, "INVALID_LIMIT", "limit must be an integer")
    if not 1 <= limit <= 100:
        return error(400, "INVALID_LIMIT", "limit must be between 1 and 100")
    try:
        page_number = int(params.get("page", 1))
    except ValueError:
        return error(400, "INVALID_PAGE", "page must be an integer")
    if page_number < 1:
        return error(400, "INVALID_PAGE", "page must be at least 1")
    items = scan_all(table)
    tier = str(params.get("tier", "ALL")).upper()
    search = str(params.get("search", "")).lower()
    if tier != "ALL":
        if tier not in VALID_TIERS:
            return error(400, "INVALID_TIER", f"tier must be one of {VALID_TIERS}")
        items = [item for item in items if item.get("predicted_class") == tier or item.get("current_tier") == tier]
    if search:
        items = [
            item for item in items
            if search in str(item.get("scan_id", "")).lower()
            or search in str(item.get("finding_labels", "")).lower()
            or search in str(item.get("patient_id", "")).lower()
        ]
    total = len(items)
    start = (page_number - 1) * limit
    return response(200, {"scans": items[start:start + limit], "total": total, "page": page_number, "limit": limit})


def scan_detail(event, resources, engine):
    table = resources["table"]
    item = get_item(table, event["pathParameters"]["id"])
    if not item:
        return error(404, "SCAN_NOT_FOUND", "Scan not found")
    decision = engine.recommend(item, item.get("pathology_scores") or {}, size_bytes=int(item.get("object_size_bytes") or 1))
    audit = resources["audit"].query(
        KeyConditionExpression="scan_id = :scan_id",
        ExpressionAttributeValues={":scan_id": item["scan_id"]},
        ScanIndexForward=False,
        Limit=100,
    ).get("Items", [])
    return response(200, {**item, "audit_history": audit, **{key: decision[key] for key in ("cost_breakdown", "feature_contributions", "policy_version", "price_snapshot", "horizon_months")}})


def predict(event, resources, engine):
    if not may_mutate(event):
        return error(403, "FORBIDDEN", "archive-admin or operator membership is required")
    scan_id = event["pathParameters"]["id"]
    item = get_item(resources["table"], scan_id)
    if not item:
        return error(404, "SCAN_NOT_FOUND", "Scan not found")
    if not item.get("pathology_scores"):
        return error(409, "FEATURES_NOT_READY", "Pretrained pathology scores are required before cloud prediction")
    decision = engine.recommend(item, item["pathology_scores"], size_bytes=int(item.get("object_size_bytes") or 1))
    current_tier = item.get("current_tier") or "STANDARD"
    if TIER_RANK[decision["predicted_class"]] < TIER_RANK[current_tier] and current_tier in {"GLACIER", "DEEP_ARCHIVE"} and item.get("restore_status") != "COMPLETE":
        return error(409, "RESTORE_REQUIRED", "Restore the archived object before requesting a more accessible tier")
    merge_tier_tag(resources["s3"], item, decision["predicted_class"])
    now = datetime.now(timezone.utc).isoformat()
    resources["table"].update_item(
        Key={"scan_id": scan_id},
        UpdateExpression=(
            "SET predicted_class=:tier, requested_tier=:tier, probability=:prob, "
            "decision_reason=:reason, policy_version=:version, decision_status=:status, "
            "decision_timestamp=:time REMOVE override_reason"
        ),
        ExpressionAttributeValues={
            ":tier": decision["predicted_class"],
            ":prob": Decimal(str(decision["probability"])),
            ":reason": decision["reason"],
            ":version": decision["policy_version"],
            ":status": "PENDING_TRANSITION",
            ":time": now,
        },
    )
    write_audit(resources["audit"], event, scan_id, "PREDICTION_REQUESTED", {
        "tier": decision["predicted_class"], "policy_version": decision["policy_version"],
    })
    if TIER_RANK[decision["predicted_class"]] < TIER_RANK[current_tier]:
        resources["s3"].copy_object(
            Bucket=item["bucket_name"], Key=item["object_key"],
            CopySource={"Bucket": item["bucket_name"], "Key": item["object_key"]},
            StorageClass=decision["predicted_class"],
            MetadataDirective="COPY", TaggingDirective="COPY",
        )
    return response(200, {"scan_id": scan_id, "decision_status": "PENDING_TRANSITION", **decision})


def override(event, resources):
    if not may_mutate(event):
        return error(403, "FORBIDDEN", "archive-admin or operator membership is required")
    scan_id = event["pathParameters"]["id"]
    item = get_item(resources["table"], scan_id)
    if not item:
        return error(404, "SCAN_NOT_FOUND", "Scan not found")
    payload = body(event)
    tier = str(payload.get("tier", "")).upper()
    reason = str(payload.get("reason", "")).strip()
    if tier not in VALID_TIERS:
        return error(400, "INVALID_TIER", f"tier must be one of {VALID_TIERS}")
    if len(reason) < 3:
        return error(400, "OVERRIDE_REASON_REQUIRED", "A short override reason is required")
    current_tier = item.get("current_tier") or "STANDARD"
    moving_to_faster_tier = TIER_RANK[tier] < TIER_RANK[current_tier]
    if moving_to_faster_tier and current_tier in {"GLACIER", "DEEP_ARCHIVE"} and item.get("restore_status") != "COMPLETE":
        return error(409, "RESTORE_REQUIRED", "Restore the archived object before requesting a more accessible tier")
    merge_tier_tag(resources["s3"], item, tier)
    now = datetime.now(timezone.utc).isoformat()
    resources["table"].update_item(
        Key={"scan_id": scan_id},
        UpdateExpression="SET requested_tier=:tier, decision_status=:status, override_reason=:reason, decision_timestamp=:time",
        ExpressionAttributeValues={":tier": tier, ":status": "PENDING_TRANSITION", ":reason": reason, ":time": now},
    )
    write_audit(resources["audit"], event, scan_id, "TIER_OVERRIDE_REQUESTED", {"tier": tier, "reason": reason})
    if moving_to_faster_tier:
        resources["s3"].copy_object(
            Bucket=item["bucket_name"], Key=item["object_key"],
            CopySource={"Bucket": item["bucket_name"], "Key": item["object_key"]},
            StorageClass=tier, MetadataDirective="COPY", TaggingDirective="COPY",
        )
    return response(200, {"success": True, "scan_id": scan_id, "requested_tier": tier, "decision_status": "PENDING_TRANSITION"})


def restore(event, resources):
    if not may_mutate(event):
        return error(403, "FORBIDDEN", "archive-admin or operator membership is required")
    scan_id = event["pathParameters"]["id"]
    item = get_item(resources["table"], scan_id)
    if not item:
        return error(404, "SCAN_NOT_FOUND", "Scan not found")
    tier = item.get("current_tier") or "STANDARD"
    now = datetime.now(timezone.utc).isoformat()
    if tier in {"STANDARD", "STANDARD_IA"}:
        status = "NOT_REQUIRED"
    elif item.get("restore_status") == "PENDING":
        return response(202, {"scan_id": scan_id, "restore_status": "PENDING", "requested_at": item.get("restore_requested_at")})
    else:
        resources["s3"].restore_object(
            Bucket=item["bucket_name"], Key=item["object_key"],
            RestoreRequest={"Days": 1, "GlacierJobParameters": {"Tier": "Standard"}},
        )
        status = "PENDING"
    resources["table"].update_item(
        Key={"scan_id": scan_id},
        UpdateExpression="SET restore_status=:status, restore_requested_at=:time ADD access_count :one",
        ExpressionAttributeValues={":status": status, ":time": now, ":one": 1},
    )
    write_audit(resources["audit"], event, scan_id, "RESTORE_REQUESTED", {"tier": tier, "status": status})
    return response(202 if status == "PENDING" else 200, {"scan_id": scan_id, "restore_status": status, "requested_at": now})


def aggregate(resources, engine, costs=False, horizon=12):
    items = scan_all(resources["table"])
    tiers = {tier: 0 for tier in VALID_TIERS}
    monthly = 0.0
    wrongly = 0
    positives = 0
    policy_totals = {"All Standard": 0.0, "Simple Cold Rule": 0.0, "Standard-IA": 0.0, "Current Policy": 0.0}
    policy_wrong = {name: 0 for name in policy_totals}
    for item in items:
        size = int(item.get("object_size_bytes") or 1)
        probability = float(item.get("probability") or 0)
        current = item.get("current_tier") or item.get("predicted_class") or "STANDARD"
        tiers[current] = tiers.get(current, 0) + 1
        monthly += engine.cost_breakdown(current, probability, size, 12)["monetary_cost"] / 12
        positive = int(item.get("retrieved_again") or 0)
        positives += positive
        wrongly += int(positive and current in {"GLACIER", "DEEP_ARCHIVE"})
        cold = "GLACIER" if int(item.get("access_count") or 0) == 0 else "STANDARD_IA"
        mappings = {"All Standard": "STANDARD", "Simple Cold Rule": cold, "Standard-IA": "STANDARD_IA", "Current Policy": item.get("predicted_class") or "STANDARD"}
        for name, tier in mappings.items():
            policy_totals[name] += engine.cost_breakdown(tier, probability, size, horizon)["monetary_cost"]
            policy_wrong[name] += int(positive and tier in {"GLACIER", "DEEP_ARCHIVE"})
    if costs:
        policies = [{"name": name, "cost": round(total, 4), "wrongly_archived_rate": round(policy_wrong[name] / max(1, positives) * 100, 2)} for name, total in policy_totals.items()]
        standard, current = policy_totals["All Standard"], policy_totals["Current Policy"]
        return {"horizon": horizon, "policies": policies, "savings_pct": round((standard-current)/max(standard, 1e-12)*100, 2), "total_scans": len(items), "currency": "USD", "scope": "simulation", "policy_version": engine.version}
    colors = {"STANDARD": "#10B981", "STANDARD_IA": "#3B82F6", "GLACIER": "#F59E0B", "DEEP_ARCHIVE": "#EF4444"}
    return {"total_scans": len(items), "tier_distribution": [{"name": tier.replace("_", "-").title(), "value": tiers[tier], "color": colors[tier]} for tier in VALID_TIERS], "tier_distribution_dict": tiers, "projected_monthly_cost": round(monthly, 4), "wrongly_archived_count": wrongly, "wrongly_archived_rate": round(wrongly/max(1, positives)*100, 2), "mode": "AWS DynamoDB", "policy_version": engine.version}


def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    if method == "OPTIONS":
        return response(200, {})
    resources, engine = _resources(), _engine()
    try:
        if resource == "/api/scans" and method == "GET":
            return list_scans(event, resources["table"])
        if resource == "/api/scans/{id}" and method == "GET":
            return scan_detail(event, resources, engine)
        if resource == "/api/scans/{id}/predict" and method == "POST":
            return predict(event, resources, engine)
        if resource == "/api/scans/{id}/tier" and method == "POST":
            return override(event, resources)
        if resource == "/api/scans/{id}/restore" and method == "POST":
            return restore(event, resources)
        if resource == "/api/dashboard/summary" and method == "GET":
            return response(200, aggregate(resources, engine))
        if resource == "/api/costs" and method == "GET":
            params = event.get("queryStringParameters") or {}
            horizon = float(params.get("horizon", 12))
            if not 0 < horizon <= 120:
                return error(400, "INVALID_HORIZON", "horizon must be between 0 and 120")
            return response(200, aggregate(resources, engine, costs=True, horizon=horizon))
        return error(404, "NOT_FOUND", "Endpoint not found")
    except ValueError as exc:
        return error(400, "INVALID_REQUEST", str(exc))
    except Exception:
        logger.exception("API request failed")
        return error(500, "INTERNAL_ERROR", "Internal server error")
