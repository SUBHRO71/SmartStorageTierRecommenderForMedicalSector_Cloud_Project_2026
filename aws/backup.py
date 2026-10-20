"""Consistent SQLite snapshot; keep source/cache backup separate from tiered objects."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone

import boto3

root = Path("/var/lib/cloudtier")
snapshot = root / "backups/archive.db"
with closing(sqlite3.connect(os.environ["ARCHIVE_DB_PATH"])) as source, closing(sqlite3.connect(snapshot)) as dest:
    source.backup(dest)
s3 = boto3.client("s3")
bucket = os.environ["ARCHIVE_BUCKET"]
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
s3.upload_file(str(snapshot), bucket, f"backups/{stamp}/archive.db")
for path in (root / "files").rglob("*"):
    if path.is_file():
        # Cache backup remains Standard; it is not counted as tiering savings.
        key = "working-cache/" + path.relative_to(root / "files").as_posix()
        head = None
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
        except s3.exceptions.ClientError as error:
            if error.response["Error"]["Code"] not in ("404", "NoSuchKey"):
                raise
        if not head or head["ContentLength"] != path.stat().st_size:
            s3.upload_file(str(path), bucket, key)
print(f"Catalog backup written to s3://{bucket}/backups/{stamp}/archive.db")
