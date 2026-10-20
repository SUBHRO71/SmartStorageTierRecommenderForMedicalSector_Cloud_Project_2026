import contextlib
import io
import os
from pathlib import Path
import runpy
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]


class BackupTests(unittest.TestCase):
    def test_online_catalog_snapshot_and_working_file_copy_without_cloud_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "backups").mkdir()
            (root / "files/ST-TEST").mkdir(parents=True)
            (root / "files/ST-TEST/fixture.bin").write_bytes(b"synthetic pixels")
            database = root / "archive.db"
            with sqlite3.connect(database) as conn:
                conn.execute("CREATE TABLE evidence (value TEXT)")
                conn.execute("INSERT INTO evidence VALUES ('synthetic study')")
            conn.close()
            uploads = {}

            def upload(filename, bucket, key):
                self.assertEqual(bucket, "test-bucket")
                uploads[key] = Path(filename).read_bytes()

            class S3:
                exceptions = types.SimpleNamespace(ClientError=ClientError)
                upload_file = staticmethod(upload)

                @staticmethod
                def head_object(**_args):
                    raise ClientError({"Error": {"Code": "404", "Message": "Missing"}}, "HeadObject")

            original_path = Path
            def sandbox_path(value):
                return root if value == "/var/lib/cloudtier" else original_path(value)

            with patch.dict(os.environ, {"ARCHIVE_DB_PATH": str(database), "ARCHIVE_BUCKET": "test-bucket"}), \
                 patch("boto3.client", return_value=S3()), patch("pathlib.Path", side_effect=sandbox_path), \
                 contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(ROOT / "aws/backup.py"))
            snapshot = root / "verified.db"
            snapshot.write_bytes(next(value for key, value in uploads.items() if key.endswith("archive.db")))
            with sqlite3.connect(snapshot) as conn:
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(conn.execute("SELECT value FROM evidence").fetchone()[0], "synthetic study")
            conn.close()
            self.assertEqual(uploads["working-cache/ST-TEST/fixture.bin"], b"synthetic pixels")
