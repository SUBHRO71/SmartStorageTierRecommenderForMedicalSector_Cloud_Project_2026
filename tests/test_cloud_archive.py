import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import jwt
import nibabel as nib
import numpy as np
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))
from cloud_archive import CloudArchive
from cloud_app import create_app


class S3:
    def __init__(self):
        self.objects, self.tags, self.copies, self.restores = {}, {}, [], []
        self.fail = None

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.objects[key] = {"ContentLength": Path(filename).stat().st_size}
        self.tags[key] = [{"Key": "source", "Value": "preserve"}]

    def delete_object(self, **location):
        self.objects.pop(location["Key"], None)

    def head_object(self, Bucket, Key):
        if self.fail == Key: raise RuntimeError("Member unavailable")
        return copy.deepcopy(self.objects[Key])

    def get_object_tagging(self, Bucket, Key):
        return {"TagSet": self.tags[Key]}

    def put_object_tagging(self, Bucket, Key, Tagging):
        self.tags[Key] = Tagging["TagSet"]

    def copy_object(self, **args):
        self.copies.append(args)
        self.objects[args["Key"]]["StorageClass"] = args["StorageClass"]

    def restore_object(self, **args):
        self.restores.append(args)
        self.objects[args["Key"]]["Restore"] = 'ongoing-request="true"'

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return "https://upload.example.test/" + Params["Key"]

    def download_fileobj(self, bucket, key, stream):
        stream.write(self.objects[key]["Body"])


class CloudArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.s3 = S3()
        self.archive = CloudArchive("archive-test", self.root / "catalog.db", self.root / "files", s3=self.s3)
        self.env = patch.dict(os.environ, {"COGNITO_USER_POOL_ID": "us-east-1_test", "COGNITO_CLIENT_ID": "client-test"})
        self.env.start()
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.keys = patch("jwt.PyJWKClient.get_signing_key_from_jwt")
        self.keys.start().return_value.key = self.key.public_key()
        # A verifier wrapper avoids starting the production reconciliation thread;
        # token verification itself still uses the real install_auth validation below.
        self.app = create_app(verifier=lambda t: jwt.decode(t, self.key.public_key(), algorithms=["RS256"], audience="client-test"), archive=self.archive)
        self.app.logger.disabled = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.keys.stop(); self.env.stop(); self.temp.cleanup()

    def token(self, group="archive-admin", **overrides):
        claims = {"sub": "test-actor", "aud": "client-test", "exp": int(time.time()) + 300, "cognito:groups": [group]}
        claims.update(overrides)
        return {"Authorization": "Bearer " + jwt.encode(claims, self.key, algorithm="RS256")}

    def imported(self):
        volume = self.root / "volume.nii"
        nib.save(nib.Nifti1Image(np.random.default_rng(2).normal(size=(32, 32, 32)).astype("float32"), np.eye(4)), volume)
        payload = {"subject": "FIXTURE", "collection": "Synthetic QA", "license": "Synthetic generated fixture",
                   "clinical": (io.BytesIO(b"subject_id,diagnosis\nFIXTURE,Test\n"), "clinical.csv")}
        for role in ("T1", "T1ce", "T2", "FLAIR"):
            payload[role] = (io.BytesIO(volume.read_bytes()), role + ".nii")
        response = self.client.post("/api/archive/import", headers=self.token(), data=payload, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201, response.json)
        return self.archive.get(response.json["study"]["id"])

    def test_authentication_roles_and_signed_token_validation(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/archive/studies").status_code, 401)
        self.assertEqual(self.client.get("/api/archive/studies", headers=self.token("viewer")).status_code, 200)
        self.assertEqual(self.client.post("/api/archive/demo", headers=self.token("viewer")).status_code, 403)
        self.assertEqual(self.client.get("/api/archive/studies", headers=self.token("other")).status_code, 403)
        self.assertEqual(self.client.get("/api/archive/studies", headers=self.token(exp=1)).status_code, 401)
        self.assertEqual(self.client.get("/api/archive/studies", headers=self.token(aud="other-client")).status_code, 401)

    def test_import_uploads_all_members_and_private_preview_requires_token(self):
        study = self.imported()
        self.assertEqual(len(self.s3.objects), 4)
        self.assertTrue(all(o.get("key") and o["sha256"] for o in study["objects"]))
        url = f"/api/archive/studies/{study['id']}/preview/T1"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.token("viewer")).mimetype, "image/png")
        self.assertEqual(self.archive.events(study["id"])[0]["details"]["actor"], "test-actor")

    def test_forecast_requires_matching_cohort_and_records_model_without_overriding_hold(self):
        study = self.imported()
        path = f"/api/archive/studies/{study['id']}/forecast"
        payload = dict(version=study["version"], cohort="LUMIERE", history_days=[0, 49, 147],
                       scenario_anchor_date="2026-10-20", enable_storage_scenario=True)
        self.assertEqual(self.client.post(path, headers=self.token(), json=payload).status_code, 400)
        study["collection"] = "LUMIERE research pilot"
        study["access"]["hold"] = True
        study = self.archive.save(study, "TEST_CONTEXT", "Publisher context")
        payload["version"] = study["version"]
        self.assertEqual(self.client.post(path, headers=self.token("viewer"), json=payload).status_code, 403)
        response = self.client.post(path, headers=self.token(), json=payload)
        self.assertEqual(response.status_code, 200, response.json)
        result = response.json["study"]
        self.assertFalse(result["forecast"]["actual_retrieval_model"])
        self.assertEqual(result["decision"]["tier"], "STANDARD")
        self.assertEqual(result["decision"]["horizon"], 3)
        self.assertEqual(self.client.post(path, headers=self.token(), json=payload).status_code, 400)
        def declared_standard(months):
            data = self.client.get(f"/api/archive/costs?horizon={months}&accesses=0", headers=self.token()).json
            self.assertEqual(data["horizon"], months)
            return next(p["cost"] for p in data["policies"] if p["name"] == "All Standard")
        self.assertAlmostEqual(declared_standard(12), 4 * declared_standard(3))

    def test_placement_is_pending_until_every_member_is_observed(self):
        study = self.imported()
        study["access"]["max_hours"] = 48
        study["decision"].update(horizon=120, accesses=0)
        self.archive.save(study, "TEST", expected_version=study["version"])
        result = self.archive.place(study["id"], study["version"], "Test cold placement")
        target = result["requested_tier"]
        self.assertIn(target, ("GLACIER", "DEEP_ARCHIVE"))
        self.assertEqual(result["placement_status"], "PENDING")
        self.assertTrue(all(o["tier"] == "STANDARD" for o in result["objects"]))
        self.assertTrue(all(any(t["Key"] == "source" for t in tags) for tags in self.s3.tags.values()))
        for obj in result["objects"]: self.s3.objects[obj["key"]]["StorageClass"] = target
        result = self.archive.reconcile(study["id"])
        self.assertEqual(result["placement_status"], "APPLIED")

    def test_restore_waits_for_complete_bundle_and_detects_partial_failure(self):
        study = self.imported()
        for obj in study["objects"]: self.s3.objects[obj["key"]]["StorageClass"] = "DEEP_ARCHIVE"
        study = self.archive.reconcile(study["id"])
        result = self.archive.restore_bundle(study["id"], study["version"])
        self.assertEqual(len(self.s3.restores), 4)
        self.assertEqual(result["restore"], "PENDING")
        for obj in result["objects"]: self.s3.objects[obj["key"]]["Restore"] = 'ongoing-request="false", expiry-date="future"'
        self.assertEqual(self.archive.reconcile(study["id"])["restore"], "AVAILABLE")
        self.s3.fail = study["objects"][0]["key"]
        self.assertEqual(self.archive.reconcile(study["id"])["placement_status"], "PARTIAL_FAILURE")

    def test_hot_copy_requires_restore_and_stale_requests_do_not_mutate_s3(self):
        study = self.imported()
        for obj in study["objects"]: self.s3.objects[obj["key"]]["StorageClass"] = "GLACIER"
        with self.assertRaises(ValueError): self.archive.place(study["id"], 0, "Stale request")
        self.assertEqual(self.s3.copies, [])
        result = self.archive.place(study["id"], study["version"], "Hot hold")
        self.assertEqual(result["placement_status"], "PARTIAL_FAILURE")
        for obj in result["objects"]: self.s3.objects[obj["key"]]["Restore"] = 'ongoing-request="false"'
        result = self.archive.place(study["id"], result["version"], "Restored hot hold")
        self.assertEqual(result["placement_status"], "APPLIED")
        self.assertEqual(len(self.s3.copies), 4)

    def test_synthetic_records_never_produce_real_s3_requests(self):
        self.archive.demo()
        with self.assertRaises(ValueError): self.archive.place("DEMO-008", 1, "Synthetic")
        self.assertEqual(self.s3.objects, {})

    def test_access_hold_cancels_outstanding_cold_tags(self):
        study = self.imported()
        study["access"]["max_hours"] = 48
        study["decision"].update(horizon=120, accesses=0)
        self.archive.save(study, "TEST", expected_version=study["version"])
        study = self.archive.place(study["id"], study["version"], "Cold request")
        response = self.client.patch(f"/api/archive/studies/{study['id']}/access", headers=self.token(), json={
            "version": study["version"], "hold": True, "active": False, "max_hours": 0, "reason": "Protect immediate access"})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["study"]["requested_tier"], "STANDARD")
        self.assertTrue(all(any(t == {"Key": "tier", "Value": "STANDARD"} for t in tags) for tags in self.s3.tags.values()))

    def test_failed_upload_does_not_commit_a_study(self):
        with patch.object(self.s3, "upload_file", side_effect=RuntimeError("S3 denied upload")):
            with self.assertRaises(AssertionError):
                self.imported()
        self.assertEqual(self.archive.studies(), [])
        self.assertEqual(self.s3.objects, {})

    def test_production_verifier_rejects_wrong_token_use_and_issuer(self):
        from flask import Flask
        from cloud_auth import install_auth
        app = Flask(__name__)
        install_auth(app)
        app.add_url_rule("/api/test", view_func=lambda: {"ok": True})
        client = app.test_client()
        issuer = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test"
        headers = self.token(iss=issuer, iat=int(time.time()), token_use="id")
        self.assertEqual(client.get("/api/test", headers=headers).status_code, 200)
        self.assertEqual(client.get("/api/test", headers=self.token(iss=issuer, iat=int(time.time()), token_use="access")).status_code, 401)
        self.assertEqual(client.get("/api/test", headers=self.token(iss="wrong", iat=int(time.time()), token_use="id")).status_code, 401)

    def test_direct_upload_limits_roles_and_owner_binding(self):
        payload = {"subject": "TEST", "collection": "Synthetic", "license": "Generated",
                   "files": [{"role": "T1", "name": "fixture.nii", "size": 100}]}
        self.assertEqual(self.client.post("/api/archive/uploads", headers=self.token("viewer"), json=payload).status_code, 403)
        payload["files"][0]["size"] = 513 * 1024 * 1024
        self.assertEqual(self.client.post("/api/archive/uploads", headers=self.token(), json=payload).status_code, 400)
        payload["files"][0]["size"] = 100
        response = self.client.post("/api/archive/uploads", headers=self.token(), json=payload)
        self.assertEqual(response.status_code, 201)
        identifier = response.json["id"]
        self.assertEqual(self.client.get("/api/archive/uploads/" + identifier, headers=self.token(sub="other-actor")).status_code, 404)

    def test_direct_upload_job_validates_and_imports_all_members(self):
        volume = self.root / "staged.nii"
        nib.save(nib.Nifti1Image(np.ones((4, 4, 4), dtype="float32"), np.eye(4)), volume)
        payload = {"subject": "STAGED", "collection": "Synthetic", "license": "Generated", "files": [
            {"role": role, "name": role + ".nii", "size": volume.stat().st_size} for role in ("T1", "T1ce", "T2", "FLAIR")]}
        response = self.client.post("/api/archive/uploads", headers=self.token(), json=payload)
        self.assertEqual(response.status_code, 201, response.json)
        identifier = response.json["id"]
        for index in range(4): self.s3.objects[f"staging/{identifier}/{index}"] = {"ContentLength": volume.stat().st_size, "Body": volume.read_bytes()}
        self.assertEqual(self.client.post(f"/api/archive/uploads/{identifier}/commit", headers=self.token()).status_code, 202)
        for _ in range(100):
            result = self.client.get(f"/api/archive/uploads/{identifier}", headers=self.token()).json
            if result["status"] != "PROCESSING": break
            time.sleep(.02)
        self.assertEqual(result["status"], "DONE", result)
        self.assertTrue(result["study"]["complete"])
        self.assertEqual(self.archive.events(result["study"]["id"])[0]["details"]["actor"], "test-actor")
        self.assertEqual(self.client.post(f"/api/archive/uploads/{identifier}/commit", headers=self.token()).status_code, 409)


if __name__ == "__main__": unittest.main()
