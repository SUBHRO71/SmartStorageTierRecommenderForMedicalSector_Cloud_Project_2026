# src/ml_model/

The inference-only model and policy that recommend a storage tier for each scan. **Owner: Mehul Anand.**

## Current implementation decision

The project does **not train a model locally**. `extract_pretrained_features.py` loads the
published `densenet121-res224-all` chest X-ray weights through TorchXRayVision and produces
pathology scores. `decision_engine.py` combines those scores with metadata using the checked-in
`retrieval_policy_weights.json`, then applies the explicit S3 cost policy.

The fixed retrieval-policy coefficients are provisional engineering weights, not fitted clinical
evidence. This distinction is returned by the API through the policy version and must remain clear
in reports. `train.py` intentionally exits; the old experimental trainer remains in
`legacy_training.py` for audit history only.

```bash
pip install -r src/ml_model/requirements.txt
python src/ml_model/extract_pretrained_features.py path/to/xray.png --output features.json
python src/ml_model/predict.py --features features.json --metadata metadata.json --size-bytes 15728640
python -m unittest discover -s tests -p "test_*.py" -v
```

The first feature extraction downloads the published weights into PyTorch's cache. It does not use
AWS credentials and it does not fit or fine-tune the network.

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
