# Conditional next-visit prediction: executed research pilot

Executed 20 October 2026. This is a fitted and tested **next recorded imaging visit**
model. It has no observed file-retrieval labels. Performance is insufficient to
claim reliable retrieval-date prediction or general autonomous archival.

## Sources and actual usable data

| Cohort | Publisher/source count | Usable temporal records | Known next-visit intervals |
| --- | --- | --- | --- |
| TCGA-GBM | 262 subjects, 575 studies overall; publisher-linked NBIA digest contains 5,412 series | MR subset: 259 subjects, 531 study UIDs; collapsed to 482 subject-dates; 60 subjects have repeated dates | 223 |
| LUMIERE | 91 subjects, 638 timepoints | 589 subject-weeks after collapsing 49 same-week records; 83 subjects have repeated weeks | 498 |

TCGA uses the **2015 NBIA metadata digest currently linked by the publisher**, not
an assertion that we downloaded a complete current pixel release. The 2026
controlled-access manifest was inventoried; no controlled TCGA pixels were
acquired or uploaded. Study UID count is not treated as a repeat-visit count.
Only within-subject relative imaging intervals are used; TCGA clinical date
reference systems were not joined to imaging dates.

LUMIERE uses the v202211 imaging/features release. Its relative timepoints are
weeks, not true calendar dates. First within-week records supply current features.
DeepBraTumIA volume summaries are available for 482 of the 589 selected weeks.
These are **publisher segmentation outputs**, distinct from our frozen MONAI
SegResNet masks. No segmentation network was trained in this experiment.

Downloads and SHA-256 checksums are recorded locally in
`dataset/raw/longitudinal/manifest.json`; raw and subject-level derived data are
ignored by Git. The four-image sample comes from the public LUMIERE archive,
conservatively restricted to non-commercial research and private AWS storage.

Sources: [TCGA-GBM collection](https://www.cancerimagingarchive.net/collection/tcga-gbm/),
[TCGA metadata digest](https://www.cancerimagingarchive.net/wp-content/uploads/TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx),
[LUMIERE collection](https://springernature.figshare.com/collections/The_LUMIERE_Dataset_Longitudinal_Glioblastoma_MRI_with_Expert_RANO_Evaluation/5904905/1),
[LUMIERE paper](https://doi.org/10.1038/s41597-022-01881-7),
[author repository and usage note](https://github.com/ysuter/gbm-data-longitudinal).

## Target and predictors

At each current visit, predict the distribution of days until the next recorded
visit, **conditional on another visit being present in this archive**. Derive
30/60/90-day conditional probabilities, a median interval and a 10–90% interval.
A new scan does not prove retrieval of an old image.

The final record for each of 350 subjects has no known observation endpoint. Those
350 labels remain unknown; they are excluded from supervised fitting/evaluation.
They are not negative examples. The data do not identify an unconditional chance
of future follow-up, and do not support an unconditional retrieval survival model.
Although the forest method supports censored outcomes, this experiment only fits
observed intervals; inventing a censoring endpoint would change the target.

Predictors known by the current visit:

- Cohort, number of distinct prior/current visits, elapsed days since first visit.
- Last, median and mean prior interval, plus interval standard deviation.
- Current LUMIERE log total segmented volume and enhancing/edema fractions when available.
- Training-only median imputation and explicit missing-value indicators.

No patient ID, future visit date, future mask, future response rating, survival
time or outcome is a predictor. Pixel arrays and file size are not predictors in
this version. File size is measured separately for the cost calculation.

## Papers and model choice

[Ishwaran et al., Random Survival Forests, 2008](https://doi.org/10.1214/08-AOAS169)
motivates a nonlinear ensemble returning a time-to-event distribution. We compared
12 prespecified forest configurations: history versus history plus mask summaries,
minimum leaf sizes 5/10/20, and maximum depths 4/8; each has 100 trees and seed 42.

The [2019 LR-LRU paper](https://doi.org/10.1109/ACCESS.2019.2913961) motivates a
transparent logistic classification baseline. Its real hospital access-log target
is different from our archive-follow-up proxy. No accuracy from that paper is
transferred to this experiment. Logistic C is selected from 0.1/1/10 on validation
Brier score. Empirical, last-gap and median-prior-gap timing baselines are included.

All subject IDs are split once within each cohort, seed 42, approximately
70/15/15. The model uses subject-weighted training so subjects with many visits
do not receive proportionally larger total fit weights.

| Partition | All subject IDs | Subjects with known intervals | Known intervals |
| --- | ---: | ---: | ---: |
| Train | 244 | 97 | 479 |
| Validation | 53 | 21 | 124 |
| Test | 53 | 25 | 118 |

Many TCGA subjects have only one date. Thus 53 test IDs do not mean 53 labelled
subjects: 25 contribute the 118 evaluated intervals. Validation selects the
lowest day MAE, then Brier90 as tie-breaker. The test is not used for tuning or
refitting. The selected forest uses history plus masks, leaf size 10, depth 4.

## Locked held-out results

| Method | 90-day accuracy | Balanced accuracy | AUC | Brier90 (lower better) | Day MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected timing forest | 63.6% | 56.3% | 0.659 | 0.223 | 44.2 |
| Empirical baseline | 64.4% | 50.0% | 0.500 | 0.233 | 46.7 |
| Logistic baseline | 66.9% | 61.6% | 0.705 | 0.212 | 47.0 (constant timing baseline) |

Last-gap timing MAE is 59.4 days; median-prior-gap MAE is 51.7 days. Missing prior
history uses the 79-day unweighted training median for these two baselines.
The selected forest improves mean timing error modestly, and does not beat the
majority baseline on raw classification accuracy. Logistic regression is stronger
for 90-day classification. The timing forest remains the deployed timing model;
it was selected on validation MAE, not promoted for its test accuracy.

The forest's median absolute timing error is 34.5 days; 49.2% of intervals are
within 28 days. Subject-cluster bootstrap 95% intervals: accuracy 50.2–74.7%; MAE
34.9–55.7 days. Its nominal 10–90% interval covers 83.1% of test intervals, with
average width 136.7 days. Broad uncertainty makes an exact retrieval date unjustified.

By cohort: LUMIERE 86 intervals / 14 labelled test subjects, accuracy 57.0%, MAE
46.2 days; TCGA 32 intervals / 11 labelled test subjects, accuracy 81.3%, MAE
38.8 days. TCGA's 87.5% positive prevalence exceeds that 81.3% accuracy: its high
raw accuracy is not evidence of a strong classifier.

Exact results and all validation candidates: [metrics](longitudinal_metrics.json).
Portable forest predictions match the library to max absolute difference
8.96e-11. The deployed JSON is about 554 KB and needs no sklearn runtime on AWS.

## Cost counterfactual and its limits

The held-out cost experiment treats each of 118 intervals as a fresh four-object
bundle with the measured sample's total size, 18,404,657 bytes. It uses a 90-day
horizon, declared 12-hour restore tolerance and the existing labeled engineering
price snapshot. Predicted P(next visit within 90 days) weights the cost of **one**
possible whole-bundle retrieval. It is not an expected count of arbitrary accesses.

A manual hold, active-use flag, immediate access, incomplete files, unverified
clinical linkage or failed/running analysis continues to override cost. A
prespecified pilot guard keeps P(visit within 30 days) >= 50% in Standard.

| Additional unobserved accesses per bundle | All Standard | Fixed-workload policy | Model scenario |
| --- | ---: | ---: | ---: |
| 0 | $0.13968 | $0.05955 | $0.06100 |
| 1 | $0.13987 | $0.09549 | $0.09633 |
| 5 | $0.14062 | $0.23924 | $0.23765 |

These are aggregate modeled costs for the 118 small bundles over 90 days, not
measured bills. The model scenario appears 56.3% cheaper than all Standard under
the one-access assumption, but **does not outperform the fixed-workload policy**.
With five additional accesses, it is 69.0% more expensive than Standard. It sends
116 bundles cold, including 75 with a known first event within 90 days: it does
not eliminate restore exposure. No proactive prefetch is simulated. The general cost-comparison page explicitly
uses the user-declared horizon/access count for every policy; it does not silently
substitute a study-specific 90-day proxy scenario.

The age-only baseline keeps these age-zero bundles in Standard. The reported
hindsight lower bound has future information and is not a deployable competitor.
This is a single-placement counterfactual, not a full multi-transition lifecycle
simulation. Compute, EBS working cache, egress, tag/request overhead, retained
versions, later tier changes and their exit charges are excluded. Minimum storage
durations and archive metadata are included in the existing estimator.
See [cost replay](longitudinal_cost_replay.json) and
[AWS pricing mechanics](https://aws.amazon.com/s3/pricing/).

## AWS pilot

Release `releases/16dda78195b2e1e59adc.tgz` is deployed to the existing private
research stack. No new GPU, instance, public bucket, permission grant or paid-plan
upgrade was introduced. Existing administrator credentials were preserved.

Four actual LUMIERE publisher-processed NIfTI volumes (T1, T1ce, T2, FLAIR),
18.4 MB, were imported through the authenticated staged-upload workflow for
Patient-011, week-021. Selection was the first eligible subject/timepoint in the
locked test partition, without selecting for prediction success. Clinical linkage
is an exact source-ID join; the exported age is age at source surgery, not age at
some inferred future event. Publisher shape features were passed separately;
MONAI inference was not run on this sample.

[Open study ST-8B325CB5D201](https://dbfq563k4fadil4rqn4taz653e0mbpar.lambda-url.us-east-1.on.aws/studies/ST-8B325CB5D201)

Historical context contains only visits at relative days 0, 21 and 147. The
model outputs median 98 days, 10–90% interval 28–203 days, P30=11.9%, P60=19.5%,
P90=42.3%. With **20 October 2026 as an explicit scenario anchor**, the displayed
median date is **26 January 2027**. That is not a real patient forecast or an
observed future retrieval date.

Under the declared 12-hour research tolerance, Glacier Flexible Retrieval has
the lowest modeled eligible source-member cost: $0.000437 versus $0.001183
Standard over 90 days. Deep Archive is excluded by the 12-hour limit; Standard-IA
is excluded by the configured 30-day object-age boundary.

The placement request and all four `tier=GLACIER` S3 tags were verified, as were
source SHA-256 metadata and local/cloud model checksum/prediction equality.
At verification, all four objects were still observed STANDARD and placement was
PENDING. Lifecycle transitions are asynchronous. No archived retrieval or
scheduled predictive restore was tested. The EBS preview cache remains hot, so
source-member savings are not total-account savings.

## Reproduction and verification

From the repository root after installing training dependencies:

```powershell
python -m pip install -r src/ml_model/longitudinal/requirements.txt
python -m pip install --no-deps scikit-survival==0.25.0
python src/ml_model/longitudinal/download.py
python src/ml_model/longitudinal/train.py
python src/ml_model/longitudinal/sample.py
python src/ml_model/longitudinal/replay.py
python -m unittest discover -s tests -p "test_*.py" -v
```

On Windows/Python 3.13, the forest wheel works without the unused ECOS solver;
the explicit no-dependencies install avoids building that unrelated solver.
Core numpy/scipy/sklearn dependencies must already be installed by the requirements.

Build the frontend and use `aws/deploy.py` for the existing deployment procedure.
`aws/longitudinal_pilot.py` imports/reuses this exact sample, requests the explicitly
enabled experimental cost scenario and verifies S3 state. It is scoped to account
657878533811. Do not run it against other data as a validated retrieval model.

49 automated tests pass. Frontend production build passes. Tests cover future
feature leakage, disjoint subject splits, unknown terminal labels, invalid
contexts, authorization/stale versions and protection overrides. Raw/processed
subject tables and local AWS evidence are not committed. The current conclusion
is a working research pipeline with weak predictive evidence, not successful
retrieval-model validation. A reliable next stage needs timestamped object access
logs, known observation coverage and independent prospective validation.
