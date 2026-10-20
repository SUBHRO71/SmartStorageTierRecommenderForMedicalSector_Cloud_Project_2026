"""Deployed v2-only application. Local demonstration auth is never installed."""
import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from archive_routes import create_archive_blueprint
from cloud_archive import CloudArchive
from cloud_auth import install_auth


def create_app(verifier=None, archive=None):
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
    archive = archive or CloudArchive(os.environ["ARCHIVE_BUCKET"])
    app.register_blueprint(create_archive_blueprint(archive_instance=archive))
    if hasattr(archive, "bucket"):
        from staged_uploads import install_staged_uploads
        install_staged_uploads(app, archive)
    install_auth(app, verifier)
    frontend = Path(os.environ.get("FRONTEND_DIR", Path(__file__).resolve().parents[1] / "frontend/dist"))

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store" if response.mimetype != "text/css" else "public, max-age=3600"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error={"message": exc.description}), exc.code
        app.logger.exception("Study API failed")
        return jsonify(error={"message": "The operation failed. Refresh and inspect the operation history before retrying."}), 500

    @app.get("/api/health")
    def health():
        return jsonify(status="healthy", mode="AWS", version="v2", auth_mode="cognito")

    @app.get("/config.js")
    def config():
        data = {"apiUrl": "/api", "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
                "userPoolId": os.environ["COGNITO_USER_POOL_ID"], "clientId": os.environ["COGNITO_CLIENT_ID"], "mode": "AWS"}
        return app.response_class("window.CLOUDTIER_CONFIG=" + json.dumps(data) + ";", mimetype="application/javascript")

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend_files(path):
        if path.startswith("api/"):
            return jsonify(error={"message": "Endpoint not found"}), 404
        target = frontend / path
        return send_from_directory(frontend, path if path and target.is_file() else "index.html")

    if verifier is None:
        def reconcile_loop():
            while not stop.wait(300):
                for study in archive.studies():
                    if study["source"] != "SYNTHETIC":
                        try:
                            archive.reconcile(study["id"])
                        except Exception:
                            app.logger.exception("Scheduled S3 reconciliation failed")
        stop = threading.Event()
        threading.Thread(target=reconcile_loop, daemon=True).start()
    return app
