"""Live v2 acceptance checks using generated, explicitly synthetic MRI volumes."""
import argparse
import io
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
import uuid

import boto3
import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "temp/aws-v2"
    outputs = json.loads((folder / "outputs.json").read_text())
    credentials = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "CloudTierRecommender/aws-v2/admin-login.json"
    login = json.loads(credentials.read_text())
    cognito = boto3.client("cognito-idp", region_name="us-east-1")
    token = cognito.admin_initiate_auth(UserPoolId=outputs["UserPoolId"], ClientId=outputs["UserPoolClientId"],
        AuthFlow="ADMIN_USER_PASSWORD_AUTH", AuthParameters={"USERNAME": login["username"], "PASSWORD": login["password"]})["AuthenticationResult"]["IdToken"]
    base = outputs["ApiUrl"]
    evidence = {"provenance": "Generated synthetic compatibility fixture; no patient data or clinical accuracy claim.", "checks": []}

    def call(path, method="GET", payload=None, data=None, content_type="application/json", auth=True):
        if payload is not None: data = json.dumps(payload).encode()
        headers = {"Content-Type": content_type}
        if auth: headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=130) as response:
            raw = response.read()
            return json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw

    def check(name, success):
        if not success: raise AssertionError(name)
        evidence["checks"].append(name)
        print("PASS " + name, flush=True)

    check("HTTPS health", call("/health", auth=False)["version"] == "v2")
    try:
        call("/archive/studies", auth=False)
        raise AssertionError("Unauthenticated access was allowed")
    except urllib.error.HTTPError as error:
        check("Unauthenticated API denied", error.code == 401)
    check("Cognito authenticated catalog", call("/archive/studies")["mode"] == "AWS")
    try:
        call("/scans")
        raise AssertionError("Legacy scan API remains active")
    except urllib.error.HTTPError as error:
        check("Legacy API retired", error.code == 404)
    fields, upload_files = {}, []
    def field(name, value, filename=None, mime="application/octet-stream"):
        if filename: upload_files.append({"role": name, "name": filename, "body": value if isinstance(value, bytes) else value.encode()})
        else: fields[name] = value
    subject = "QA-SYNTHETIC-" + uuid.uuid4().hex[:8]
    for name, value in {"subject": subject, "collection": "Synthetic AWS deployment verification", "license": "Generated synthetic data; no patient images", "release": "AWS v2 compatibility smoke fixture"}.items():
        field(name, value)
    field("clinical", f"subject_id,diagnosis,age\n{subject},Synthetic test fixture,40\n", "clinical.csv", "text/csv")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "fixture.nii"
        nib.save(nib.Nifti1Image(np.random.default_rng(20).normal(size=(32, 32, 32)).astype("float32"), np.eye(4)), path)
        for role in ("T1", "T1ce", "T2", "FLAIR"): field(role, path.read_bytes(), role + ".nii")
    ticket = call("/archive/uploads", "POST", payload={**fields, "files": [{"role": f["role"], "name": f["name"], "size": len(f["body"])} for f in upload_files]})
    first_url = ticket["uploads"][0]["url"]
    preflight = urllib.request.Request(first_url, method="OPTIONS", headers={"Origin": outputs["FrontendUrl"].rstrip("/"), "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "content-type"})
    with urllib.request.urlopen(preflight, timeout=30) as response:
        check("Browser direct-upload CORS", response.status == 200 and response.headers.get("Access-Control-Allow-Origin") in ("*", outputs["FrontendUrl"].rstrip("/")))
    for item, upload in zip(upload_files, ticket["uploads"]):
        req = urllib.request.Request(upload["url"], data=item["body"], headers={"Content-Type": "application/octet-stream"}, method="PUT")
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status != 200: raise AssertionError("Direct source upload failed")
    call(f"/archive/uploads/{ticket['id']}/commit", "POST", payload={})
    for _ in range(120):
        result = call(f"/archive/uploads/{ticket['id']}")
        if result["status"] != "PROCESSING": break
        time.sleep(2)
    check("Asynchronous direct S3 import completed", result["status"] == "DONE")
    study = result["study"]
    identifier = study["id"]
    evidence["study_id"] = identifier
    path = "/archive/studies/" + identifier
    check("Four-volume import and exact clinical join", study["complete"] and study["clinical"]["status"] == "VERIFIED")
    s3 = boto3.client("s3", region_name="us-east-1")
    check("All source members exist in private S3", all(s3.head_object(Bucket=outputs["ArchiveBucketName"], Key=o["key"])["ContentLength"] == o["bytes"] for o in study["objects"]))
    check("Authenticated MRI PNG preview", call(path + "/preview/T1").startswith(b"\x89PNG"))
    study = call(path + "/access", "PATCH", payload={"version": study["version"], "hold": False, "active": False, "max_hours": 48, "reason": "Synthetic deployment test"})["study"]
    study = call(path + "/recommend", "POST", payload={"version": study["version"], "horizon": 120, "accesses": 0})["study"]
    study = call(path + "/placement", "POST", payload={"version": study["version"], "reason": "Synthetic S3 tag and pending-state verification"})["study"]
    check("Cold placement keeps observed Standard pending", study["placement_status"] == "PENDING" and all(o["tier"] == "STANDARD" for o in study["objects"]))
    check("Real S3 requested tier tags", all(any(t["Key"] == "tier" and t["Value"] == study["requested_tier"] for t in s3.get_object_tagging(Bucket=outputs["ArchiveBucketName"], Key=o["key"])["TagSet"]) for o in study["objects"]))
    # Cancel cold requests immediately; synthetic QA objects remain available in Standard.
    study = call(path + "/access", "PATCH", payload={"version": study["version"], "hold": True, "active": False, "max_hours": 0, "reason": "Keep synthetic deployment fixture hot"})["study"]
    check("Access hold cancels cold Lifecycle request", study["requested_tier"] == "STANDARD")
    study = call(path + "/restore", "POST", payload={"version": study["version"]})["study"]
    check("Complete hot bundle availability observed", study["restore"] == "AVAILABLE")
    if args.analyze:
        study = call(path + "/analyze", "POST", payload={"version": study["version"], "preprocessed": True})["study"]
        print("Waiting for CPU synthetic MRI compatibility analysis...", flush=True)
        for _ in range(180):
            time.sleep(5)
            study = call(path)["study"]
            if study["analysis"]["status"] != "RUNNING": break
        check("Pinned pretrained MRI worker completed", study["analysis"]["status"] == "READY")
        evidence["analysis"] = study["analysis"]
        check("Authenticated prediction overlay", call(path + "/preview/T1?overlay=WT").startswith(b"\x89PNG"))
    check("Audit records AWS actor and observed events", any(e["details"].get("mode") == "AWS" and e["details"].get("actor") not in (None, "local") for e in call(path)["events"]))
    (folder / "smoke-evidence.json").write_text(json.dumps(evidence, indent=2))
    print("Evidence saved to " + str(folder / "smoke-evidence.json"), flush=True)

if __name__ == "__main__": main()
