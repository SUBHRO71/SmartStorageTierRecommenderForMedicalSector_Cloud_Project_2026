# src/ml_model/

The deep learning model that recommends a storage tier for each scan. **Owner: Mehul Anand.**

This is the core contribution of the project — everything else exists to serve, demonstrate or
deploy what happens here.

## Expected files

| File | Purpose |
| --- | --- |
| `preprocessing.py` | Reads `dataset/raw/`, extracts DICOM metadata and image features, writes `dataset/processed/` |
| `train.py` | Trains the model, saves weights and metrics |
| `predict.py` | Loads a trained model and returns a tier for one scan or a batch |
| `evaluate.py` | Computes metrics, cost comparison against baselines, and writes to `results/` |
| `model.py` | Model architecture definition |
| `config.yaml` | Hyperparameters, paths, tier definitions — no values hardcoded in scripts |
| `requirements.txt` | Pinned dependencies |

## The task

**Input** — three groups of features per scan:

1. **Image features** — a vector from a deep learning model over the scan itself
2. **DICOM metadata** — modality, body part, study description, patient age, urgency
3. **Access history** — past retrieval counts and intervals, where available

**Output** — one of four S3 storage classes: Standard, Standard-IA, Glacier Flexible Retrieval,
Glacier Deep Archive.

## Two things that must not be got wrong

**1. The loss must be asymmetric.**

Standard classification treats every mistake as equally bad. Here they are not remotely equal:

- Putting a rarely-used scan in Standard → we overpay slightly. Minor.
- Putting a scan a doctor needs into Deep Archive → they wait up to 12 hours. Serious.

The loss function must encode that asymmetry. A model with excellent accuracy and a symmetric loss
is useless for this problem, and this is exactly the point our research gap analysis argues.

**2. Split by patient, not by image.**

Multiple scans of one patient are highly correlated. If the same patient lands in both train and
test, accuracy will be inflated and the result will not survive questioning at review.

## Baselines to compare against

A number means nothing without something to compare it to. Evaluate against all three:

| Baseline | Why |
| --- | --- |
| Everything in S3 Standard | The expensive status quo — shows the saving |
| Age-based rule (e.g. archive after 90 days) | What hospitals actually do today |
| S3 Intelligent-Tiering | AWS's own built-in answer — the honest competitor |

Beating an age-based rule is the minimum bar. Beating Intelligent-Tiering is the real claim, and
it should be winnable because Intelligent-Tiering cannot see clinical metadata.

## Report cost, not just accuracy

The headline result should be a **monthly storage bill**, plus how often a needed scan ended up in
archive. Accuracy alone will not convince anyone that the system is worth deploying.

## Rules

- Fix and record the random seed. Unreproducible results are worthless.
- Log every experiment to `results/` — configuration, metrics, date. Do not rely on memory.
- Do not commit model weights over 50 MB. Commit the training script and the config.
- Do not commit data. See [`../../dataset/README.md`](../../dataset/README.md).

## Setup

To be filled in by Mehul Anand once the framework is chosen. Must include Python version, install
steps, how to run training, and expected runtime.
