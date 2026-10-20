"""Build a whitelist-only release, provision the v2 stack, and verify readiness."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]

def release():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        paths = list((ROOT / "src/backend").glob("*.py"))
        paths += [ROOT / "src/backend/requirements.txt", ROOT / "src/ml_model/mri_inference.py",
                  ROOT / "src/ml_model/requirements_mri.txt", ROOT / "src/ml_model/retrieval_policy_weights.json"]
        paths += [ROOT / "src/ml_model/longitudinal_model.json"]
        paths += [ROOT / "aws" / name for name in ("bootstrap.sh", "requirements-cloud.txt", "backup.py")]
        paths += [p for p in (ROOT / "src/frontend/dist").rglob("*") if p.is_file()]
        if not any(p.name == "index.html" for p in paths):
            raise RuntimeError("Build the frontend before deployment")
        for path in sorted(paths):
            data = path.read_bytes()
            if path.suffix in (".sh", ".py", ".txt"):
                data = data.replace(b"\r\n", b"\n")
            info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()

def outputs(cf, stack):
    return {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]}

def command(ssm, instance, commands, timeout=1800):
    identifier = ssm.send_command(InstanceIds=[instance], DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands, "executionTimeout": [str(timeout)]}, TimeoutSeconds=timeout)["Command"]["CommandId"]
    deadline = time.monotonic() + timeout + 60
    while time.monotonic() < deadline:
        time.sleep(10)
        try:
            result = ssm.get_command_invocation(CommandId=identifier, InstanceId=instance)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if result["Status"] == "Success":
            return result.get("StandardOutputContent", "")
        if result["Status"] in ("Failed", "Cancelled", "TimedOut"):
            raise RuntimeError("SSM command failed: " + result.get("StandardErrorContent", "")[-2500:])
    raise TimeoutError("Server command timed out; inspect SSM command " + identifier)

def create_admin(cognito, pool, directory):
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "CloudTierRecommender/aws-v2"
    directory.mkdir(parents=True, exist_ok=True)
    username = "archive-admin"
    path = directory / "admin-login.json"
    try:
        cognito.admin_get_user(UserPoolId=pool, Username=username)
        print("Existing administrator preserved; its password was not reset.", flush=True)
        return path if path.exists() else None
    except cognito.exceptions.UserNotFoundException:
        pass
    password = "Aa1!" + secrets.token_urlsafe(24)
    cognito.admin_create_user(UserPoolId=pool, Username=username, MessageAction="SUPPRESS", TemporaryPassword=password)
    cognito.admin_set_user_password(UserPoolId=pool, Username=username, Password=password, Permanent=True)
    cognito.admin_add_user_to_group(UserPoolId=pool, Username=username, GroupName="archive-admin")
    path.write_text(json.dumps({"username": username, "password": password, "pool_id": pool}, indent=2))
    if os.name == "nt":
        principal = subprocess.check_output(["whoami"], text=True).strip()
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:(F)"], check=True, capture_output=True)
    else:
        path.chmod(0o600)
    print(f"Administrator login saved to {path}; no email sent.", flush=True)
    return path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--stack", default="cloudtier-v2")
    parser.add_argument("--expected-account", default="657878533811")
    parser.add_argument("--notification-email", default="")
    args = parser.parse_args()
    session = boto3.Session(region_name=args.region)
    account = session.client("sts").get_caller_identity()["Account"]
    if account != args.expected_account:
        raise RuntimeError("Configured AWS account differs from the reviewed deployment account")
    cf, ec2, s3 = (session.client(s) for s in ("cloudformation", "ec2", "s3"))
    instance = ec2.describe_instance_types(InstanceTypes=["m7i-flex.large"])["InstanceTypes"][0]
    if not instance.get("FreeTierEligible") or instance["MemoryInfo"]["SizeInMiB"] < 8192:
        raise RuntimeError("The reviewed 8 GiB, Free Tier eligible server type is unavailable")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("A default VPC with internet egress is required for this pilot")
    vpc = vpcs[0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}])["Subnets"]
    subnet = next(s["SubnetId"] for s in sorted(subnets, key=lambda s: s["AvailabilityZone"]) if s["MapPublicIpOnLaunch"])
    artifact = f"{args.stack}-releases-{account}-{args.region}"
    try:
        s3.head_bucket(Bucket=artifact)
    except ClientError as error:
        if error.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
        config = {"CreateBucketConfiguration": {"LocationConstraint": args.region}} if args.region != "us-east-1" else {}
        s3.create_bucket(Bucket=artifact, **config)
    s3.put_public_access_block(Bucket=artifact, PublicAccessBlockConfiguration={k: True for k in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")})
    s3.put_bucket_encryption(Bucket=artifact, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    data = release()
    key = "releases/" + hashlib.sha256(data).hexdigest()[:20] + ".tgz"
    s3.put_object(Bucket=artifact, Key=key, Body=data)
    params = {"VpcId": vpc, "SubnetId": subnet, "ArtifactBucket": artifact, "ReleaseKey": key, "NotificationEmail": args.notification_email}
    request = {"StackName": args.stack, "TemplateBody": (ROOT / "aws/template.yaml").read_text(), "Parameters": [{"ParameterKey": k, "ParameterValue": v} for k, v in params.items()], "Capabilities": ["CAPABILITY_IAM"], "Tags": [{"Key": "Project", "Value": "CloudTierRecommender-v2"}]}
    try:
        cf.describe_stacks(StackName=args.stack)
        existing = True
    except ClientError as error:
        if "does not exist" not in str(error): raise
        existing = False
    if existing:
        try:
            cf.update_stack(**request)
        except ClientError as error:
            if "No updates are to be performed" not in str(error): raise
    else:
        cf.create_stack(**request)
    print(f"Provisioning {args.stack} in {account}/{args.region}; release {key}.", flush=True)
    previous = None
    for _ in range(160):
        stack = cf.describe_stacks(StackName=args.stack)["Stacks"][0]
        status = stack["StackStatus"]
        if status != previous:
            print(status, flush=True); previous = status
        if status in ("CREATE_COMPLETE", "UPDATE_COMPLETE"): break
        if "FAILED" in status or "ROLLBACK" in status:
            events = cf.describe_stack_events(StackName=args.stack)["StackEvents"]
            raise RuntimeError(json.dumps([{k: e.get(k) for k in ("LogicalResourceId", "ResourceStatus", "ResourceStatusReason")} for e in events if "FAILED" in e["ResourceStatus"]], indent=2))
        time.sleep(15)
    else: raise TimeoutError("CloudFormation provisioning timed out")
    out = outputs(cf, args.stack)
    directory = ROOT / "temp" / "aws-v2"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "outputs.json").write_text(json.dumps(out, indent=2))
    ssm = session.client("ssm")
    for _ in range(80):
        instances = ssm.describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [out["InstanceId"]]}])["InstanceInformationList"]
        if instances and instances[0]["PingStatus"] == "Online": break
        time.sleep(15)
    else: raise TimeoutError("Server did not register with SSM")
    if existing:
        command(ssm, out["InstanceId"], ["set -eu", "systemctl stop cloudtier", f"aws s3 cp s3://{artifact}/{key} /tmp/release.tgz --region {args.region}", "tar -xzf /tmp/release.tgz -C /opt/cloudtier", "bash /opt/cloudtier/aws/bootstrap.sh"])
    print("Waiting for package installation and model readiness...", flush=True)
    command(ssm, out["InstanceId"], ["set -eu", "for attempt in $(seq 1 120); do if curl -sf http://127.0.0.1/api/health; then exit 0; fi; sleep 15; done; tail -60 /var/log/cloud-init-output.log; exit 1"])
    print(urllib.request.urlopen(out["ApiUrl"] + "/health", timeout=30).read().decode(), flush=True)
    create_admin(session.client("cognito-idp"), out["UserPoolId"], directory)
    print(json.dumps(out, indent=2), flush=True)

if __name__ == "__main__": main()
