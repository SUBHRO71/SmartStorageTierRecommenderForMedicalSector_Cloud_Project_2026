# V2 local implementation and verification

> Update, 20 October 2026: the AWS v2 pilot is now implemented and deployed.
> See [deployment status](../aws/DEPLOYMENT_STATUS.md) and the
> [AWS plan](AWS_V2_DEPLOYMENT.md). The boundaries below record the earlier local milestone.

**Date:** 11 October 2026\
**Scope:** Working local cancer-imaging archive and redesigned dashboard.\
**Target requirements:** [PRD](PRD_V2_TCIA_BRATS.md), [dashboard specification](DASHBOARD_V2_SPEC.md).

## Delivered

- Coordinated teal/mint/slate dashboard, navy navigation, dark MRI viewer and matching sign-in.
- Overview, study explorer, clinical/metadata/policy tabs, quality queue, operations, imports and cost comparison.
- Responsive layouts tested at 1440, 1024, 768, 499 and 390 px. Phone navigation supports keyboard focus containment and Escape; off-screen navigation is inert. Phone MRI inspection uses a single sequence viewport. Horizontal tables have visible scroll guidance. Study filters persist in the URL and the return link restores them.
- Subtle page arrival, menu and chart introduction animations. System reduced-motion preferences disable authored motion.
- Persistent SQLite study records containing sequence/object hierarchy, checksums, measured bytes, source declarations, clinical state, access requirements, analysis and decisions. Events are append-only.
- Multipart NIfTI/DICOM import, explicit sequence roles, matching DICOM PatientID/StudyInstanceUID, exact clinical CSV joins and ambiguous/missing states. No guessed cross-dataset joins.
- Real NIfTI slice previews in three planes. Prediction overlays become available after a successful MRI analysis; samples never display fabricated images.
- Pretrained SegResNet worker with four-channel order, matching affine/shape, 1 mm spacing, intensity validation, pinned revision and checkpoint checksum. Produces nested ET/TC/WT masks, mL measurements and runtime/input provenance.
- Study policy with active-use/hold constraints, complete sequence/clinical requirements, explicit access tolerance and per-object monetary comparison. MRI measurements do not generate an access probability.
- Reviewed local placement, complete-bundle local restore, optimistic version checks and audit events. Sample import is explicit and idempotent.
- Existing v1 X-ray routes and their AWS implementation remain separately available.

## Run

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

Open `http://127.0.0.1:5173`. **Open local workspace** uses the existing demonstration identity. The archive begins empty; **Explore sample cohort** creates 12 labeled synthetic records with no MRI pixels or inferred model results. Previously imported studies persist.

MRI setup, once:

```powershell
python src/ml_model/mri_inference.py --download --smoke-test
```

The checkpoint is cached outside the repository under the user's `.cache/cloudtier/brats-0.5.4`. Import four permitted, already aligned and brain-extracted NIfTI volumes, attest their preprocessing on study detail, then select **Run MRI analysis**. The backend runs a local background worker and the page polls its status. Startup marks interrupted analyses as failed so they can be inspected and retried. Worker results merge atomically with current access requirements.

Optional settings: `ARCHIVE_DB_PATH`, `ARCHIVE_DATA_DIR`, `MRI_BUNDLE_DIR`, `VITE_API_URL` and `VITE_DISPLAY_TIMEZONE` (defaults to Asia/Kolkata). These are local paths/public endpoint settings, not embedded AWS credentials.

### Clinical CSV

Use an exact subject identifier in `subject_id`, `PatientID` or `ID`. Supported normalized fields: diagnosis, age, sex, grade, IDH, MGMT. Common UCSF column equivalents are also recognized. Only allowlisted clinical values are stored; names/birth dates and arbitrary free-text columns are not imported into the displayed clinical record.

```csv
subject_id,diagnosis,age,sex,grade,IDH,MGMT
EXAMPLE-SUBJECT,Example research diagnosis,41,F,3,not reported,unknown
```

The example is a schema illustration. Upload permitted real records for a real clinical demonstration. An exact CSV match verifies the declared ID join; NIfTI subject correspondence remains a source declaration unless separately established through a provider crosswalk.

## Validation evidence

| Check | Result |
| --- | --- |
| Python regression suite | 28 tests passed, including 11 v2 tests |
| Frontend production build | Passed; archive screens split into separate route chunks |
| DICOM fixtures | Header identity/geometry extracted; subject mismatch rejected |
| NIfTI fixtures | Four-sequence import, measured/checksummed files and real PNG preview passed |
| Clinical CSV | Exact join passed; duplicate matching rows remained ambiguous |
| Policy/operations | Holds, immediate-access and failed-analysis constraints; stale placement rejection; complete local restore passed |
| Bad inputs | Invalid files cleaned up without a partial study; non-finite workloads rejected |
| Browser | Explicit sample import, coverage filter, study detail, placement/restore, costs, sign-in and mobile menu exercised |
| Responsive | Overview and study surfaces stayed within viewport width after the table containment fix |
| Model checkpoint | Official published weights loaded; finite output shape `[1,3,32,32,32]` on a synthetic compatibility tensor |
| Full MRI adapter | Synthetic four-volume run produced masks/volumes/provenance; evidence in `results/v2_model_compatibility.json` |

Model bundle release 0.5.4 is pinned to revision `04689f51062d1ec889c8af2e78fc0369c6fda36d`. Verified checkpoint SHA-256: `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`. The tested runtime uses MONAI 1.5.2 and PyTorch 2.11.0 CPU; the newer framework supports this machine's Python/NumPy installation. The publisher's bundle metadata originally specifies MONAI 1.4.0. This compatibility evidence does not establish accuracy on cancer imaging.

## Remaining target requirements

| Area | Current boundary |
| --- | --- |
| Real TCIA/BraTS cohort | No real patient dataset was downloaded in this implementation. Import requires permitted local files and their actual clinical export/crosswalk. |
| Provider discovery | TCIA/IDC API adapter, provider-driven manifests and automated collection download remain planned. Current import is a validated local upload. |
| Raw DICOM model path | DICOM metadata import is implemented. Conversion, registration and brain extraction are explicit offline prerequisites for the NIfTI MRI worker. |
| Clinical field completeness | Depends on the acquired release. Exact IDs are validated; no complete clinical history is inferred. |
| Cloud v2 execution | V2 APIs are explicitly gated in DynamoDB mode. V1 cloud mechanisms remain implemented; study-bundle DynamoDB/S3 execution and live reconciliation are still to be added. |
| Operations | Placement and restore are local simulations, not observed S3 transitions. A real cloud study would need member-level pending/mixed/failure reconciliation. |
| Cost evaluation | Declared workload simulation using the checked-in engineering price snapshot. Prior-tier exit charges, egress, compute, hot previews and other services are excluded and labeled. No claim of measured AWS savings. |
| Segmentation evidence | Checkpoint/adapter functional tests passed on synthetic inputs. Independent cohort accuracy, overlap audit and Dice/HD95 evaluation remain pending. |
| Production hardening | Local demonstration authentication; no new server-side role enforcement is claimed for the local archive. Raw imported files are retained locally and are not automatically de-identified. |
| Large archives | The local pilot returns its study inventory as one response; server-side bounded pagination and indexed collection queries are future scale work. |

The local application is a usable implementation milestone. The target PRD continues to describe the fuller dataset, evaluation and cloud delivery scope; these boundaries must stay visible in project presentations.
