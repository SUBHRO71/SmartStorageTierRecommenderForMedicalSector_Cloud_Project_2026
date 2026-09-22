"""Local REST API with the same response contract as the AWS API Lambda."""

from __future__ import annotations

import os
import sys
import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))
from db import VALID_TIERS, db  # noqa: E402
from model_service import model_service  # noqa: E402

app = Flask(__name__)
allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins}},
)


def error_response(status, code, message):
    return jsonify({"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}}), status


@app.errorhandler(404)
def not_found(_error):
    return error_response(404, "NOT_FOUND", "Endpoint not found")


@app.errorhandler(Exception)
def unhandled(error):
    app.logger.exception("Unhandled API error")
    return error_response(500, "INTERNAL_ERROR", str(error) if app.debug else "Internal server error")


@app.get("/api/health")
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "service": "Smart Storage Tier Recommender Backend",
            "mode": "AWS DynamoDB" if db.use_aws else "Local SQLite",
            "auth_mode": os.environ.get("AUTH_MODE", "local"),
            "inference_mode": "pretrained-weights-and-fixed-policy",
            "policy_version": model_service.engine.version,
        }
    )


@app.get("/api/scans")
def get_scans():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))
    except ValueError:
        return error_response(400, "INVALID_PAGINATION", "page and limit must be integers")
    if page < 1 or limit < 1 or limit > 100:
        return error_response(400, "INVALID_PAGINATION", "page must be >= 1 and limit must be 1..100")
    tier = request.args.get("tier")
    if tier and tier.upper() not in {*VALID_TIERS, "ALL"}:
        return error_response(400, "INVALID_TIER", f"tier must be one of {VALID_TIERS}")
    return jsonify(db.get_scans(page, limit, tier, request.args.get("search")))


@app.get("/api/scans/<path:scan_id>")
def get_scan(scan_id):
    scan = db.get_scan(scan_id)
    if not scan:
        return error_response(404, "SCAN_NOT_FOUND", f"Scan {scan_id} was not found")
    prediction = model_service.predict_scan(scan)
    scan.update(
        {
            "cost_breakdown": prediction["cost_breakdown"],
            "feature_contributions": prediction["feature_contributions"],
            "policy_version": prediction["policy_version"],
            "price_snapshot": prediction["price_snapshot"],
            "horizon_months": prediction["horizon_months"],
            "audit_history": db.get_audit_events(scan_id),
        }
    )
    return jsonify(scan)


@app.post("/api/scans/<path:scan_id>/predict")
def predict_scan(scan_id):
    scan = db.get_scan(scan_id)
    if not scan:
        return error_response(404, "SCAN_NOT_FOUND", f"Scan {scan_id} was not found")
    prediction = model_service.predict_scan(scan)
    if not db.update_prediction(scan_id, prediction):
        return error_response(409, "PREDICTION_NOT_SAVED", "Prediction could not be persisted")
    updated = db.get_scan(scan_id) or {}
    return jsonify(
        {
            "scan_id": scan_id,
            "current_tier": updated.get("current_tier"),
            "requested_tier": updated.get("requested_tier"),
            "decision_status": updated.get("decision_status"),
            **prediction,
        }
    )


@app.post("/api/scans/<path:scan_id>/tier")
def override_tier(scan_id):
    scan = db.get_scan(scan_id)
    if not scan:
        return error_response(404, "SCAN_NOT_FOUND", f"Scan {scan_id} was not found")
    payload = request.get_json(silent=True) or {}
    tier = str(payload.get("tier", "")).upper()
    reason = str(payload.get("reason", "")).strip()
    if tier not in VALID_TIERS:
        return error_response(400, "INVALID_TIER", f"tier must be one of {VALID_TIERS}")
    if len(reason) < 3:
        return error_response(400, "OVERRIDE_REASON_REQUIRED", "A short override reason is required")
    previous = scan.get("current_tier") or "STANDARD"
    status = db.override_tier(scan_id, tier, reason)
    return jsonify(
        {
            "success": True,
            "scan_id": scan_id,
            "previous_tier": previous,
            "requested_tier": tier,
            "current_tier": tier if status == "APPLIED_LOCAL" else previous,
            "decision_status": status,
            "override_reason": reason,
        }
    )


@app.post("/api/scans/<path:scan_id>/restore")
def restore_scan(scan_id):
    result = db.request_restore(scan_id)
    if not result:
        return error_response(404, "SCAN_NOT_FOUND", f"Scan {scan_id} was not found")
    return jsonify(result), 202 if result["restore_status"] == "PENDING" else 200


@app.get("/api/costs")
def get_costs():
    try:
        horizon = float(request.args.get("horizon", 12))
    except ValueError:
        return error_response(400, "INVALID_HORIZON", "horizon must be a number")
    if horizon <= 0 or horizon > 120:
        return error_response(400, "INVALID_HORIZON", "horizon must be between 0 and 120 months")
    return jsonify(db.get_cost_comparison(horizon))


@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    summary = db.get_summary()
    distribution = summary["tier_distribution"]
    colors = {
        "STANDARD": "#10B981",
        "STANDARD_IA": "#3B82F6",
        "GLACIER": "#F59E0B",
        "DEEP_ARCHIVE": "#EF4444",
    }
    summary["tier_distribution_dict"] = distribution
    summary["tier_distribution"] = [
        {"name": tier.replace("_", "-").title(), "value": distribution.get(tier, 0), "color": color}
        for tier, color in colors.items()
    ]
    summary["policy_version"] = model_service.engine.version
    return jsonify(summary)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
