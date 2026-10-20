"""Study archive for the explicit local v2 research workflow.

Sample metadata is created only by a user-requested demo import. Clinical joins
are exact; image inference is never fabricated. Cloud v2 is intentionally gated.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("T1", "T1ce", "T2", "FLAIR")
TIERS = ("STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE")


def now():
    return datetime.now(timezone.utc).isoformat()


def policy(study, horizon=12, accesses=1, *, use_forecast=True):
    """Compare per-object monetary costs, after explicit access constraints.

    Uses the existing checked-in engineering snapshot, not current AWS prices.
    Workload is declared, or explicitly enabled as an experimental first-event
    visit proxy. A next-visit probability is not a general retrieval count.
    """
    if not math.isfinite(horizon) or not 0 < horizon <= 120:
        raise ValueError("Horizon must be between 0 and 120 months")
    if not math.isfinite(accesses) or not 0 <= accesses <= 1000:
        raise ValueError("Expected study accesses must be between 0 and 1000")
    forecast = study.get("forecast", {})
    proxy = use_forecast and forecast.get("storage_scenario_enabled", False)
    if proxy:
        horizon, accesses = 3, forecast["probability_90d"]
    prices = json.loads((ROOT / "src/ml_model/retrieval_policy_weights.json").read_text())["price_snapshot"]
    protection = study["access"]
    reasons = []
    allowed = list(TIERS)
    if protection["hold"] or protection["active"]:
        allowed = ["STANDARD"]
        reasons.append("An active-use window or manual hold keeps the complete study in Standard.")
    elif protection["max_hours"] is None:
        allowed = ["STANDARD"]
        reasons.append("Declare the required access time before requesting colder storage.")
    else:
        if protection["max_hours"] < 48:
            allowed.remove("DEEP_ARCHIVE")
        if protection["max_hours"] < 12:
            allowed.remove("GLACIER")
        if study.get("age_days", 0) < 30:
            allowed = [tier for tier in allowed if tier != "STANDARD_IA"]
            reasons.append("Standard-IA requires the configured 30-day object-age boundary.")
    if not study["complete"] or study["clinical"]["status"] != "VERIFIED":
        allowed = ["STANDARD"]
        reasons.append("Resolve missing sequences or clinical linkage before automatic cold placement.")
    if study["analysis"]["status"] in ("FAILED", "RUNNING"):
        allowed = ["STANDARD"]
        reasons.append("Review the failed or unfinished analysis before automatic cold placement.")
    if any(obj["bytes"] < 131072 for obj in study["objects"]):
        allowed = ["STANDARD"]
        reasons.append("The bundle contains an object below the default Lifecycle transition size.")
    if proxy:
        reasons.append("Experimental 90-day scenario: one possible complete-bundle access at the next recorded visit; its probability weights retrieval cost.")
        if forecast["probability_30d"] >= .5:
            allowed = ["STANDARD"]
            reasons.append("At least 50% modeled probability of a recorded visit within 30 days keeps this pilot bundle in Standard.")
    candidates = []
    for tier in TIERS:
        settings = prices["tiers"][tier]
        months = max(horizon, settings["minimum_duration_days"] / 30)
        storage = transition = retrieval = metadata = 0.0
        for obj in study["objects"]:
            size = obj["bytes"]
            storage += max(size, settings["minimum_billable_bytes"]) / (1024 ** 3) * settings["storage_gb_month"] * months
            if obj["tier"] != tier:
                transition += settings["transition_1000_requests"] / 1000
            retrieval += accesses * (size / (1024 ** 3) * settings["retrieval_gb"] + settings["retrieval_1000_requests"] / 1000)
            if settings["archive_metadata_bytes"]:
                metadata += months * (8192 / (1024 ** 3) * prices["tiers"]["STANDARD"]["storage_gb_month"] + 32768 / (1024 ** 3) * settings["storage_gb_month"])
        # Scenario assumption: each archive access retains a temporary Standard copy for one day.
        temporary = accesses * sum(o["bytes"] for o in study["objects"]) / (1024 ** 3) * prices["tiers"]["STANDARD"]["storage_gb_month"] / 30 if tier in TIERS[2:] else 0
        candidates.append({"tier": tier, "eligible": tier in allowed, "storage": storage,
                           "transition": transition, "retrieval": retrieval, "metadata": metadata,
                           "temporary": temporary, "cost": storage + transition + retrieval + metadata + temporary})
    chosen = min((c for c in candidates if c["eligible"]), key=lambda c: c["cost"])["tier"]
    if not reasons:
        reasons.append("Lowest modeled monetary cost among tiers compatible with the declared access time.")
    return {"tier": chosen, "reason": " ".join(reasons), "candidates": candidates,
            "version": "study-policy-v2.2", "horizon": horizon, "accesses": accesses,
            "price_snapshot": {k: prices[k] for k in ("currency", "region", "reviewed_on")},
            "scope": "experimental first-event visit proxy" if proxy else "declared workload simulation",
            "forecast_model": forecast.get("model_id") if proxy else None,
            "limitations": ("Assumes the next recorded visit causes exactly one bundle retrieval; additional retrievals are unmodeled. " if proxy else "") + "Engineering snapshot; excludes prior-tier exit charges, egress, compute, hot previews and other service overhead. Not an AWS bill."}


class Archive:
    def __init__(self, path=None, data_dir=None):
        self.path = Path(path or os.environ.get("ARCHIVE_DB_PATH", Path(__file__).with_name("archive.db")))
        self.data_dir = Path(data_dir or os.environ.get("ARCHIVE_DATA_DIR", ROOT / "dataset/processed/archive"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS archive_studies (id TEXT PRIMARY KEY, record TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS archive_events (id TEXT PRIMARY KEY, study_id TEXT NOT NULL, kind TEXT NOT NULL, created TEXT NOT NULL, details TEXT NOT NULL)")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def studies(self):
        with self.connection() as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT record FROM archive_studies ORDER BY id")]

    def get(self, study_id):
        with self.connection() as conn:
            row = conn.execute("SELECT record FROM archive_studies WHERE id=?", (study_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def save(self, study, kind, details="", expected_version=None):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute("SELECT record FROM archive_studies WHERE id=?", (study["id"],)).fetchone()
            version = json.loads(prior[0])["version"] if prior else 0
            if expected_version is not None and expected_version != version:
                raise ValueError("The study changed. Refresh it before submitting this action.")
            study["version"] = version + 1
            study["updated"] = now()
            conn.execute("INSERT OR REPLACE INTO archive_studies VALUES (?,?)", (study["id"], json.dumps(study)))
            from flask import g, has_app_context
            actor = getattr(g, "actor", "local") if has_app_context() else "system"
            conn.execute("INSERT INTO archive_events VALUES (?,?,?,?,?)", (str(uuid.uuid4()), study["id"], kind, now(), json.dumps({"message": details, "mode": getattr(self, "mode", "LOCAL"), "actor": actor, "version": study["version"]})))
        return study

    def events(self, study_id=None):
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM archive_events WHERE (? IS NULL OR study_id=?) ORDER BY created DESC LIMIT 100", (study_id, study_id)).fetchall()
            return [{**dict(row), "details": json.loads(row["details"])} for row in rows]

    def finish_analysis(self, identifier, result):
        """Merge worker output atomically without overwriting concurrent access edits."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT record FROM archive_studies WHERE id=?", (identifier,)).fetchone()
            if not row:
                return
            study = json.loads(row[0])
            study["analysis"] = result
            study["version"] += 1
            study["updated"] = now()
            previous = study["decision"]
            study["decision"] = policy(study, previous["horizon"], previous["accesses"])
            conn.execute("UPDATE archive_studies SET record=? WHERE id=?", (json.dumps(study), identifier))
            conn.execute("INSERT INTO archive_events VALUES (?,?,?,?,?)", (str(uuid.uuid4()),identifier,"ANALYSIS_"+result["status"],now(),json.dumps({"message":result.get("message","Model output saved"),"mode":getattr(self,"mode","LOCAL"),"actor":"worker","version":study["version"]})))

    def recover_interrupted_analysis(self):
        for study in self.studies():
            if study["analysis"]["status"] == "RUNNING":
                self.finish_analysis(study["id"], {"status":"FAILED","model":study["analysis"]["model"],"message":"The backend restarted during analysis. Verify the inputs and retry."})

    def demo(self):
        loaded = 0
        for index in range(1, 13):
            identifier = f"DEMO-{index:03d}"
            if self.get(identifier):
                continue
            sequences = [r for r in ROLES if not (index in (4, 9) and r == "FLAIR")]
            tier = TIERS[(index - 1) % 4] if index not in (4, 9) else "STANDARD"
            objects = [{"id": f"{identifier}-{role}", "role": role, "bytes": (26 + index * 3 + j * 5) * 1024 ** 2,
                        "tier": tier, "format": "NIfTI", "sha256": None, "file": None, "geometry": None}
                       for j, role in enumerate(sequences)]
            record = {"id": identifier, "subject": f"SAMPLE-{index:03d}", "collection": "Demonstration cohort",
                      "release": "Synthetic v2 fixture", "license": "Synthetic metadata — no patient images",
                      "source": "SYNTHETIC", "source_url": None, "modality": "MR", "age_days": 40 + index * 30,
                      "objects": objects, "sequences": sequences, "complete": len(sequences) == 4,
                      "clinical": {"status": "UNMATCHED" if index == 7 else "VERIFIED", "provenance": "Synthetic demonstration record",
                                   "fields": {} if index == 7 else {"diagnosis": "Diffuse glioma (synthetic)", "age": 28 + index * 3, "sex": "F" if index % 2 else "M", "grade": 4 if index % 3 else 3}},
                      "access": {"hold": index in (1, 4), "active": index in (1, 2), "max_hours": 0 if index in (1, 2) else 48},
                      "analysis": {"status": "NOT_RUN", "model": "MONAI BraTS SegResNet 0.5.4", "message": "No MRI pixels in the sample cohort. Import permitted volumes to run analysis."},
                      "requested_tier": tier, "restore": "NOT_REQUESTED", "version": 0}
            record["decision"] = policy(record)
            self.save(record, "SAMPLE_IMPORTED", "User-requested synthetic cohort. No real patient images or clinical records.")
            loaded += 1
        return loaded

    def summary(self, studies=None):
        studies = self.studies() if studies is None else studies
        distribution = {tier: {"tier": tier, "bytes": 0, "objects": 0} for tier in TIERS}
        issues = []
        for study in studies:
            for obj in study["objects"]:
                distribution[obj["tier"]]["bytes"] += obj["bytes"]
                distribution[obj["tier"]]["objects"] += 1
            for condition, code, title in [
                (not study["complete"], "sequence", "Missing MRI sequence"),
                (study["clinical"]["status"] != "VERIFIED", "clinical", "Clinical record needs linkage"),
                (study["analysis"]["status"] == "FAILED", "analysis", "MRI analysis failed"),
                (study["access"]["hold"], "hold", "Manual hot-storage hold"),
            ]:
                if condition:
                    issues.append({"study_id": study["id"], "title": title, "kind": code})
        return {"studies": len(studies), "bytes": sum(o["bytes"] for s in studies for o in s["objects"]),
                "objects": sum(len(s["objects"]) for s in studies), "complete": sum(s["complete"] for s in studies),
                "clinical": sum(s["clinical"]["status"] == "VERIFIED" for s in studies),
                "distribution": list(distribution.values()), "issues": issues,
                "protected": sum(s["access"]["hold"] or s["access"]["active"] for s in studies),
                "synthetic": sum(s["source"] == "SYNTHETIC" for s in studies), "updated": now()}

    def import_study(self, form, files):
        subject = str(form.get("subject", "")).strip()
        collection = str(form.get("collection", "")).strip()
        license_name = str(form.get("license", "")).strip()
        if not subject or not collection or not license_name:
            raise ValueError("Source subject ID, collection and permission/license are required")
        if any(len(value) > 200 for value in (subject, collection, license_name)):
            raise ValueError("Source fields must be at most 200 characters")
        identifier = "ST-" + uuid.uuid4().hex[:12].upper()
        objects = []
        sequences = []
        directory = self.data_dir / identifier
        try:
            for role in ROLES:
                uploads = files.getlist(role)
                if not uploads:
                    continue
                sequences.append(role)
                series_uid = None
                for upload in uploads:
                    name = upload.filename.lower()
                    suffix = ".nii.gz" if name.endswith(".nii.gz") else ".nii" if name.endswith(".nii") else ".dcm" if name.endswith(".dcm") else None
                    if not suffix:
                        raise ValueError("Only NIfTI (.nii/.nii.gz) and DICOM (.dcm) are supported")
                    directory.mkdir(parents=True, exist_ok=True)
                    destination = directory / (uuid.uuid4().hex + suffix)
                    upload.save(destination)
                    if destination.stat().st_size == 0:
                        raise ValueError("An uploaded imaging file is empty")
                    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
                    geometry = {}
                    if suffix == ".dcm":
                        import pydicom
                        ds = pydicom.dcmread(destination, stop_before_pixels=True)
                        if str(ds.get("PatientID", "")) != subject:
                            raise ValueError("DICOM PatientID must exactly match the declared source subject ID")
                        if str(ds.get("Modality", "")) != "MR":
                            raise ValueError("The four-sequence MRI importer accepts MR DICOM only")
                        uid = str(ds.get("SeriesInstanceUID", ""))
                        if not uid or (series_uid and series_uid != uid):
                            raise ValueError("Each sequence input must contain one identified DICOM series")
                        series_uid = uid
                        geometry = {"rows": int(ds.get("Rows", 0)), "columns": int(ds.get("Columns", 0)),
                                    "study_uid": str(ds.get("StudyInstanceUID", "")), "series_uid": uid,
                                    "spacing": [float(v) for v in ds.get("PixelSpacing", [])]}
                    else:
                        import nibabel as nib
                        image = nib.load(destination)
                        if len(image.shape) != 3 or min(image.shape) < 2:
                            raise ValueError("Each MRI sequence must be a three-dimensional volume")
                        if max(image.shape) > 512 or math.prod(image.shape) > 256 ** 3:
                            raise ValueError("The local importer accepts up to 256 cubed voxels and 512 per axis")
                        geometry = {"shape": list(image.shape), "spacing": [float(v) for v in image.header.get_zooms()[:3]], "affine": image.affine.tolist()}
                        if len(uploads) != 1:
                            raise ValueError("Use exactly one NIfTI volume per MRI sequence")
                    objects.append({"id": destination.stem, "role": role, "bytes": destination.stat().st_size,
                                    "tier": "STANDARD", "format": "DICOM" if suffix == ".dcm" else "NIfTI",
                                    "file": str(destination.resolve()), "sha256": checksum, "geometry": geometry})
            if not objects:
                raise ValueError("Choose at least one imaging file")
            study_uids = {o["geometry"].get("study_uid") for o in objects if o["format"] == "DICOM"}
            if len(study_uids) > 1 or "" in study_uids:
                raise ValueError("DICOM series must belong to the same identified study")
            clinical = {"status": "UNMATCHED", "fields": {}, "provenance": "No clinical CSV supplied"}
            if files.get("clinical"):
                data = files["clinical"].read(2 * 1024 * 1024 + 1)
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError("Clinical CSV must be at most 2 MiB")
                rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
                matches = [r for r in rows if str(r.get("subject_id", r.get("PatientID", r.get("ID", "")))) == subject]
                clinical["status"] = "VERIFIED" if len(matches) == 1 else "AMBIGUOUS" if len(matches) > 1 else "UNMATCHED"
                clinical["provenance"] = "Exact subject ID join to uploaded clinical CSV"
                if len(matches) == 1:
                    aliases = {"diagnosis": ("diagnosis", "Final pathologic diagnosis (WHO 2021)"), "age": ("age", "Age at MRI"), "sex": ("sex", "Sex"), "grade": ("grade", "WHO CNS Grade"), "IDH": ("IDH",), "MGMT": ("MGMT", "MGMT status")}
                    clinical["fields"] = {key: next((matches[0][a][:500] for a in names if matches[0].get(a)), None) for key, names in aliases.items()}
            record = {"id": identifier, "subject": subject, "collection": collection, "release": str(form.get("release", "User-supplied export"))[:200],
                      "license": license_name, "source": "IMPORTED", "modality": "MR", "age_days": 0,
                      "objects": objects, "sequences": sequences, "complete": len(sequences) == 4,
                      "clinical": clinical, "access": {"hold": False, "active": False, "max_hours": None},
                      "analysis": {"status": "NOT_RUN", "model": "MONAI BraTS SegResNet 0.5.4", "message": "Validate aligned, brain-extracted inputs before analysis."},
                      "requested_tier": "STANDARD", "restore": "NOT_REQUESTED", "version": 0}
            record["decision"] = policy(record)
            return self.save(record, "IMPORTED", "Files measured and checksummed; clinical join evaluated.")
        except Exception:
            # Remove only files created by this failed import, inside its unique directory.
            if directory.exists():
                for child in directory.iterdir():
                    child.unlink()
                directory.rmdir()
            raise


def public_study(study):
    result = json.loads(json.dumps(study))
    for obj in result["objects"]:
        obj["has_pixels"] = bool(obj.pop("file", None))
    return result
