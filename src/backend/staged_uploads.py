"""Authenticated, owner-bound, resumable-inventory direct S3 study uploads."""
import json
import tempfile
import threading
import time
import uuid

from flask import abort, g, jsonify, request
from werkzeug.datastructures import FileStorage, MultiDict

from archive import public_study


def install_staged_uploads(app, archive):
    with archive.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS upload_jobs (id TEXT PRIMARY KEY, actor TEXT NOT NULL, status TEXT NOT NULL, record TEXT NOT NULL)")
        conn.execute("UPDATE upload_jobs SET status='FAILED' WHERE status='PROCESSING'")

    def job(identifier):
        with archive.connection() as conn:
            row = conn.execute("SELECT * FROM upload_jobs WHERE id=? AND actor=?", (identifier, g.actor)).fetchone()
        if not row: abort(404, "Upload not found")
        return dict(row), json.loads(row["record"])

    @app.post("/api/archive/uploads")
    def initiate():
        payload = request.get_json(silent=True) or {}
        files = payload.get("files")
        if not isinstance(files, list) or not 1 <= len(files) <= 512:
            abort(400, "Choose 1 to 512 imaging/clinical files")
        form = {key: str(payload.get(key, ""))[:200] for key in ("subject", "collection", "license", "release")}
        if not all(form[key].strip() for key in ("subject", "collection", "license")):
            abort(400, "Subject, collection and permission/license are required")
        identifier = uuid.uuid4().hex
        members, uploads, total = [], [], 0
        for index, item in enumerate(files):
            if not isinstance(item, dict): abort(400, "Invalid file descriptor")
            role, name, size = item.get("role"), str(item.get("name", "")), item.get("size")
            if role not in ("T1", "T1ce", "T2", "FLAIR", "clinical") or type(size) is not int or size <= 0:
                abort(400, "Invalid sequence role or file size")
            if not name.lower().endswith((".csv",) if role == "clinical" else (".nii", ".nii.gz", ".dcm")):
                abort(400, "Unsupported imaging or clinical file type")
            if role == "clinical" and size > 2 * 1024 * 1024: abort(400, "Clinical CSV must be at most 2 MiB")
            total += size
            if total > 512 * 1024 * 1024: abort(400, "Import must be at most 512 MiB")
            key = f"staging/{identifier}/{index}"
            members.append({"key": key, "role": role, "name": name[:255], "size": size})
        for item in members:
            url = archive.s3.generate_presigned_url("put_object", Params={"Bucket": archive.bucket,
                "Key": item["key"], "ContentLength": item["size"], "ContentType": "application/octet-stream"}, ExpiresIn=3600)
            uploads.append({"url": url, "role": item["role"], "name": item["name"]})
        record = {"form": form, "members": members, "expires": time.time() + 3600}
        with archive.connection() as conn:
            active = conn.execute("SELECT COUNT(*) FROM upload_jobs WHERE actor=? AND status='PROCESSING'", (g.actor,)).fetchone()[0]
            if active >= 2: abort(409, "Wait for your current imports to finish")
            conn.execute("INSERT INTO upload_jobs VALUES (?,?,?,?)", (identifier, g.actor, "UPLOADING", json.dumps(record)))
        return jsonify(id=identifier, uploads=uploads), 201

    @app.get("/api/archive/uploads/<identifier>")
    def status(identifier):
        row, record = job(identifier)
        study = archive.get(record["study_id"]) if record.get("study_id") else None
        return jsonify(id=identifier, status=row["status"], study=public_study(study) if study else None,
                       message=record.get("message", "The server restarted during import. Start a new upload." if row["status"] == "FAILED" else ""))

    @app.post("/api/archive/uploads/<identifier>/commit")
    def commit(identifier):
        row, record = job(identifier)
        if row["status"] != "UPLOADING": abort(409, "This upload has already been submitted")
        if time.time() > record["expires"]: abort(400, "Upload expired. Start a new upload")
        actor = g.actor
        with archive.connection() as conn:
            changed = conn.execute("UPDATE upload_jobs SET status='PROCESSING' WHERE id=? AND status='UPLOADING'", (identifier,)).rowcount
            if not changed: abort(409, "This upload has already been submitted")

        def worker():
            streams = []
            try:
                files = MultiDict()
                for item in record["members"]:
                    head = archive.s3.head_object(Bucket=archive.bucket, Key=item["key"])
                    if head["ContentLength"] != item["size"]: raise ValueError("An uploaded member has an unexpected size")
                    stream = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
                    streams.append(stream)
                    archive.s3.download_fileobj(archive.bucket, item["key"], stream)
                    stream.seek(0)
                    files.add(item["role"], FileStorage(stream=stream, filename=item["name"]))
                with archive.operations, app.app_context():
                    g.actor = actor
                    study = archive.import_study(record["form"], files)
                record["study_id"] = study["id"]
                state = "DONE"
            except Exception as error:
                app.logger.exception("Staged study import failed")
                record["message"] = str(error)[:500]
                state = "FAILED"
            finally:
                for stream in streams: stream.close()
            with archive.connection() as conn:
                conn.execute("UPDATE upload_jobs SET status=?,record=? WHERE id=?", (state, json.dumps(record), identifier))
            for item in record["members"]:
                try: archive.s3.delete_object(Bucket=archive.bucket, Key=item["key"])
                except Exception: app.logger.exception("Staging cleanup deferred to Lifecycle")

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(id=identifier, status="PROCESSING"), 202
