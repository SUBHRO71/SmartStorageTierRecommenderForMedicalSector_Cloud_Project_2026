# AWS implementation

`template.yaml` is the deployable SAM/CloudFormation source of truth. It creates:

- a private, encrypted, versioned medical-image bucket with tag-filtered Lifecycle rules;
- a private frontend bucket served through CloudFront Origin Access Control;
- DynamoDB scan-state and append-only decision-audit tables with point-in-time recovery;
- Cognito user pool, web client, and `viewer`, `archive-admin`, and `operator` groups;
- API Gateway with a Cognito authorizer;
- API and inference/reconciliation Lambda functions with scoped policies;
- an EventBridge schedule, CloudWatch custom metrics/logs, and an SNS restore-event topic.

## Credential-free checks

```powershell
python aws/lambda/api_handler/build_package.py
python aws/lambda/tier_inference/build_package.py
cfn-lint aws/template.yaml
python -m unittest discover -s tests -p "test_*.py" -v
```

The Lambda bundles include the shared pure-Python decision engine and policy JSON. PyTorch and model weights are not packaged because image scores are extracted before upload.

## Deploy

Configure an AWS CLI profile, SSO session, or temporary environment credentials. SDK code uses the standard AWS chain and Lambda execution roles; no key is read from a committed file.

Create a low AWS Budget alert in the intended account, then run:

```powershell
.\aws\deploy.ps1 -Region us-east-1 -StackName smart-storage-tier -NotificationEmail you@example.com
```

The script validates the caller, creates/reuses an artifact bucket, builds and packages Lambda code, deploys the stack, derives an ignored Vite production environment from outputs, builds `dist/`, uploads it, and invalidates CloudFront.

## Ingest a scan

First extract scores using the published weights:

```powershell
python src/ml_model/extract_pretrained_features.py path\to\xray.png --output temp\features.json
```

Preview the cloud registration without changing AWS:

```powershell
python aws/ingest_scan.py path\to\xray.png --features temp\features.json --bucket STACK_IMAGE_BUCKET --table STACK_SCAN_TABLE --dry-run
```

Remove `--dry-run` after credentials and stack outputs are available. The script registers features in DynamoDB before uploading to S3, preventing the normal event from racing ahead of its input features.

## Operational behavior

- Missing feature registration records `BLOCKED_MISSING_FEATURES` and leaves the object in Standard.
- Existing S3 tags are preserved when the requested tier tag is added.
- Tier overrides require an `archive-admin` or `operator` Cognito group and a reason.
- Moves to a more accessible tier use a same-key S3 copy; archived sources must be restored first.
- Archive restores call `RestoreObject`; Standard and Standard-IA return `NOT_REQUIRED`.
- Hourly reconciliation reads S3 storage class and restore headers, updates observed state, and appends audit events.
- Standard-IA transitions begin after 30 days. Glacier tiers use immediate eligible Lifecycle transitions, which remain asynchronous.

Never commit credentials, `.env` files, generated production configuration, raw medical images, local tables, or Lambda bundles.
