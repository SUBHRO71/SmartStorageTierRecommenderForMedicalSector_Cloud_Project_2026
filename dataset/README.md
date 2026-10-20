# Dataset and provenance

Owner: Mehul Anand. Current experiment: 20 October 2026.

The executed experiment uses TCGA-GBM MRI timeline metadata and LUMIERE timelines
plus publisher-produced segmentation shape summaries. See the
[model report](../architecture/LONGITUDINAL_MODEL_REPORT.md) for measured counts,
exact releases, subject splits, metrics, model references and limitations.

| Folder | Contents |
| --- | --- |
| `raw/longitudinal/` | Unmodified publisher metadata, checksum manifest and a small permitted LUMIERE image sample; ignored by Git |
| `processed/longitudinal/` | Reproducible visit examples, subject splits and test predictions; ignored by Git |
| `../src/ml_model/longitudinal/` | Acquisition, preprocessing, training, selective sample download and cost replay scripts |
| `../src/ml_model/longitudinal_model.json` | Portable fitted experimental visit-proxy forest, without patient IDs |

Run from the repository root:

```powershell
python -m pip install -r src/ml_model/longitudinal/requirements.txt
python -m pip install --no-deps scikit-survival==0.25.0
python src/ml_model/longitudinal/download.py
python src/ml_model/longitudinal/train.py
python src/ml_model/longitudinal/sample.py
python src/ml_model/longitudinal/replay.py
```

The explicit forest-wheel installation avoids the unused ECOS solver build on
Windows/Python 3.13; the core dependencies are installed first.
The deployed runtime only needs the portable artifact and Python standard library.
The sample fetcher reads selected members of the public LUMIERE ZIP with byte ranges
and refuses an accidental full 32 GB download.

## What the label means

The label is days until the next recorded MRI visit, conditional on another visit
being present in the archive. TCGA visits on the same date are collapsed;
LUMIERE visits in the same anonymized week are collapsed, retaining the first
within-week record for predictors. Terminal outcomes are unknown and excluded
from supervised evaluation, rather than being labelled no follow-up.

A later visit does not establish that an earlier file was retrieved. No matching
retrieval logs were obtained for either release. This is not a claim that no
public medical access-log dataset exists anywhere. Actual timestamped object
access and restore events are needed to evaluate the intended retrieval target.

## Access and handling

The TCGA file used here is the publisher-linked 2015 NBIA metadata digest. The
current collection has controlled-access image downloads; no controlled TCGA
pixels were acquired or uploaded. Clinical outcome dates were not combined with
anonymized imaging dates.

LUMIERE metadata and the four-volume sample come from the publisher's public
Figshare release. The author repository specifies non-commercial use; this pilot
is restricted to non-commercial research and private AWS storage. Publisher
DeepBraTumIA summaries are distinct from our frozen MONAI model's masks.

Never commit raw scans, patient-level tables, clinical exports or credentials.
Keep checksums and acquisition scripts so local derived outputs can be reproduced.
The earlier NIH ChestX-ray14 workflow is historical and is not training data for
this longitudinal experiment.

## Local 12-model comparison

See the [experiment index](../experiments/longitudinal/README.md). The benchmark
uses nested patient-group validation and preserves the previously inspected test
partition as diagnostic-only data. It saves all 12 local model bundles and every
candidate/fold prediction under `processed/longitudinal/benchmarks/`; aggregate
results and plots live under `experiments/longitudinal/`. No AWS action is part
of this benchmark.
