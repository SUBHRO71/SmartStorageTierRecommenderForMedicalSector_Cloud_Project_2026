"""S3-backed members with a transactional, single-server study catalog."""
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from archive import Archive, policy


class CloudArchive(Archive):
    mode = "AWS"

    def __init__(self, bucket, *args, s3=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bucket = bucket
        self.s3 = s3 or boto3.client("s3", config=Config(signature_version="s3v4"))
        self.operations = threading.RLock()

    def save(self, study, kind, details="", expected_version=None):
        if kind == "IMPORTED":
            study["uploaded_at"] = datetime.now(timezone.utc).isoformat()
            uploaded = []
            try:
                for obj in study["objects"]:
                    key = f"studies/{study['id']}/{Path(obj['file']).name}"
                    self.s3.upload_file(obj["file"], self.bucket, key,
                                        ExtraArgs={"Metadata": {"sha256": obj["sha256"]}, "Tagging": "tier=STANDARD"})
                    uploaded.append(key)
                    obj.update(bucket=self.bucket, key=key)
            except Exception:
                # Uploaded members have unique keys; failures remain visible in S3 version history.
                for key in uploaded:
                    self.s3.delete_object(Bucket=self.bucket, Key=key)
                raise
        return super().save(study, kind, details, expected_version)

    def get(self, identifier):
        study = super().get(identifier)
        if study and study.get("uploaded_at"):
            study["age_days"] = (datetime.now(timezone.utc) - datetime.fromisoformat(study["uploaded_at"])).days
        return study

    def finish_analysis(self, identifier, result):
        with self.operations:
            return super().finish_analysis(identifier, result)

    def _members(self, study):
        if study["source"] == "SYNTHETIC" or any(not obj.get("key") for obj in study["objects"]):
            raise ValueError("Real S3 operations require an imported study with uploaded members.")
        return study["objects"]

    def place(self, identifier, version, reason):
        with self.operations:
            study = self.get(identifier)
            self._members(study)
            if study["version"] != version:
                raise ValueError("The study changed. Refresh before requesting placement.")
            decision = policy(study, study["decision"]["horizon"], study["decision"]["accesses"])
            study.update(requested_tier=decision["tier"], decision=decision, placement_status="PENDING")
            self.save(study, "PLACEMENT_REQUESTED", reason, version)
            failures = []
            for obj in study["objects"]:
                try:
                    location = {"Bucket": self.bucket, "Key": obj["key"]}
                    tags = {t["Key"]: t["Value"] for t in self.s3.get_object_tagging(**location)["TagSet"]}
                    target = decision["tier"]
                    tags["tier"] = target
                    # Remove a previous cold request even when a hot copy must wait for restore.
                    self.s3.put_object_tagging(**location, Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]})
                    head = self.s3.head_object(**location)
                    observed = head.get("StorageClass", "STANDARD")
                    rank = {tier: i for i, tier in enumerate(("STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE"))}
                    if rank[target] < rank[observed]:
                        if observed in ("GLACIER", "DEEP_ARCHIVE") and 'ongoing-request="false"' not in head.get("Restore", ""):
                            raise ValueError("Restore this archived member before requesting hot placement.")
                        self.s3.copy_object(**location, CopySource=location, StorageClass=target,
                                            MetadataDirective="COPY", TaggingDirective="REPLACE", Tagging=urlencode(tags))
                    obj.pop("operation_error", None)
                except Exception as error:
                    obj["operation_error"] = str(error)[:300]
                    failures.append(obj["id"])
            study["placement_status"] = "PARTIAL_FAILURE" if failures else "PENDING"
            self.save(study, "PLACEMENT_SUBMITTED", f"Failed members: {failures}", study["version"])
            return self.reconcile(identifier)

    def restore_bundle(self, identifier, version):
        with self.operations:
            study = self.get(identifier)
            self._members(study)
            study["restore"] = "PENDING"
            self.save(study, "RESTORE_REQUESTED", "Complete bundle requested using Standard retrieval.", version)
            failures = []
            for obj in study["objects"]:
                try:
                    location = {"Bucket": self.bucket, "Key": obj["key"]}
                    head = self.s3.head_object(**location)
                    if head.get("StorageClass", "STANDARD") in ("GLACIER", "DEEP_ARCHIVE") and 'ongoing-request="false"' not in head.get("Restore", ""):
                        try:
                            self.s3.restore_object(**location, RestoreRequest={"Days": 2, "GlacierJobParameters": {"Tier": "Standard"}})
                        except ClientError as error:
                            if error.response["Error"]["Code"] != "RestoreAlreadyInProgress":
                                raise
                    obj.pop("operation_error", None)
                except Exception as error:
                    obj["operation_error"] = str(error)[:300]
                    failures.append(obj["id"])
            study["restore"] = "PARTIAL_FAILURE" if failures else "PENDING"
            self.save(study, "RESTORE_SUBMITTED", f"Failed members: {failures}", study["version"])
            return self.reconcile(identifier)

    def reconcile(self, identifier):
        with self.operations:
            study = self.get(identifier)
            self._members(study)
            prior = [(o.get("tier"), o.get("restore_state"), o.get("observation_error")) for o in study["objects"]]
            old_status = (study.get("placement_status"), study.get("restore"))
            for obj in study["objects"]:
                try:
                    head = self.s3.head_object(Bucket=self.bucket, Key=obj["key"])
                    obj["tier"] = head.get("StorageClass", "STANDARD")
                    obj["restore_state"] = ("AVAILABLE" if 'ongoing-request="false"' in head.get("Restore", "") else "PENDING") if obj["tier"] in ("GLACIER", "DEEP_ARCHIVE") else "NOT_REQUIRED"
                    obj.pop("observation_error", None)
                except Exception as error:
                    obj["observation_error"] = str(error)[:300]
            errors = any(o.get("operation_error") or o.get("observation_error") for o in study["objects"])
            study["placement_status"] = "PARTIAL_FAILURE" if errors else "APPLIED" if all(o["tier"] == study["requested_tier"] for o in study["objects"]) else "PENDING"
            if study["restore"] != "NOT_REQUESTED":
                study["restore"] = "PARTIAL_FAILURE" if errors else "AVAILABLE" if all(o.get("restore_state") in ("AVAILABLE", "NOT_REQUIRED") for o in study["objects"]) else "PENDING"
            observed = [(o.get("tier"), o.get("restore_state"), o.get("observation_error")) for o in study["objects"]]
            if prior != observed or old_status != (study.get("placement_status"), study.get("restore")):
                self.save(study, "S3_RECONCILED", "Member storage classes and restore headers observed from S3.", study["version"])
            return study
