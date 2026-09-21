# Architecture Decision Records

Every significant design decision, why it was taken, and what was rejected.

At review, being able to explain *why an alternative was rejected* is worth as much as the design
itself. This file exists so nobody has to reconstruct that reasoning from memory three months later.

**Format:** Context → Decision → Consequences → Rejected alternatives.
**Status values:** Accepted · Superseded · Revisit.

---

## ADR-001 — Serverless only, no EC2

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Subhrojyoti Das

### Context

AWS replaced the Free Tier for new accounts on **15 July 2025**. Accounts created after that date
do **not** get 750 hours/month of free EC2 for 12 months. They get $100 in credits on signup, up to
$100 more for completing five onboarding tasks, and a **6-month clock**.

Separately, more than 30 services keep **always-free** monthly allowances that neither consume
credits nor count against the 6-month window — notably Lambda (1M requests + 400,000 GB-seconds),
DynamoDB (25 GB, 25 RCU/WCU) and CloudFront.

We have zero budget and no institutional AWS account.

### Decision

Build entirely on serverless services. **No EC2, no RDS, no always-on compute of any kind.**

Compute is Lambda. Storage is S3 and DynamoDB. The API is API Gateway. The dashboard is an S3
static website. Model training happens locally or in Google Colab, not in AWS.

### Consequences

- **Zero idle cost.** Nothing accrues charges when nobody is using the system.
- A forgotten resource cannot drain the credits — the most common way student projects overspend.
- Lambda's deployment package limit forces the embedding work offline, which turns out to be the
  right design anyway (see [ADR-002](#adr-002--precompute-image-embeddings-offline)).
- **No cloud GPU.** Training must fit on a laptop or Colab's free tier.
- If the course rubric explicitly requires an EC2 component for marks, this decision must be
  revisited — flagged as an open item.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| EC2 `t3.micro` for the backend | No longer free for post-July-2025 accounts; accrues cost around the clock; easy to forget |
| RDS for metadata | Same idle-cost problem; DynamoDB's always-free tier covers our needs entirely |
| SageMaker for training/hosting | Not in the free tier in any meaningful way; would consume the whole credit balance |
| ECS / Fargate | Idle cost, and far more operational complexity than this project justifies |

---

## ADR-002 — Precompute image embeddings offline

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Mehul Anand

### Context

The system needs features derived from the image itself — that is the entire premise of the
project. But a CNN plus its framework does not fit comfortably in a Lambda deployment package
(250 MB unzipped for a zip-based function), and container-image Lambdas add ECR storage and
cold-start cost.

Meanwhile the image content of a scan **never changes**. Recomputing an embedding on every
invocation would be pure waste.

### Decision

Split the model in two, along the axis of what changes:

- **Offline, once, free:** run MobileNetV3 over every image in Colab, producing a 128-dimensional
  embedding per scan. Store the vectors in DynamoDB.
- **Online, per request:** Lambda loads only the small Stage-1 classifier (a few hundred KB) and
  reads the embedding from DynamoDB.

### Consequences

- The Lambda package stays tiny, so cold starts stay fast and the size limit is a non-issue.
- Embedding extraction gets Colab's free GPU rather than costing anything on AWS.
- **The architecture is honest, not a workaround** — static heavy work belongs in batch, dynamic
  light work belongs in serverless.
- A newly ingested scan with no precomputed embedding needs a fallback: either predict from
  metadata alone, or queue it for the next batch. **Must be handled explicitly** in `tier_inference`.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Full CNN inside Lambda | Exceeds the zip package limit; slow cold starts |
| Lambda container image (10 GB limit) | Works, but adds ECR cost and complexity for no benefit, since embeddings are static |
| SageMaker endpoint | Always-on cost; nothing free about it |
| Skip image features, use metadata only | Would abandon the project's central claim |

---

## ADR-003 — Tag-based Lifecycle rules over direct API calls

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Subhrojyoti Das

### Context

Once the model has chosen a storage class, something has to actually move the object. Two options:
call `CopyObject` with a new storage class directly from the Lambda, or write a tag and let an S3
Lifecycle rule act on it.

### Decision

The Lambda writes an **object tag** (`tier=GLACIER`, etc.). A **tag-filtered S3 Lifecycle
configuration** performs the transition.

**The model decides policy. AWS enforces mechanism.**

### Consequences

- Clean separation of concerns, and a genuinely defensible design point at review.
- Lifecycle transitions are managed, retried and audited by AWS — our code cannot half-move an object.
- No risk of the Lambda hammering the S3 API or failing mid-transition.
- The tag is human-readable in the console, which makes the demo far easier to show.
- **Lifecycle evaluates once daily**, so transitions are not instant. Acceptable here, and worth
  stating in the report rather than glossing over.
- **Critical configuration detail:** by default, Lifecycle will **not transition objects smaller
  than 128 KB**. `transition_default_minimum_object_size` must be set explicitly, or small scans
  will silently never move and the results will be wrong in a way that is hard to spot.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Direct `CopyObject` from Lambda | Couples policy to mechanism; error handling and partial failures become our problem; no audit trail |
| S3 Batch Operations | Better for bulk one-off moves than for a continuous per-object policy |
| S3 Intelligent-Tiering | This is a *baseline we are trying to beat*, not our mechanism |

---

## ADR-004 — DynamoDB for metadata, not a relational database

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Subhrojyoti Das

### Context

The system needs to store, per scan: metadata features, a 128-dim embedding, access history, the
predicted class, the probability, and a reason string. Access is overwhelmingly key-value —
"give me everything about scan X".

### Decision

**DynamoDB.** Partition key `scan_id`. Embedding stored as a binary or number-list attribute.

### Consequences

- 25 GB and 25 RCU/WCU are **always free** — no clock, no credits consumed.
- No cluster, no idle cost, no connection pooling, nothing to leave running.
- Single-digit-millisecond lookups suit the Lambda hot path.
- Ad-hoc analytical queries are awkward. Mitigated by doing all analysis offline in pandas against
  `dataset/processed/`, which is where the analysis belongs anyway.
- Partition key design and access patterns still need to be fixed — open item.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| RDS PostgreSQL | Idle cost; no always-free tier; more than the access pattern needs |
| S3 + Athena | Query cost, and latency unsuitable for the Lambda hot path |
| DocumentDB | No free tier; heavily over-specified for this |

**Revisit if:** the course rubric explicitly requires a relational database component.

---

## ADR-005 — Two-stage model instead of a four-class classifier

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Mehul Anand

### Context

The obvious approach is a four-class classifier over the S3 storage classes. But a standard
classifier treats every misclassification as equally bad, and here they emphatically are not:

- A rarely-used scan left in Standard → we overpay slightly. Minor.
- A scan the doctor needs sent to Deep Archive → they wait up to 12 hours. Serious.

Our own research gap analysis argues that existing systems fail precisely because they treat all
mistakes as equal. A symmetric classifier would reproduce the flaw we are criticising.

### Decision

Split the decision in two:

- **Stage 1 (learned):** predict `P(scan is retrieved again)` — a probability, not a class.
- **Stage 2 (explicit rule):** choose the class minimising expected total cost:

```
expected_cost(class) =  storage_cost(class, billable_size, horizon)
                      + P * retrieval_cost(class, size)
                      + P * clinical_penalty(class)
                      + transition_cost(class)
```

`clinical_penalty` scales with retrieval latency — near zero for Standard, large for Deep Archive.

### Consequences

- **Explainable.** "P was 0.03, so expected cost was lowest in Glacier" is a defensible answer at
  review. "The softmax said so" is not.
- **The clinical penalty is tunable without retraining.** Every result can be regenerated across a
  range of penalty values, which gives the sensitivity analysis essentially for free.
- **The asymmetry lives in inspectable code**, not buried in a loss function.
- Stage 1 becomes a clean binary problem with standard metrics (AUC, calibration).
- Two components to build and validate instead of one.
- **Stage 1 must be well calibrated**, not merely accurate — the cost rule consumes the probability
  directly, so a miscalibrated model produces wrong decisions even at high accuracy. Report a
  calibration curve, not just AUC.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Four-class softmax classifier | Symmetric treatment of errors — the exact flaw our gap analysis criticises |
| Class-weighted classifier | Better, but weights must be retrained to change; less explainable |
| Reinforcement learning agent | Matches the papers we reviewed, but needs an environment to explore, and we have no live archive to explore against |

---

## ADR-006 — NIH ChestX-ray14 as the dataset

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Mehul Anand

### Context

We are students with no institutional clearance, no ethics approval, and no budget. Most useful
medical imaging datasets are gated behind credentialing or data use agreements.

Critically, **no public dataset records who retrieved which scan and when.** Those records exist
only in hospital PACS audit trails, are protected patient information, and are never released. The
label this project needs cannot be downloaded.

### Decision

**NIH ChestX-ray14.** Fully open — no registration, no credentialing, no DUA.

Derive the label from the `Follow-up #` column: if a scan's follow-up number is below the maximum
for that `Patient ID`, a later study exists, so the earlier scan was very likely retrieved for
comparison.

### Consequences

- Zero access friction. Work can start immediately.
- 112,120 images across 30,805 patients — ample scale.
- Metadata includes Patient ID, Follow-up #, Patient Age, Gender, View Position and finding labels.
- Published precedent for this exact proxy framing: Yayan et al., *Scientific Reports*, December
  2025, on metadata-derived 90-day follow-up proxies in ChestX-ray14.
- **The label is a proxy, not ground truth.** It misses retrievals with no subsequent scan — MDT
  meetings, second opinions, research requests. Must be stated in the report with a sensitivity
  analysis, not hidden.
- **No timestamps.** Only follow-up ordering and Patient Age. Intervals are approximate.
- Images are PNG, not DICOM, so real DICOM header features must be simulated from the available
  columns. State this limitation.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| MIMIC-CXR | Free but credentialed — CITI training plus a supervisor reference. Good upgrade path; do not block on it |
| TCIA | Real DICOM headers, but no follow-up structure as convenient as ChestX-ray14's |
| Real hospital PACS logs | Would need ethics approval and a clinical partner. Out of scope |
| Fully synthetic access traces | Weaker than a real, if imperfect, proxy |

---

## ADR-007 — Two-track evaluation

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Mehul Anand

### Context

The full dataset is ~45 GB. The S3 always-free allowance is 5 GB. We cannot host the whole dataset,
but we still need a credible cost result at full scale.

### Decision

Two tracks.

**Track A — cost projection, offline, $0.** Run the model over all 112,120 records and compute what
the S3 bill *would be* under each policy using AWS's published price list. **This produces the
headline result.**

**Track B — live demo, real AWS, near $0.** Upload ~1,000 real images (~400 MB, inside the free
allowance), run the real Lambda, apply real tags, trigger real Lifecycle transitions.

The report states plainly: *mechanism demonstrated at small scale, cost projected at full scale from
published rates.*

### Consequences

- Full-scale cost numbers at zero cost.
- The mechanism is genuinely proven, not just simulated.
- Scientifically legitimate and standard practice — Khan et al. did exactly this with Google Cloud
  prices on simulated data. **We do it better by including the transition and early-deletion costs
  they omitted.**
- Must be disclosed clearly. Presenting projected figures as measured would be dishonest and is
  exactly the kind of thing a reviewer probes.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Everything on real AWS at full scale | 45 GB far exceeds the free allowance; would consume the credit balance |
| Pure simulation, no deployment | No working demo; loses most of the cloud-architecture marks |
| Tiny dataset only | Cost results would be too small to be meaningful |

---

## ADR-008 — Model per-object storage overheads explicitly

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Mehul Anand

### Context

S3 archive classes carry per-object overheads that are invisible at the per-GB headline rate:

- Objects under **128 KB are billed as 128 KB** in IA and Glacier classes.
- Glacier adds **40 KB of metadata per object** — 8 KB at Standard rates, 32 KB at archive rates.
- Minimum storage durations: IA 30 days, Glacier Flexible 90 days, Deep Archive 180 days, with
  pro-rata early-deletion charges.
- Lifecycle transitions are charged per 1,000 requests.

ChestX-ray14 averages roughly 400 KB per image, so most objects clear the 128 KB floor — but the
40 KB overhead is still about a 10% tax, and the small tail is affected.

The Khan et al. paper the team reviewed **explicitly omitted** transition and early-deletion costs.
We listed that as one of its limitations.

### Decision

Model every one of these terms in `src/ml_model/evaluate.py`. Report the naive headline saving and
the overhead-corrected saving **side by side**.

### Consequences

- A genuine, concrete contribution that directly addresses a limitation we identified in the
  literature. Cheap to implement — it is arithmetic.
- Produces an interesting secondary finding: how much of the theoretical saving small objects lose
  to per-object overheads.
- Motivates a possible optimisation worth evaluating — bundling a patient's scans into a single
  archive object to clear the floor and amortise the metadata overhead.
- Makes our cost figures more conservative, and therefore more defensible, than the headline
  numbers vendors quote.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Per-GB rates only | Would reproduce the exact limitation we criticised in Khan et al. |
| Ignore minimum durations | Materially distorts any policy that moves objects frequently |

---

## ADR-009 — Add Amazon Cognito and Amazon SNS

**Status:** Accepted · **Date:** 31 July 2026 · **Owner:** Subhrojyoti Das

### Context

The course guidelines make two architecture diagrams mandatory, and specify that the AWS Cloud
Architecture diagram must show **data flow, storage, processing, authentication, notifications and
monitoring**.

Reviewing the design against that list exposed two genuine gaps, not merely diagram omissions:

- **No user authentication.** AWS IAM governs what *services* may do; it does not authenticate a
  radiologist logging into a dashboard. The dashboard had no access control at all.
- **No notification path.** The wrongly-archived rate was defined as the headline safety metric, but
  nothing told anyone when it happened. A clinician would have discovered a stranded scan by waiting
  twelve hours for it.

### Decision

Add two services:

- **Amazon Cognito** — a user pool authenticating radiologists and archive administrators, issuing
  JWTs. API Gateway is configured with a Cognito authorizer so every API call is validated before it
  reaches a Lambda.
- **Amazon SNS** — a notification topic publishing to email and SMS subscribers on archive restore
  completion, on a scan being retrieved from cold storage (and therefore logged as wrongly
  archived), on inference failure, and on the AWS Budgets threshold being crossed.

### Consequences

- The mandatory diagram requirements are satisfied by real components rather than boxes drawn to
  tick a box.
- The wrongly-archived metric becomes actionable: a mistake surfaces immediately instead of being
  discovered by a waiting clinician.
- Both stay inside the zero-budget constraint. Cognito's user pool tier covers a generous monthly
  active user count, and SNS allows 1 million publishes and 1,000 email notifications per month.
- Adds two services for each member to understand for the individual defence.
- Cognito introduces real token handling in the frontend, which is more work for
  [ADR-001](#adr-001--serverless-only-no-ec2)'s serverless model than a no-auth dashboard would be.
- SNS on every archive retrieval could become noisy at scale; a threshold or digest may be needed.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| No authentication at all | Indefensible for a system handling medical imaging, even with a public dataset |
| Hand-rolled auth in the backend | Storing password hashes ourselves is worse in every respect than a managed user pool |
| IAM users for each clinician | IAM is for service and operator identity, not application end users |
| Amazon SES instead of SNS | Email only; SNS also covers SMS and fans out to multiple subscriber types |
| CloudWatch alarms with no SNS | CloudWatch alarms need a notification target — SNS is that target |

---

## ADR-010 — Inference-only published weights; no local model training

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Mehul Anand

### Context

The project owner does not want to train or fine-tune a model. The prototype's random embeddings
and locally trained XGBoost artifact could not support the intended claim or reproduce cloud
inference reliably.

### Decision

Use TorchXRayVision's published `densenet121-res224-all` weights offline to produce pathology
scores. Do not fit a model in this repository. A checked-in, versioned fixed-weight policy combines
those scores with metadata and access counts, and a shared cost engine chooses the S3 tier. The
fixed coefficients are an engineering policy and must not be presented as clinically trained or
validated probabilities.

The online Lambda consumes precomputed pathology scores and therefore does not package PyTorch.
`train.py` intentionally exits; the earlier training experiment remains as `legacy_training.py`
for audit history.

### Consequences

- A user can run inference from published weights without a training dataset or GPU training job.
- Offline feature extraction still downloads a sizeable public weight file on first use.
- The policy is transparent and immediately testable, but its probability needs calibration before
  any clinical or autonomous archival claim.
- The architecture no longer depends on a local pickle artifact.

---

## ADR-011 — AWS code uses roles later and fails safe when features are missing

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Subhrojyoti Das

### Context

AWS credentials are not available during implementation. The earlier code inferred cloud mode from
static access-key environment variables and the inference Lambda used fabricated defaults when a
feature record was missing.

### Decision

Write and test AWS code without credentials. In Lambda, `boto3` will use temporary credentials from
the execution role. Local deployment may later use the standard AWS credential provider chain.
Never add static keys to application configuration.

Derive a stable opaque `scan_id` from the bucket and complete S3 object key, and store the bucket
and key as separate fields. If its registered DynamoDB feature record is absent, leave the object in S3 Standard and record
`BLOCKED_MISSING_FEATURES`. Preserve existing object tags when adding the requested tier, and store
the request as `PENDING_TRANSITION` until a later reconciler confirms the physical storage class.

### Consequences

- Implementation and unit tests do not wait for an AWS account.
- Missing data cannot silently send an image to archive.
- Existing DynamoDB fixtures keyed by a filename alone will need migration to the stable identifier
  before deployment.
- The scheduled reconciler now confirms observed placement and completed restores.

---

## ADR-012 — Explicit local and AWS execution modes

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Subhrojyoti Das

### Context

Implicit fallback from AWS to SQLite and from failed live HTTP requests to mock responses made a
broken integration look successful.

### Decision

Use SQLite unless `DATA_BACKEND=dynamodb` is set explicitly. Use live HTTP unless
`VITE_USE_MOCK_API=true` is set explicitly. Display the selected frontend data mode and return the
backend execution mode from `/api/health`. A live request failure is an error state.

### Consequences

- The credential-free local application remains easy to run.
- Cloud misconfiguration cannot silently write a local database.
- Failed overrides and restores cannot be mistaken for successful mock operations.

---

## ADR-013 — One SAM stack and scheduled state reconciliation

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Subhrojyoti Das

### Context

Separate JSON examples did not define a repeatable system and an S3 tag did not prove that an
asynchronous Lifecycle transition or restore had completed.

### Decision

Use `aws/template.yaml` as the deployable source of truth for storage, identity, API, compute,
state, audit, notification, and frontend resources. Invoke the inference Lambda hourly through
EventBridge to read actual S3 object state and reconcile DynamoDB. Use `aws/deploy.ps1` to package
both Lambdas and publish the Vite frontend from stack outputs.

### Consequences

- Infrastructure can be reviewed and linted without credentials.
- Deployment requires one AWS identity and one command rather than manual console assembly.
- Lifecycle remains asynchronous, so pending state is normal and visible.
- Standard-IA uses a 30-day transition boundary; it cannot be demonstrated as an immediate move.

---

## ADR-014 — Separate latest state from append-only audit history

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Subhrojyoti Das

### Context

Overwriting the scan row is useful for fast reads but loses who requested a decision and how state
changed over time.

### Decision

Keep current scan and placement fields in the scan table. Append prediction, override, restore,
blocked-decision, and reconciliation events to a separate audit store. SQLite uses an
`audit_events` table; AWS uses `DecisionAuditTable` keyed by `(scan_id, event_id)`.

### Consequences

- The UI can show a chronological decision history.
- Current-state reads remain simple.
- Audit retention and access controls can evolve separately from scan metadata.

---

## ADR-015 — Vite is the frontend build system

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Pratyush Chandrasekhar

### Context

Create React App was obsolete and its dependency tree produced numerous audit findings.

### Decision

Build and serve the React application with Vite. Use `VITE_` variables for public browser
configuration, write production values from CloudFormation outputs, and publish `dist/`.

### Consequences

- Development startup and production builds are faster and current.
- The verified dependency audit has no findings.
- Amplify v5 needs `global` mapped to `globalThis` in the Vite configuration.

---

## ADR-016 — Use S3 copy for moves to more accessible storage

**Status:** Accepted · **Date:** 21 September 2026 · **Owner:** Subhrojyoti Das

### Context

The tag-filtered Lifecycle mechanism in ADR-003 moves eligible objects into colder classes, but
changing an archived object's tag to `STANDARD` cannot bring it back to hot storage. A manual
override to a more accessible tier needs an actual S3 storage-class operation.

### Decision

Keep Lifecycle tags for moves to colder classes. For moves to a more accessible class, require an
archived source to be restored first, then perform a same-key S3 copy with the requested storage
class. Keep the decision pending until reconciliation reads the new object's storage class. Suppress
the `ObjectCreated` inference event caused by that copy while a manual override is pending.

### Consequences

- Manual moves back to Standard or Standard-IA have an executable mechanism.
- Restore and copy charges must be included when evaluating operational costs.
- The implementation remains limited to objects that fit a single `CopyObject` request; large
  objects would require a multipart-copy extension before production use.

---

## Open decisions

| # | Question | Blocks | Owner |
| --- | --- | --- | --- |
| 1 | AWS account created before or after 15 July 2025? | Free-tier assumptions in ADR-001 | All |
| 2 | Clinical penalty values and sensitivity sweep range | Research validation | Mehul |
| 3 | Does the rubric require EC2 or a relational database for marks? | ADR-001, ADR-004 | All |

Record each answer as a new ADR or an amendment to the relevant one. Do not resolve these in chat
and leave the file stale.
