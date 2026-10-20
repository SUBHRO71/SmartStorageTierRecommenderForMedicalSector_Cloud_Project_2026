"""Import the permitted small sample, forecast, and request reviewed pilot placement."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import boto3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))
from temporal_forecast import forecast


def main():
    out = ROOT / "temp/aws-v2"
    outputs = json.loads((out / "outputs.json").read_text())
    login = json.loads((Path(os.environ["LOCALAPPDATA"]) / "CloudTierRecommender/aws-v2/admin-login.json").read_text())
    session = boto3.Session(region_name="us-east-1")
    if session.client("sts").get_caller_identity()["Account"] != "657878533811":
        raise RuntimeError("Unexpected AWS account")
    token = session.client("cognito-idp").admin_initiate_auth(UserPoolId=outputs["UserPoolId"], ClientId=outputs["UserPoolClientId"], AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": login["username"], "PASSWORD": login["password"]})["AuthenticationResult"]["IdToken"]

    def call(path, payload=None, method=None):
        request = urllib.request.Request(outputs["ApiUrl"]+path, data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer "+token, "Content-Type": "application/json"}, method=method or ("POST" if payload is not None else "GET"))
        with urllib.request.urlopen(request, timeout=130) as response: return json.loads(response.read())

    folder = ROOT / "dataset/raw/longitudinal/lumiere/aws_sample"
    context = json.loads((folder / "context.json").read_text())
    existing = [s for s in call("/archive/studies")["studies"] if s["collection"] == "LUMIERE longitudinal research pilot" and s["subject"] == context["subject"]]
    if existing:
        if len(existing) != 1: raise RuntimeError("Ambiguous pilot studies")
        study = existing[0]
    else:
        roles = {"ct1": "T1ce", "t1": "T1", "t2": "T2", "flair": "FLAIR"}
        files = [{"role": roles[item["name"].split('_')[0]], "name": item["name"], "body": (folder/item["name"]).read_bytes()} for item in context["manifest"]]
        import pandas as pd
        demographics = pd.read_csv(ROOT / "dataset/raw/longitudinal/lumiere/LUMIERE-Demographics_Pathology.csv")
        patient = demographics[demographics.Patient == context["subject"]].iloc[0]
        clinical = f"subject_id,diagnosis,age,sex\n{context['subject']},Publisher research cohort,{patient['Age at surgery (years)']},{patient['Sex']}\n".encode()
        files.append(dict(role="clinical", name="clinical.csv", body=clinical))
        ticket = call("/archive/uploads", dict(subject=context["subject"], collection="LUMIERE longitudinal research pilot", license=context["permission"],
            release="Imaging-v202211; DeepBraTumIA atlas skull-stripped volumes; "+context["timepoint"],
            files=[dict(role=f["role"], name=f["name"], size=len(f["body"])) for f in files]))
        for f, upload in zip(files, ticket["uploads"]):
            with urllib.request.urlopen(urllib.request.Request(upload["url"], data=f["body"], headers={"Content-Type": "application/octet-stream"}, method="PUT"), timeout=120) as response:
                if response.status != 200: raise RuntimeError("Source upload failed")
        call(f"/archive/uploads/{ticket['id']}/commit", {})
        for _ in range(100):
            result = call(f"/archive/uploads/{ticket['id']}")
            if result["status"] != "PROCESSING": break
            time.sleep(2)
        if result["status"] != "DONE": raise RuntimeError(str(result))
        study = result["study"]
    path = "/archive/studies/"+study["id"]
    masks = {k: context[k] for k in ("log_mask_volume", "enhancing_fraction", "edema_fraction")}
    anchor = "2026-10-20"
    payload = dict(version=study["version"], cohort="LUMIERE", history_days=context["history_days"], mask_features=masks, scenario_anchor_date=anchor, enable_storage_scenario=True)
    study = call(path+"/forecast", payload)["study"]
    local = forecast(context["history_days"], "LUMIERE", masks, anchor)
    for key in ("model_sha256", "probability_90d", "median_days", "scenario_predicted_date"):
        if study["forecast"][key] != local[key]: raise AssertionError("Local/cloud forecast mismatch: "+key)
    study = call(path+"/access", dict(version=study["version"], hold=False, active=False, max_hours=12,
        reason="Explicit non-commercial research pilot: complete sample may wait up to 12 hours; experimental first-event scenario"), method="PATCH")["study"]
    study = call(path+"/placement", dict(version=study["version"], reason="Apply experimental 90-day proxy-cost choice to this permitted research sample only"))["study"]
    s3 = session.client("s3")
    observed = []
    for obj in study["objects"]:
        tags = {t["Key"]: t["Value"] for t in s3.get_object_tagging(Bucket=obj["bucket"], Key=obj["key"])["TagSet"]}
        head = s3.head_object(Bucket=obj["bucket"], Key=obj["key"])
        if tags["tier"] != study["requested_tier"] or head["Metadata"]["sha256"] != obj["sha256"]:
            raise AssertionError("S3 tag or integrity mismatch")
        observed.append(dict(key=obj["key"], bytes=head["ContentLength"], requested_tier=tags["tier"], observed_tier=head.get("StorageClass", "STANDARD")))
    evidence = dict(study_id=study["id"], frontend_url=outputs["FrontendUrl"].rstrip('/')+"/studies/"+study["id"],
                    subject=context["subject"], timepoint=context["timepoint"], forecast=study["forecast"],
                    decision=study["decision"], placement_status=study["placement_status"], objects=observed,
                    checks=["Cognito authenticated import", "Four real publisher-processed NIfTI volumes", "Exact source clinical ID join", "Local/cloud model checksum and predictions agree", "S3 source checksums and Lifecycle tags verified"],
                    limitation="Lifecycle transition is asynchronous. No actual archived retrieval or proactive scheduled restore verified. Hot EBS preview cache remains.")
    (out / "longitudinal-pilot-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__": main()
