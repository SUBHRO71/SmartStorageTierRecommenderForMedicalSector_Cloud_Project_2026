"""Persistence adapters for the local demo and optional DynamoDB execution."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ML_DIR = PROJECT_ROOT / "src" / "ml_model"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from decision_engine import DecisionEngine  # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "ScanFeatures")
LOCAL_DB_PATH = Path(os.environ.get("LOCAL_DB_PATH", Path(__file__).with_name("local_scans.db")))
VALID_TIERS = ("STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


class DatabaseClient:
    """Use SQLite by default; enable DynamoDB explicitly with DATA_BACKEND=dynamodb."""

    def __init__(self):
        self.backend = os.environ.get("DATA_BACKEND", "sqlite").lower()
        self.use_aws = self.backend == "dynamodb"
        self.table = None
        self.engine = DecisionEngine()
        if self.use_aws:
            import boto3

            self.table = boto3.resource(
                "dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            ).Table(TABLE_NAME)
            self.table.load()
        elif self.backend == "sqlite":
            self._init_local_db()
        else:
            raise ValueError("DATA_BACKEND must be 'sqlite' or 'dynamodb'")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(LOCAL_DB_PATH)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_local_db(self):
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    patient_id INTEGER,
                    patient_age INTEGER,
                    patient_gender TEXT,
                    view_position TEXT,
                    follow_up_number INTEGER,
                    finding_labels TEXT,
                    pathology_scores TEXT DEFAULT '{}',
                    object_size_bytes INTEGER NOT NULL,
                    current_tier TEXT NOT NULL DEFAULT 'STANDARD',
                    requested_tier TEXT,
                    predicted_class TEXT,
                    probability REAL,
                    reason TEXT,
                    policy_version TEXT,
                    decision_status TEXT NOT NULL DEFAULT 'READY',
                    decision_timestamp TEXT,
                    last_accessed TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    retrieved_again INTEGER NOT NULL DEFAULT 0,
                    override_reason TEXT,
                    restore_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED',
                    restore_requested_at TEXT,
                    restore_completed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_scan_time ON audit_events(scan_id, created_at DESC)"
            )
            existing = {row[1] for row in connection.execute("PRAGMA table_info(scans)")}
            migrations = {
                "pathology_scores": "TEXT DEFAULT '{}'",
                "requested_tier": "TEXT",
                "policy_version": "TEXT",
                "decision_status": "TEXT NOT NULL DEFAULT 'READY'",
                "decision_timestamp": "TEXT",
                "override_reason": "TEXT",
                "restore_status": "TEXT NOT NULL DEFAULT 'NOT_REQUESTED'",
                "restore_requested_at": "TEXT",
                "restore_completed_at": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE scans ADD COLUMN {column} {definition}")
            count = connection.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            if count == 0:
                self._seed_local_db(connection)
            self._refresh_local_policy(connection)

    def _refresh_local_policy(self, connection):
        """Keep seeded demo rows consistent with the checked-in policy artifact."""
        rows = connection.execute(
            """SELECT * FROM scans WHERE policy_version IS NULL OR policy_version != ?
               OR (override_reason IS NULL AND NOT EXISTS (
                   SELECT 1 FROM audit_events WHERE audit_events.scan_id = scans.scan_id
               ))""",
            (self.engine.version,),
        ).fetchall()
        for row in rows:
            item = self._row_to_dict(row)
            decision = self.engine.recommend(
                item, item.get("pathology_scores") or {}, int(item.get("object_size_bytes") or 1)
            )
            connection.execute(
                """
                UPDATE scans SET predicted_class=?, probability=?, reason=?, policy_version=?,
                    requested_tier=CASE WHEN override_reason IS NULL THEN ? ELSE requested_tier END,
                    current_tier=CASE WHEN override_reason IS NULL THEN ? ELSE current_tier END,
                    decision_status=CASE WHEN override_reason IS NULL THEN 'APPLIED_LOCAL' ELSE decision_status END,
                    decision_timestamp=CASE WHEN override_reason IS NULL THEN ? ELSE decision_timestamp END
                WHERE scan_id=?
                """,
                (
                    decision["predicted_class"], decision["probability"], decision["reason"],
                    decision["policy_version"], decision["predicted_class"],
                    decision["predicted_class"], _now(), item["scan_id"],
                ),
            )

    def _source_rows(self):
        for candidate in (
            PROJECT_ROOT / "dataset" / "processed" / "features.csv",
            PROJECT_ROOT / "dataset" / "processed" / "sample.csv",
        ):
            if candidate.exists():
                with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
                    return list(csv.DictReader(handle))[:250]
        return [
            {
                "Image Index": f"demo-{patient:03d}-{follow_up:02d}.png",
                "Patient ID": patient,
                "Patient Age": 32 + patient,
                "Patient Gender": "M" if patient % 2 == 0 else "F",
                "View Position": "PA" if follow_up % 2 == 0 else "AP",
                "Follow-up #": follow_up,
                "Finding Labels": "Effusion" if patient % 3 == 0 else "No Finding",
                "retrieved_again": int(follow_up == 0),
            }
            for patient in range(1, 25)
            for follow_up in range(3)
        ]

    def _seed_local_db(self, connection):
        for row in self._source_rows():
            metadata = {
                "patient_age": int(float(row.get("Patient Age") or 50)),
                "follow_up_number": int(float(row.get("Follow-up #") or 0)),
                "finding_labels": str(row.get("Finding Labels") or "No Finding"),
                "access_count": int(float(row.get("Follow-up #") or 0)),
            }
            size_bytes = 15 * 1024 * 1024
            decision = self.engine.recommend(metadata, size_bytes=size_bytes)
            connection.execute(
                """
                INSERT INTO scans (
                    scan_id, patient_id, patient_age, patient_gender, view_position,
                    follow_up_number, finding_labels, object_size_bytes, current_tier,
                    requested_tier, predicted_class, probability, reason, policy_version,
                    decision_status, decision_timestamp, last_accessed, access_count,
                    retrieved_again
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row.get("Image Index") or "unknown.png"),
                    int(float(row.get("Patient ID") or 0)),
                    metadata["patient_age"],
                    str(row.get("Patient Gender") or "U"),
                    str(row.get("View Position") or "UNKNOWN"),
                    metadata["follow_up_number"],
                    metadata["finding_labels"],
                    size_bytes,
                    decision["predicted_class"],
                    decision["predicted_class"],
                    decision["predicted_class"],
                    decision["probability"],
                    decision["reason"],
                    decision["policy_version"],
                    "APPLIED_LOCAL",
                    _now(),
                    _now(),
                    metadata["access_count"],
                    int(float(row.get("retrieved_again") or 0)),
                ),
            )

    @staticmethod
    def _row_to_dict(row):
        item = dict(row)
        raw_scores = item.get("pathology_scores")
        if isinstance(raw_scores, str):
            try:
                item["pathology_scores"] = json.loads(raw_scores)
            except json.JSONDecodeError:
                item["pathology_scores"] = {}
        return item

    def get_scans(self, page=1, limit=20, tier=None, search=None):
        page = max(1, int(page))
        limit = min(100, max(1, int(limit)))
        if self.use_aws:
            response = self.table.scan()
            items = [_json_value(item) for item in response.get("Items", [])]
            if tier and tier.upper() != "ALL":
                items = [item for item in items if item.get("predicted_class") == tier.upper()]
            if search:
                needle = search.lower()
                items = [
                    item for item in items
                    if needle in str(item.get("scan_id", "")).lower()
                    or needle in str(item.get("finding_labels", "")).lower()
                    or needle in str(item.get("patient_id", "")).lower()
                ]
            start = (page - 1) * limit
            return {"scans": items[start:start + limit], "total": len(items), "page": page, "limit": limit}

        clauses = []
        params = []
        if tier and tier.upper() != "ALL":
            clauses.append("(predicted_class = ? OR current_tier = ?)")
            params.extend([tier.upper(), tier.upper()])
        if search:
            clauses.append("(scan_id LIKE ? OR finding_labels LIKE ? OR CAST(patient_id AS TEXT) LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM scans{where}", params).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM scans{where} ORDER BY decision_timestamp DESC, scan_id LIMIT ? OFFSET ?",
                [*params, limit, (page - 1) * limit],
            ).fetchall()
        return {"scans": [self._row_to_dict(row) for row in rows], "total": total, "page": page, "limit": limit}

    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        if self.use_aws:
            return _json_value(self.table.get_item(Key={"scan_id": scan_id}).get("Item"))
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_audit_events(self, scan_id: str):
        if self.use_aws:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE scan_id=? ORDER BY created_at DESC LIMIT 100",
                (scan_id,),
            ).fetchall()
        events = []
        for row in rows:
            event = dict(row)
            event["details"] = json.loads(event["details"] or "{}")
            events.append(event)
        return events

    def _record_local_event(self, connection, scan_id, event_type, details):
        connection.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), scan_id, event_type, "local-user", _now(),
                json.dumps(details, sort_keys=True),
            ),
        )

    def _all_scans(self):
        if self.use_aws:
            items = []
            request = {}
            while True:
                response = self.table.scan(**request)
                items.extend(_json_value(item) for item in response.get("Items", []))
                key = response.get("LastEvaluatedKey")
                if not key:
                    return items
                request["ExclusiveStartKey"] = key
        with self._connect() as connection:
            return [self._row_to_dict(row) for row in connection.execute("SELECT * FROM scans")]

    def update_prediction(self, scan_id, prediction):
        timestamp = _now()
        if self.use_aws:
            self.table.update_item(
                Key={"scan_id": scan_id},
                UpdateExpression=(
                    "SET predicted_class=:tier, requested_tier=:tier, probability=:prob, "
                    "decision_reason=:reason, policy_version=:version, "
                    "decision_status=:status, decision_timestamp=:time"
                ),
                ExpressionAttributeValues={
                    ":tier": prediction["predicted_class"],
                    ":prob": Decimal(str(prediction["probability"])),
                    ":reason": prediction["reason"],
                    ":version": prediction["policy_version"],
                    ":status": "PENDING_TRANSITION",
                    ":time": timestamp,
                },
            )
            return True
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE scans SET predicted_class=?, requested_tier=?, current_tier=?,
                    probability=?, reason=?, policy_version=?, decision_status='APPLIED_LOCAL',
                    decision_timestamp=? WHERE scan_id=?
                """,
                (
                    prediction["predicted_class"], prediction["predicted_class"],
                    prediction["predicted_class"], prediction["probability"],
                    prediction["reason"], prediction["policy_version"], timestamp, scan_id,
                ),
            )
            if cursor.rowcount:
                self._record_local_event(
                    connection, scan_id, "PREDICTION_APPLIED",
                    {"tier": prediction["predicted_class"], "policy_version": prediction["policy_version"]},
                )
        return cursor.rowcount > 0

    def override_tier(self, scan_id, tier, reason):
        timestamp = _now()
        if self.use_aws:
            self.table.update_item(
                Key={"scan_id": scan_id},
                UpdateExpression=(
                    "SET requested_tier=:tier, decision_status=:status, override_reason=:reason, "
                    "decision_timestamp=:time"
                ),
                ExpressionAttributeValues={
                    ":tier": tier, ":status": "PENDING_TRANSITION",
                    ":reason": reason, ":time": timestamp,
                },
            )
            return "PENDING_TRANSITION"
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE scans SET requested_tier=?, current_tier=?, decision_status='APPLIED_LOCAL',
                    override_reason=?, decision_timestamp=? WHERE scan_id=?""",
                (tier, tier, reason, timestamp, scan_id),
            )
            if cursor.rowcount:
                self._record_local_event(
                    connection, scan_id, "TIER_OVERRIDE_APPLIED", {"tier": tier, "reason": reason},
                )
        return "APPLIED_LOCAL"

    def request_restore(self, scan_id):
        item = self.get_scan(scan_id)
        if not item:
            return None
        tier = item.get("current_tier") or "STANDARD"
        requested = _now()
        status = "NOT_REQUIRED" if tier in {"STANDARD", "STANDARD_IA"} else "COMPLETE_LOCAL"
        completed = requested if status != "PENDING" else None
        if self.use_aws:
            status = "PENDING"
            completed = None
            # The API Lambda performs the S3 restore call before persisting this state.
        else:
            with self._connect() as connection:
                cursor = connection.execute(
                    """UPDATE scans SET restore_status=?, restore_requested_at=?,
                        restore_completed_at=?, access_count=access_count+1, last_accessed=?
                        WHERE scan_id=?""",
                    (status, requested, completed, requested, scan_id),
                )
                if cursor.rowcount:
                    self._record_local_event(
                        connection, scan_id, "RESTORE_REQUESTED", {"status": status, "tier": tier},
                    )
        return {"scan_id": scan_id, "restore_status": status, "requested_at": requested, "completed_at": completed}

    def get_summary(self):
        scans = self._all_scans()
        distribution = {tier: 0 for tier in VALID_TIERS}
        monthly = 0.0
        wrongly_archived = 0
        positives = 0
        for scan in scans:
            tier = scan.get("current_tier") or "STANDARD"
            distribution[tier] = distribution.get(tier, 0) + 1
            probability = float(scan.get("probability") or 0)
            costs = self.engine.cost_breakdown(
                tier, probability, int(scan.get("object_size_bytes") or 1), horizon_months=12
            )
            monthly += costs["monetary_cost"] / 12
            if int(scan.get("retrieved_again") or 0):
                positives += 1
                if tier in {"GLACIER", "DEEP_ARCHIVE"}:
                    wrongly_archived += 1
        return {
            "total_scans": len(scans),
            "tier_distribution": distribution,
            "projected_monthly_cost": round(monthly, 4),
            "wrongly_archived_count": wrongly_archived,
            "wrongly_archived_rate": round(wrongly_archived / max(1, positives) * 100, 2),
            "mode": "AWS DynamoDB" if self.use_aws else "Local SQLite",
        }

    def get_cost_comparison(self, horizon_months=12):
        scans = self._all_scans()
        totals = {"All Standard": 0.0, "Simple Cold Rule": 0.0, "Standard-IA": 0.0, "Current Policy": 0.0}
        wrong = {name: 0 for name in totals}
        positives = sum(int(scan.get("retrieved_again") or 0) for scan in scans)
        for scan in scans:
            size = int(scan.get("object_size_bytes") or 1)
            probability = float(scan.get("probability") or 0)
            current = scan.get("predicted_class") or "STANDARD"
            cold = "GLACIER" if int(scan.get("access_count") or 0) == 0 else "STANDARD_IA"
            mapping = {
                "All Standard": "STANDARD", "Simple Cold Rule": cold,
                "Standard-IA": "STANDARD_IA", "Current Policy": current,
            }
            for name, tier in mapping.items():
                totals[name] += self.engine.cost_breakdown(
                    tier, probability, size, horizon_months
                )["monetary_cost"]
                if int(scan.get("retrieved_again") or 0) and tier in {"GLACIER", "DEEP_ARCHIVE"}:
                    wrong[name] += 1
        policies = [
            {
                "name": name,
                "cost": round(cost, 4),
                "wrongly_archived_rate": round(wrong[name] / max(1, positives) * 100, 2),
            }
            for name, cost in totals.items()
        ]
        standard = totals["All Standard"]
        current = totals["Current Policy"]
        return {
            "horizon": horizon_months,
            "policies": policies,
            "savings_pct": round((standard - current) / max(standard, 1e-12) * 100, 2),
            "total_scans": len(scans),
            "currency": "USD",
            "scope": "simulation",
            "policy_version": self.engine.version,
        }


db = DatabaseClient()
