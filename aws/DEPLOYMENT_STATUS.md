# AWS v2 deployment status

Latest extension verified: 21 October 2026. The conditional next-visit research
pilot is deployed; [executed model report](../architecture/LONGITUDINAL_MODEL_REPORT.md).
The original deployment checks below were recorded at 17:32 IST.

## Project guide extension (21 October 2026)

- Added authenticated `/project/architecture`, `/project/models`, `/project/aws` and `/project/demo` pages with a sidebar entry.
- Six-stage animated architecture walkthrough, sortable saved 12-family local comparison, deployed artifact roles, official pricing links and infrastructure baseline assumptions.
- Teacher checklist includes a live catalog preflight and persists progress within the browser session. See [classroom walkthrough](../architecture/TEACHER_DEMO.md).
- Study detail can re-run the saved historical forecast through the existing authenticated/versioned API, preserving inputs and storage scenario.
- Frontend production build and 17 targeted archive/forecast tests pass. Guide and model controls checked in the live browser.
- Live browser forecast re-run succeeded with unchanged probabilities/date and a new VISIT_PROXY_FORECAST audit event. Checklist persistence and reset verified.
- Read-only S3 check still observed all four pilot members as STANDARD; Glacier request pending. No cold retrieval claim is added.

## Longitudinal pilot extension

- TCGA MRI metadata contributes 223 known next-visit intervals; LUMIERE contributes 498.
- Locked subject-separated test: 118 intervals from 25 labelled subjects. Timing MAE 44.2 days; 90-day accuracy 63.6%, versus majority baseline 64.4%. These are conditional visit-proxy results, not retrieval accuracy.
- Logistic baseline reaches 66.9% 90-day accuracy. No strong predictive accuracy or ML cost advantage is claimed.
- Four real LUMIERE publisher-processed volumes, 18,404,657 bytes, imported to private S3 for study `ST-8B325CB5D201`. This extends the earlier synthetic-only deployment.
- The fitted portable forest is included in the release. Local/cloud checksums and predictions match.
- Sample scenario: median 98 days, 10–90% interval 28–203 days; anchor 2026-10-20 produces scenario date 2027-01-26.
- S3 Lifecycle tags request GLACIER under an explicit 12-hour research tolerance. All four members were still observed STANDARD, placement PENDING, at verification. Actual cold retrieval remains unverified.
- 49 automated tests and the frontend build pass. Browser verification shows real MRI previews, the labeled experimental forecast and storage recommendation.
- Counterfactual cost savings depend on an unverified one-access assumption and do not beat the fixed-workload policy. Additional retrievals can reverse the apparent savings; no total-account savings are established.

## Original deployment verification

**Status: deployed and verified.** Stack `cloudtier-v2` is `UPDATE_COMPLETE` in account `657878533811`, `us-east-1`.

[Open the study archive](https://dbfq563k4fadil4rqn4taz653e0mbpar.lambda-url.us-east-1.on.aws/)

| Resource | Identifier |
| --- | --- |
| InstanceId | `i-03e4ae914ce61d333` |
| ArchiveBucketName | `cloudtier-v2-archivebucket-wflgqziprz0e` |
| GatewayFunctionName | `cloudtier-v2-Gateway-UNTBVsEB6Duh` |
| UserPoolId | `us-east-1_t73sSN4He` |
| UserPoolClientId | `7puabfjq7c5r6k6k2m7g07s9cb` |

Current published release: `releases/0c06921d4159ee9e92ab.tgz`.
Original deployment release: `releases/75669a3cb4f62c4caec5.tgz`.

## Login

Username: `archive-admin`. The generated password is stored outside the repository at
`C:/Users/Subhr/AppData/Local/CloudTierRecommender/aws-v2/admin-login.json`, restricted
to the current OS user. No password is committed and no email was sent. Existing
credentials were preserved during the final redeployment.

## Verification

- 43 automated Python tests passed, including token/role checks, direct upload ownership and size bounds, S3 requested/observed state, partial failures, restore gating, and a local consistent backup test.
- Frontend production build, CloudFormation validation and whitespace checks passed.
- Release inspection confirmed no credentials, local databases, raw medical files, cached weights or old Lambda deployment code.
- 16 initial live checks passed using generated synthetic MRI volumes. The later longitudinal extension separately imported the permitted LUMIERE sample described above.
- Browser Cognito sign-in, AWS dashboard, authenticated MRI PNG rendering and the corrected S3 action label were verified.
- The study and completed model output persisted across the final redeployment.

Live checks:

- HTTPS health
- Unauthenticated API denied
- Cognito authenticated catalog
- Legacy API retired
- Browser direct-upload CORS
- Asynchronous direct S3 import completed
- Four-volume import and exact clinical join
- All source members exist in private S3
- Authenticated MRI PNG preview
- Cold placement keeps observed Standard pending
- Real S3 requested tier tags
- Access hold cancels cold Lifecycle request
- Complete hot bundle availability observed
- Pinned pretrained MRI worker completed
- Authenticated prediction overlay
- Audit records AWS actor and observed events

## Model evidence

Synthetic fixture: `ST-90380FA637BF`. Four generated 32 x 32 x 32 volumes with 1 mm spacing.
MONAI BraTS SegResNet 0.5.4 completed on CPU in 1.96 seconds.
Checkpoint SHA-256: `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`.
This is compatibility evidence only; it establishes no clinical accuracy.

## Account restrictions and cleanup

The account rejected t3.large under its restricted Free Tier plan. The deployed
m7i-flex.large is eligible under that plan and provides 8 GiB RAM. AWS Pricing API
returned $0.09576/hour (about $69.90/month continuously running), before credits
and other services. A $100 monthly Budget and instance health alarm exist;
no email recipient was configured. The Budget is not a spending cap.

CloudFront distribution creation was denied pending AWS account verification.
The deployed application uses a Lambda Function URL with AWS-managed HTTPS and
a private VPC connection instead. No billing-plan upgrade or support request was
submitted. Failed stacks, their empty archive buckets, the unattached failed
system disk and temporary VPC origin were removed. The unrelated existing bucket
`aws-haas-hazel-demo-2026` was not changed.

## Remaining verification and pilot limits

- Live archive transitions remain asynchronous. The smoke test verified real S3 tags and pending state, then cancelled the cold request with a hold. The fixture remains in Standard.
- Actual Glacier retrieval was not performed. Restore handling was tested with unit fixtures and live availability of the complete hot bundle.
- Scheduled backup units are installed. Snapshot/copy logic passed a local test with mocked S3. Automatic approval review blocked the manual live backup invocation, returning only "blocked by policy". No live backup execution or disaster recovery is claimed.
- One initial startup health probe raced the Gunicorn listener and returned 502. Readiness checks subsequently passed; the final published bootstrap retries the probe.
- This is a single-server pilot. Working MRI files remain on encrypted EBS, with separate S3 cache backups excluded from modeled tier savings. Root EBS and archive data are retained on stack deletion.
- Raw controlled-access TCGA pixels, raw DICOM preprocessing, actual retrieval-log evaluation and independent external validation remain outside this deployment. The internal conditional visit-proxy holdout is documented separately.

## Operations

Use `aws/operate.ps1 -Action Stop` when idle; storage charges continue.
Use `aws/operate.ps1 -Action Start` to resume the same HTTPS endpoint.
Use `aws/operate.ps1 -Action Backup` for a manual backup when that action is permitted.
The deployment plan is [architecture/AWS_V2_DEPLOYMENT.md](../architecture/AWS_V2_DEPLOYMENT.md).
Detailed generated evidence is saved locally under ignored `temp/aws-v2/`.
