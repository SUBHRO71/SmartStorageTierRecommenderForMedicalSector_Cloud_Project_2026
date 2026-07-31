# aws/

Cloud infrastructure configuration. **Primary owner: Student 2** — but every team member must
contribute here and be able to explain their own AWS integration individually at review.

## What goes here

| File | Purpose |
| --- | --- |
| `s3_lifecycle.json` | S3 lifecycle rules and storage class transitions |
| `iam_policies/` | IAM roles and policies, one file per role |
| `lambda/` | Lambda function source and deployment configuration |
| `cloudwatch/` | Metric filters, alarms, dashboard definitions |
| `infrastructure.yaml` | CloudFormation or Terraform definition, if used |
| `cost_estimates.md` | Pricing assumptions and projected monthly cost |

## Services in scope

Which of these are actually used depends on the architecture, still under discussion:

| Service | Likely role |
| --- | --- |
| **S3** | Stores the scans. The storage classes are the thing this project predicts. |
| **Lambda** | Runs the tier prediction on ingest, or on a schedule |
| **EC2** | Hosts the backend and, if needed, model training |
| **IAM** | Roles and least-privilege policies for every component |
| **CloudWatch** | Logs, metrics, and the cost/latency evidence for our results |

## Rules — the first one is not negotiable

**1. Never commit credentials.**
No access keys, no secret keys, no session tokens, no `.aws/credentials`, no `.env`. Git history is
permanent — a key committed and then deleted in a later commit is still in the repository and must
be treated as compromised and rotated immediately. Bots scan public GitHub for AWS keys within
minutes, and the bill lands on whoever owns the account.

Use environment variables locally and IAM roles in AWS. Commit `.env.example` with variable names
and empty values.

**2. Least privilege.**
Each role gets exactly the permissions it needs. Do not attach `AdministratorAccess` because it is
faster — an over-permissive policy is the kind of thing a reviewer will notice and ask about.

**3. Watch the cost.**
Free tier is limited and this project moves data between storage classes. Note that:
- S3 transitions between classes are charged **per request**
- Glacier and Deep Archive have **minimum storage durations** — deleting early still incurs a charge
- Retrieval from Deep Archive costs money **and** takes hours

These charges are exactly what our cost model must account for. The Khan et al. paper our team
reviewed omitted them, which is one of its stated limitations — we should not repeat that mistake.

**4. Set a billing alarm before doing anything else.** A CloudWatch billing alarm at a low
threshold has saved many student projects from an unpleasant surprise.

## For the individual defence

Each member must be able to say which AWS services they personally configured and explain how they
work. Record ownership here as it is decided:

| Service | Configured by |
| --- | --- |
| _TBD_ | _TBD_ |
