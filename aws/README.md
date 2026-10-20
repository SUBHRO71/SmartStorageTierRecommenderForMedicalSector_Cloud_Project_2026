# AWS study archive v2

The active deployment runs the current MRI study dashboard and study API.
The old X-ray SAM deployment is retired; its reference files are in `legacy/`.

Read the [deployment plan](../architecture/AWS_V2_DEPLOYMENT.md) for scope,
architecture, costs, recovery boundaries and acceptance checks. Read
[DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md) for the actual deployment result.

## Deploy

Prerequisites: AWS CLI credentials, Python with boto3, Node/npm, and cfn-lint.
The default target is the reviewed account `657878533811`, region `us-east-1`.
The script rejects an unexpected account. No keys are included in releases.

```powershell
./aws/deploy.ps1
```

The script builds the frontend, generates/validates CloudFormation, packages only
approved application source and built assets, provisions the stack, checks the
server, and creates `archive-admin` without sending email. Its generated password
is stored outside the project at `%LOCALAPPDATA%/CloudTierRecommender/aws-v2/admin-login.json`, restricted to the current OS
user. Sign in with username `archive-admin` and that password. Existing administrator
passwords are preserved on redeployment.

Optional `-NotificationEmail` configures Budget and server alarm notifications.
SNS subscription emails require confirmation. Without an address the Budget and
alarm still exist but have no email recipient. Budget alerts do not cap spending.

The catalog, append-only events, MRI working files and model checkpoint use
encrypted EBS. S3 holds the source imaging members and daily backup/cache copies.
S3 Lifecycle transitions use requested tags; member classes/restores are observed
every five minutes. Working files remain available for previews and inference
independently of the S3 source storage class. Costs in the UI describe S3 source
members only and exclude the server, working cache and backup copies.

## Operate

```powershell
./aws/operate.ps1 -Action Status
./aws/operate.ps1 -Action Stop
./aws/operate.ps1 -Action Start
./aws/operate.ps1 -Action Backup
```

Stop the server when unused to avoid compute charges. EBS/S3 charges continue.
The Lambda gateway uses the private server address, so a public IP change after stop/start does not
change the endpoint. SSM provides administration; there is no inbound SSH.

The default instance is m7i-flex.large (eligible under the current account plan) with 60 GiB encrypted
gp3. This is a single-server research pilot. The root EBS volume and archive bucket
are retained on deletion; no automatic destructive cleanup is provided. Daily
catalog backups retain 30 days; source objects and noncurrent versions are retained.
Check the backup timer and exercise recovery before relying on this pilot for data.

## Verify

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cfn-lint aws/template.yaml
```

`build_template.py` generates the checked-in CloudFormation template. Never edit
generated template fields without updating that source. `smoke.py` performs signed
live checks with a generated synthetic study; it never uploads local medical files.

CloudFront is unavailable until AWS verifies this account. The active template
uses a Lambda Function URL with AWS-managed HTTPS. The frontend and API share this endpoint. Large imports upload through
short-lived, size-bound S3 URLs and owner-bound asynchronous import jobs.
