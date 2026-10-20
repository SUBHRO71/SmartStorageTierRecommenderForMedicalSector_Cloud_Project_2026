# CloudTierRecommender — cancer imaging study archive

Cloud storage optimization for complete cancer imaging studies, with validated
DICOM/NIfTI imports, exact clinical CSV joins, MRI previews, published pretrained
MONAI SegResNet analysis, explicit access constraints, and explainable S3 tier
recommendations. The current app is the v2 study dashboard. The old X-ray routes
and old SAM deployment have been retired from the active application.

The [longitudinal experiment](architecture/LONGITUDINAL_MODEL_REPORT.md) trains a
conditional next-visit proxy using TCGA-GBM MRI timeline metadata and LUMIERE
timelines plus publisher segmentation summaries. It has no actual retrieval-log
labels. Locked holdout results and cost sensitivity do not justify general
autonomous archival.

A [local 12-model benchmark](experiments/longitudinal/README.md) now compares
classification and timing across nested patient-group folds. All fitted bundles,
settings and predictions are saved locally; it leaves the deployed model unchanged.

## Current AWS deployment

The [deployment plan](architecture/AWS_V2_DEPLOYMENT.md) describes the architecture,
rollout, costs and recovery limits. [Deployment status](aws/DEPLOYMENT_STATUS.md)
records actual verification evidence; implementation alone is not cloud evidence.

The pilot serves the frontend and Flask study API through a Lambda HTTPS gateway and a private
VPC connection to an EC2 server. Cognito verifies sign-in and viewer/operator/admin
roles on the server. An instance role accesses private versioned encrypted S3.
Validated imports upload complete member files to S3. Placement/restore requests
persist intent, perform real S3 operations and reconcile member states every five
minutes. Requested placement remains distinct from observed placement.

SQLite metadata, append-only audit events and working MRI files use encrypted EBS.
The pinned model runs on the pilot CPU server; the EBS working cache remains
available independently of the S3 source tier. Daily consistent catalog backups
and separate working-cache copies go to S3. This is a single-server research pilot.

```powershell
./aws/deploy.ps1
```

See [AWS instructions](aws/README.md) for login, backups, stop/start, retained data
and account restrictions. No keys, passwords, local databases, real images or
cached MRI weights are included in release packages. The portable trained visit
proxy is explicitly included. The initial generated login is
saved outside the project under `%LOCALAPPDATA%/CloudTierRecommender/aws-v2/` with access restricted to the current OS user.

## Run locally

Prerequisites: Python 3.11–3.13 and Node 20+.

```powershell
pip install -r src/backend/requirements.txt
pip install -r src/ml_model/requirements_mri.txt
python src/backend/app.py
```

In another terminal:

```powershell
cd src/frontend
npm ci
npm start
```

Open `http://127.0.0.1:5173`. Local demonstration sign-in remains available only
without Cognito configuration. Explicit sample import creates synthetic metadata
without MRI pixels. Import permitted aligned, brain-extracted NIfTI volumes for
analysis. Download the verified pretrained checkpoint once:

```powershell
python src/ml_model/mri_inference.py --download --smoke-test
```

## Verify

```powershell
pip install -r aws/requirements-cloud.txt
python -m unittest discover -s tests -p "test_*.py" -v
python aws/build_template.py
cfn-lint aws/template.yaml
cd src/frontend
npm run build
```

`aws/smoke.py --analyze` verifies the deployed application with generated synthetic
MRI inputs. It does not establish clinical accuracy. Historical v1 source and
tests remain for regression history; `aws/legacy` is not a deployment target.

## Boundaries

Storage optimization is the primary objective. MRI output is research segmentation,
not a diagnosis or retrieval forecast. MRI segmentation remains frozen; the
separate conditional visit proxy is locally trained and evaluated as documented above.
Raw DICOM conversion, registration and brain extraction remain offline prerequisites.
Independent external validation and actual retrieval-log evaluation remain planned.

The dashboard compares S3 source-member costs using a labeled engineering snapshot.
It excludes the server, EBS working cache, backup copies, retained versions and
other overhead. See [cost model](aws/cost_estimates.md). Lifecycle is asynchronous;
Standard-IA uses a 30-day boundary. AWS readiness does not establish hospital
production readiness or permission to process patient data.

Project Phase-I · BCSE355L Cloud Architecture Design · 2026.
Team: Pratyush Chandrasekhar, Subhrojyoti Das, Mehul Anand. MIT license.
