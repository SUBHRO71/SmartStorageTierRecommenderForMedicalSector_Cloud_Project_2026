# Study archive AWS deployment

## Scope and account

Replace the active v1 X-ray deployment with the v2 study archive in account
657878533811, us-east-1. Inspection on 20 October 2026 found no CloudFormation
stacks or CloudFront distributions in that region/account, and no project-tagged
resources. The unrelated existing S3 bucket must not be removed. Preserve the old
implementation under aws/legacy for historical tests and uncommitted fixes; it is
not an active deployment target.

## Implementation plan

1. Retire X-ray browser routes and the old SAM deployment entry point.
2. Serve the existing study API and frontend together on an EC2 pilot server.
   Use one Gunicorn process with threads: SQLite transactions and the background
   MRI worker require a single writer/worker owner. Serialize MRI execution.
3. Use Cognito ID tokens with issuer, signature, expiry, token-use and app-client
   validation. Allow viewer reads; require operator/archive-admin for all writes.
   Forward tokens for both requests and private preview images.
4. Store metadata/audit and working MRI files on encrypted EBS. Upload validated
   source members to private encrypted versioned S3 before committing imports.
   Keep the EBS working copy for MRI inspection; savings figures cover S3 only.
5. Persist operation intent before changing S3. Apply tag-based Lifecycle for cold
   placement, copy restored objects for hotter placement, and reconcile each member
   with HeadObject. Record partial failures and restore pending states explicitly.
6. Provision EC2, IAM, private S3, Cognito, a Lambda HTTPS gateway, log retention,
   alarms and an AWS Budget with CloudFormation. No inbound SSH. Use SSM for
   deployment/diagnostics. Require IMDSv2. Keep API/preview caching disabled.
7. Build a whitelist-only release (never local databases, credentials, real images
   or model caches), upload it, install the pinned MRI checkpoint on the server,
   and verify HTTPS, authentication, imports, previews and S3 member state.

## Account-compatible HTTPS architecture

The account rejected CloudFront distribution creation with an explicit AWS account
verification requirement. This restriction is independent of IAM AdministratorAccess.
The deployable implementation therefore uses a Lambda Function URL for AWS-managed
HTTPS, with a small gateway inside the VPC forwarding to the private EC2 address.
The server security group accepts only the gateway's security group. No public
HTTP or SSH access is enabled. The gateway has no S3 permissions; Cognito validation
and roles remain enforced by the study application.

Large imports use role-protected upload tickets and short-lived, size-bound SigV4
S3 PUT URLs. The browser uploads directly to private S3 staging, then submits an
owner-bound import job. The server validates source sizes and files asynchronously,
uploads final source members, commits catalog state and removes staging objects.
Interrupted imports are marked failed on startup. Staging versions expire after a
day. Files remain bounded to 512 MiB total. The HTTPS gateway buffers responses up
to 4 MiB; source MRI bytes do not traverse it. API inventory pagination is a future
scale requirement. CloudFront can be reconsidered after AWS Support verification.

The current template contains no CloudFront resources.

## Pilot storage and recovery limits

Browser -> Lambda Function URL HTTPS -> private VPC connection -> Nginx -> Flask/Gunicorn.
Cognito protects API calls; EC2 instance-role credentials access the archive bucket.
The server has a public IPv4 address for package downloads and SSM egress, but its
only inbound rule permits the Lambda gateway security group. Frontend configuration is
public runtime configuration, containing no credentials.

This is a single-server research pilot, not a hospital production deployment.
SQLite and working files are backed up to a separate S3 prefix using SQLite's
online backup API. A retained EBS volume and versioned S3 preserve data on stack
deletion; replacement/recovery requires restoring that backup. Retained data still
incurs charges. Do not scale to multiple API servers without migrating state/jobs.
Raw DICOM conversion, registration and brain extraction remain offline prerequisites.
No real patient data is uploaded by deployment or smoke tests.

## Cost and operations

Default m7i-flex.large provides 2 vCPU/8 GiB for CPU MRI and is eligible for this
account's restricted Free Tier plan. AWS Pricing API returned $0.09576/hour, or
about $69.90 per 730-hour month before applicable credits. EBS (60 GiB gp3), public IPv4, S3, Lambda gateway
requests, Cognito and logs are additional. No unlimited Free Tier assumption is made.
Flex CPU capacity may vary under sustained analysis. Stop EC2 when
unused; storage and some other charges continue. A $100 monthly Budget is an alert,
not a spending cap. Configure a real email through the deployment parameter for
notifications; deployment does not send account invitations.

Deployment: `aws/deploy.ps1`. Outputs include HTTPS URL, Cognito IDs and instance ID.
Deployment creates the `archive-admin` user with message delivery suppressed and saves
a generated password to `%LOCALAPPDATA%/CloudTierRecommender/aws-v2/admin-login.json`, restricted to the current OS user.
Use Cognito administration to add further users and assign viewer/operator/archive-admin.
No email is sent. Rotate the initial password after first use.
Use `aws/operate.ps1 -Action Stop|Start|Status|Backup` for the pilot server.

The initial t3.large launch was rejected by the account's Free Tier restriction.
The failed stack was rolled back and its empty retained bucket removed before
retrying with the eligible m7i-flex.large. No account-plan upgrade is performed.

## Acceptance evidence

Record actual results and cloud identifiers in aws/DEPLOYMENT_STATUS.md. A running
stack alone does not establish that model inference, authentication or storage
transitions were verified. S3 Lifecycle is asynchronous; Standard-IA uses a 30-day
age rule and small objects are kept hot. Record observed state separately from
requested placement. Synthetic fixtures never establish clinical validity.

## Longitudinal research extension

The [executed model report](LONGITUDINAL_MODEL_REPORT.md) describes the subsequent
TCGA metadata/LUMIERE training experiment and explicitly enabled 90-day proxy
cost scenario. A separate pilot script imported four real LUMIERE volumes into
private S3; ordinary deployment and synthetic smoke checks still do not acquire
patient images. The broad uncertainty and absent retrieval ground truth prevent
a claim of validated retrieval prediction or general automatic archival.
