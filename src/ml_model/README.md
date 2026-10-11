# Inference-only model and policy

## V2 MRI path

The new cancer-imaging archive uses a separate pretrained SegResNet adapter in `mri_inference.py`. Install `requirements_mri.txt`, then run `python src/ml_model/mri_inference.py --download --smoke-test` from the project root. It uses pinned MONAI BraTS weights without training. Four aligned, brain-extracted 1 mm NIfTI sequences are required. See [v2 implementation and evidence](../../architecture/V2_IMPLEMENTATION.md) for the exact checkpoint, input gates, model provenance and current boundaries.

## V1 chest X-ray path

This component does not train or fine-tune a model. It loads TorchXRayVision’s published `densenet121-res224-all` chest X-ray weights directly, extracts 18 named pathology scores, and passes them to a versioned fixed retrieval and cost policy.

The fixed coefficients are transparent engineering assumptions, not fitted or clinically calibrated probabilities. `train.py` exits deliberately. `legacy_training.py`, `model.py`, and historical evaluation scripts remain for audit history and are outside the active runtime.

## Setup and use

Use Python 3.11–3.13:

```powershell
pip install -r src/ml_model/requirements.txt
python src/ml_model/extract_pretrained_features.py path\to\xray.png --output temp\features.json
python src/ml_model/predict.py --features temp\features.json --metadata metadata.json --size-bytes 15728640
```

`--metadata` is optional. The first extraction downloads the official model checkpoint to the normal user cache. No AWS credentials are required and no optimizer or training loop runs.

The extraction output contains:

- source filename and SHA-256;
- published weight identifier;
- 18 pathology scores keyed by name.

The prediction output contains:

- retrieval probability and feature contributions;
- chosen S3 class and explanation;
- monetary and access-delay components for every candidate tier;
- policy version, price snapshot, and horizon.

## Active files

| File | Purpose |
| --- | --- |
| `extract_pretrained_features.py` | Load published weights and extract pathology scores |
| `decision_engine.py` | Shared pure-Python retrieval and cost policy |
| `retrieval_policy_weights.json` | Versioned coefficients and S3 price assumptions |
| `predict.py` | Command-line prediction adapter |
| `train.py` | Deliberate guard that prevents training |
| `legacy_training.py` | Historical experiment retained for traceability |

The online Lambdas receive precomputed pathology scores, so their deployment bundles do not contain PyTorch. Validate policy behavior with:

```powershell
python -m unittest tests.test_decision_engine -v
```

The runtime smoke test confirms checkpoint compatibility and output shape. Medical validity requires a separate public-data evaluation with documented provenance, splits, baselines, and sensitivity analysis.
