# V2 pilot cost model

The previous $1/month estimate described an older serverless prototype and is
retired. It does not cover the current study API, working MRI files or CPU model.

The pilot defaults to m7i-flex.large (2 vCPU, 8 GiB), and
60 GiB encrypted gp3. Compute at $0.09576/hour is approximately $69.90 for 730 hours.
EBS, public IPv4, S3 versions/requests, backup copies, Lambda gateway requests, Cognito and logs
are additional charges. Free Tier or promotional credits are not assumed.
Actual rates and credits must be checked in the account's billing console.

Sources: [EC2 on-demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS pricing](https://aws.amazon.com/ebs/pricing/),
[public IPv4 pricing](https://aws.amazon.com/vpc/pricing/),
[S3 pricing](https://aws.amazon.com/s3/pricing/).

The $100 monthly AWS Budget is an alert threshold, not a hard limit. Email alerts
require `-NotificationEmail`; without it the Budget can be inspected in AWS but
has no email recipient. Stop EC2 using `aws/operate.ps1 -Action Stop` when idle.
Retained disks, S3 data and versions continue to incur charges when EC2 is stopped
or the stack is deleted.

The dashboard's per-study comparisons use a checked-in engineering price snapshot
and describe the tiered S3 source members. They exclude EC2, EBS working copies,
Standard working-cache backups, retained object versions, egress, hot previews and
other service overhead. Do not present those modeled savings as total AWS savings.
Small QA fixtures are intentionally kept in Standard after verification.

On 20 October 2026 the account rejected t3.large as ineligible for its Free Tier
plan. The replacement m7i-flex.large is eligible. Eligibility does not mean
unlimited free usage; remaining credits and plan expiry control actual charges.
The hourly rate above was verified through the AWS Pricing API.

## Executed longitudinal counterfactual

The [visit-proxy report](../architecture/LONGITUDINAL_MODEL_REPORT.md) and
[exact replay](../architecture/longitudinal_cost_replay.json) compare all Standard,
a fixed-workload policy and the fitted timing model. The model does not beat the
fixed-workload policy in the single-access scenario. With five additional
unobserved accesses per bundle, its selected cold tiers cost more than Standard.
The live 18.4 MB research sample has a real Glacier placement request, still
pending at verification; no measured savings or archived retrieval are claimed.
