"""Local study API. Raw data stays on this machine; v1 cloud remains separate."""
import io
import threading

import numpy as np
from flask import Blueprint, g, jsonify, request, send_file
from PIL import Image

from archive import Archive, policy, public_study


def create_archive_blueprint(use_aws=False, archive_instance=None):
    api = Blueprint("archive", __name__, url_prefix="/api/archive")
    archive = archive_instance or (Archive() if not use_aws else None)
    cloud = getattr(archive, "mode", "LOCAL") == "AWS"
    analysis_lock = threading.Lock()
    if archive:
        archive.recover_interrupted_analysis()

    @api.before_request
    def require_local():
        if use_aws and not archive_instance:
            return jsonify(error={"message": "The v2 study archive currently requires the local backend. Your v1 cloud scan API remains available."}), 501
        if cloud and request.method not in ("GET", "HEAD", "OPTIONS"):
            archive.operations.acquire()
            g.archive_operation_locked = True

    @api.teardown_request
    def release_operation(_error):
        if cloud and getattr(g, "archive_operation_locked", False):
            g.archive_operation_locked = False
            archive.operations.release()

    @api.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error={"message": str(error)}), 400

    @api.errorhandler(ImportError)
    def dependency(error):
        return jsonify(error={"message": "Install src/ml_model/requirements_mri.txt to enable MRI file imports and inference."}), 503

    def get_study(identifier):
        study = archive.get(identifier)
        if not study:
            from werkzeug.exceptions import NotFound
            raise NotFound("Study not found")
        return study

    @api.get("/studies")
    def studies():
        collection = request.args.get("collection")
        rows = [s for s in archive.studies() if not collection or s["collection"] == collection]
        return jsonify(studies=[public_study(s) for s in rows], summary=archive.summary(rows), mode="AWS" if cloud else "LOCAL", events=archive.events())

    @api.get("/studies/<identifier>")
    def detail(identifier):
        return jsonify(study=public_study(get_study(identifier)), events=archive.events(identifier), mode="AWS" if cloud else "LOCAL")

    @api.post("/demo")
    def demo():
        return jsonify(imported=archive.demo(), provenance="SYNTHETIC"), 201

    @api.post("/import")
    def import_study():
        if request.content_length and request.content_length > 512 * 1024 * 1024:
            raise ValueError("An import must be at most 512 MiB")
        try:
            study = archive.import_study(request.form, request.files)
        except (ValueError, ImportError):
            raise
        except Exception as error:
            if type(error).__module__.startswith(("nibabel", "pydicom")) or isinstance(error, (OSError, UnicodeError)):
                raise ValueError("An uploaded file could not be parsed as valid DICOM, NIfTI or UTF-8 clinical CSV") from error
            raise
        return jsonify(study=public_study(study)), 201

    @api.patch("/studies/<identifier>/access")
    def access(identifier):
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("version")) is not int:
            raise ValueError("The current study version is required")
        if len(str(payload.get("reason", "")).strip()) < 3:
            raise ValueError("Give a short reason for changing access requirements")
        if type(payload.get("hold")) is not bool or type(payload.get("active")) is not bool:
            raise ValueError("Hold and active-use values must be booleans")
        hours = payload.get("max_hours")
        if hours is not None and (type(hours) not in (int, float) or not np.isfinite(hours) or not 0 <= hours <= 8760):
            raise ValueError("Access time must be between 0 and 8760 hours")
        study["access"] = {"hold": payload["hold"], "active": payload["active"], "max_hours": hours}
        study["decision"] = policy(study)
        saved = archive.save(study, "ACCESS_UPDATED", payload["reason"], payload.get("version"))
        if cloud and saved["source"] != "SYNTHETIC" and saved["decision"]["tier"] == "STANDARD" and saved["requested_tier"] != "STANDARD":
            saved = archive.place(identifier, saved["version"], "Access protection updated: " + payload["reason"])
        return jsonify(study=public_study(saved))

    @api.post("/studies/<identifier>/recommend")
    def recommend(identifier):
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("version")) is not int:
            raise ValueError("The current study version is required")
        study["decision"] = policy(study, float(payload.get("horizon", 12)), float(payload.get("accesses", 1)))
        return jsonify(study=public_study(archive.save(study, "RECOMMENDED", study["decision"]["reason"], payload.get("version"))))

    @api.post("/studies/<identifier>/forecast")
    def predict_visit(identifier):
        from temporal_forecast import forecast
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("version")) is not int:
            raise ValueError("The current study version is required")
        cohort = payload.get("cohort")
        if not isinstance(cohort, str) or cohort.upper() not in study["collection"].upper():
            raise ValueError("The historical context must match the study collection")
        if type(payload.get("enable_storage_scenario", False)) is not bool:
            raise ValueError("Storage-scenario enablement must be boolean")
        study["forecast"] = forecast(payload.get("history_days"), cohort, payload.get("mask_features"), payload.get("scenario_anchor_date"))
        study["forecast"]["storage_scenario_enabled"] = payload.get("enable_storage_scenario", False)
        study["forecast"]["feature_provenance"] = "Caller-supplied historical visit days and current publisher segmentation summaries; not the MONAI segmentation model"
        study["decision"] = policy(study)
        saved = archive.save(study, "VISIT_PROXY_FORECAST", "Experimental conditional next-visit forecast; scenario date is explicitly anchored, not an observed retrieval date.", payload["version"])
        return jsonify(study=public_study(saved))

    @api.post("/studies/<identifier>/placement")
    def placement(identifier):
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if len(str(payload.get("reason", "")).strip()) < 3:
            raise ValueError("A placement reason is required")
        if payload.get("version") != study["version"]:
            raise ValueError("The study changed. Refresh before requesting placement.")
        if cloud:
            return jsonify(study=public_study(archive.place(identifier, payload["version"], payload["reason"])), mode="AWS"), 202
        decision = policy(study, study["decision"]["horizon"], study["decision"]["accesses"])
        for obj in study["objects"]:
            obj["tier"] = decision["tier"]
        study["requested_tier"] = decision["tier"]
        study["decision"] = decision
        study["restore"] = "NOT_REQUESTED"
        return jsonify(study=public_study(archive.save(study, "PLACEMENT_SIMULATED", payload["reason"], payload["version"])), mode="LOCAL_SIMULATION")

    @api.post("/studies/<identifier>/restore")
    def restore(identifier):
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("version")) is not int:
            raise ValueError("The current study version is required")
        if cloud:
            return jsonify(study=public_study(archive.restore_bundle(identifier, payload["version"])), mode="AWS"), 202
        study["restore"] = "NOT_REQUIRED" if all(o["tier"] not in ("GLACIER", "DEEP_ARCHIVE") for o in study["objects"]) else "AVAILABLE_LOCAL"
        return jsonify(study=public_study(archive.save(study, "RESTORE_SIMULATED", "All required members available in local simulation.", payload.get("version"))), mode="LOCAL_SIMULATION")

    @api.get("/studies/<identifier>/preview/<role>")
    def preview(identifier, role):
        study = get_study(identifier)
        obj = next((o for o in study["objects"] if o["role"] == role and o.get("file") and o["format"] == "NIfTI"), None)
        if not obj:
            return jsonify(error={"message": "No NIfTI pixels are available for this sequence"}), 404
        import nibabel as nib
        image = nib.as_closest_canonical(nib.load(obj["file"]))
        plane = request.args.get("plane", "axial")
        if plane not in ("axial", "coronal", "sagittal"):
            raise ValueError("Choose axial, coronal or sagittal")
        axis = {"axial": 2, "coronal": 1, "sagittal": 0}[plane]
        fraction = float(request.args.get("slice", .5))
        if not np.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Slice position must be between 0 and 1")
        values = np.asarray(image.dataobj)
        data = np.rot90(np.take(values, round((image.shape[axis] - 1) * fraction), axis=axis))
        finite = data[np.isfinite(data)]
        if not finite.size:
            raise ValueError("Preview slice contains no finite values")
        low, high = np.percentile(finite, (1, 99))
        pixels = (np.clip((np.nan_to_num(data) - low) / max(high - low, 1e-6), 0, 1) * 255).astype("uint8")
        rendered = Image.fromarray(pixels).convert("RGB")
        overlay = request.args.get("overlay", "none")
        if overlay not in ("none", "WT", "TC", "ET"):
            raise ValueError("Unknown overlay region")
        if overlay != "none":
            if study["analysis"]["status"] != "READY":
                raise ValueError("A completed analysis is required for a prediction overlay")
            from pathlib import Path
            mask_path = Path(obj["file"]).parent / f"prediction_{overlay}.nii.gz"
            mask_image = nib.as_closest_canonical(nib.load(mask_path))
            mask = np.rot90(np.take(np.asarray(mask_image.dataobj), round((image.shape[axis] - 1) * fraction), axis=axis)).astype(bool)
            alpha = float(request.args.get("opacity", ".4"))
            if not np.isfinite(alpha) or not 0 <= alpha <= 1:
                raise ValueError("Overlay opacity must be between 0 and 1")
            rgb = np.asarray(rendered).copy()
            color = {"WT": (82, 193, 145), "TC": (105, 164, 242), "ET": (238, 163, 85)}[overlay]
            rgb[mask] = (rgb[mask] * (1-alpha) + np.array(color) * alpha).astype("uint8")
            rendered = Image.fromarray(rgb)
        output = io.BytesIO()
        rendered.save(output, format="PNG")
        output.seek(0)
        return send_file(output, mimetype="image/png", max_age=0)

    @api.post("/studies/<identifier>/analyze")
    def analyze(identifier):
        study = get_study(identifier)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("version")) is not int:
            raise ValueError("The current study version is required")
        if study["analysis"]["status"] == "RUNNING":
            return jsonify(error={"message": "An analysis is already running"}), 409
        if not study["complete"] or any(o["format"] != "NIfTI" or not o.get("file") for o in study["objects"]):
            raise ValueError("Analysis requires four imported NIfTI volumes. Raw DICOM must first be converted, aligned and brain-extracted offline.")
        if payload.get("preprocessed") is not True:
            raise ValueError("Confirm that the volumes are aligned and brain-extracted")
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml_model"))
        from mri_inference import run_study, checkpoint_ready
        if not checkpoint_ready():
            return jsonify(error={"message": "Download the pinned MONAI checkpoint using the documented MRI setup command before running analysis."}), 503
        if not analysis_lock.acquire(blocking=False):
            return jsonify(error={"message": "Another MRI analysis is running. Retry after it completes."}), 409
        study["analysis"]["status"] = "RUNNING"
        try:
            archive.save(study, "ANALYSIS_STARTED", "Frozen pretrained model; preprocessing attested by operator.", payload.get("version"))
        except Exception:
            analysis_lock.release()
            raise

        def worker():
            try:
                result = run_study(study)
            except Exception as error:
                result = {"status": "FAILED", "model": "MONAI BraTS SegResNet 0.5.4", "message": str(error)}
            try:
                archive.finish_analysis(identifier, result)
            finally:
                analysis_lock.release()

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(study=public_study(study)), 202

    @api.get("/costs")
    def costs():
        horizon = float(request.args.get("horizon", 12))
        accesses = float(request.args.get("accesses", 1))
        # Validate even when the archive is empty.
        if not np.isfinite(horizon) or not 0 < horizon <= 120 or not np.isfinite(accesses) or not 0 <= accesses <= 1000:
            raise ValueError("Invalid workload horizon or expected accesses")
        collection = request.args.get("collection")
        studies = [s for s in archive.studies() if not collection or s["collection"] == collection]
        totals = {"All Standard": 0, "Age-based": 0, "Current placement": 0, "Study policy": 0}
        components = {name: {key: 0 for key in ("storage", "transition", "retrieval", "metadata", "temporary")} for name in totals}
        for study in studies:
            # The comparison page promises one user-declared workload for all
            # policies. Study-specific proxy scenarios belong to study detail.
            decision = policy(study, horizon, accesses, use_forecast=False)
            by_tier = {c["tier"]: c for c in decision["candidates"]}
            age_tier = "GLACIER" if study["age_days"] >= 180 else "STANDARD"
            observed = {o["tier"] for o in study["objects"]}
            for name, tier in [("All Standard", "STANDARD"), ("Age-based", age_tier), ("Study policy", decision["tier"])]:
                totals[name] += by_tier[tier]["cost"]
                for key in components[name]:
                    components[name][key] += by_tier[tier][key]
            # Current placement costs each actual member in its own class.
            for obj in study["objects"]:
                single = {**study, "objects": [obj]}
                cost = next(c for c in policy(single, horizon, accesses, use_forecast=False)["candidates"] if c["tier"] == obj["tier"])
                totals["Current placement"] += cost["cost"]
                for key in components["Current placement"]:
                    components["Current placement"][key] += cost[key]
        return jsonify(policies=[{"name": name, "cost": value, "components": components[name]} for name, value in totals.items()],
                       horizon=horizon, accesses=accesses, studies=len(studies), collection=collection or "All collections", scope="Declared workload simulation",
                       price_snapshot=policy(studies[0], horizon, accesses, use_forecast=False)["price_snapshot"] if studies else None,
                       limitations="Engineering price snapshot. Excludes prior-tier exit charges, egress, compute, hot previews and other services. Age-based is an unconstrained comparison.")

    return api
