# dataset/

Data used to train and evaluate the tier recommendation model, and the documentation that
explains it. **Owner: Student 3.**

## Layout

| Path | Contents |
| --- | --- |
| `raw/` | Data exactly as downloaded from the source. Never edited, never overwritten. |
| `processed/` | Anything derived from `raw/` by a script — cleaned tables, extracted features, train/val/test splits. |
| `dataset_description.pdf` | Full documentation of what was used, where it came from, and its licence |

Every file in `processed/` must be reproducible by running a script in
[`../src/ml_model/`](../src/ml_model/) against `raw/`. If you cannot regenerate it, it does not
belong there.

---

## Rules — read before committing anything

**1. Do not commit large files.**
GitHub rejects files over 100 MB and warns above 50 MB. Medical imaging datasets are far larger
than that. Commit the *download and preprocessing scripts*, not the data itself.

**2. Do not commit patient-identifiable data. Ever.**
Even from a public de-identified dataset, do not commit raw DICOM files containing patient tags.
Git history is permanent — deleting a file in a later commit does **not** remove it from the
repository. This mistake cannot be undone by a normal commit.

**3. What to commit instead:**
- The script that downloads the data
- The preprocessing script
- A small sample (10–20 rows) so others can see the schema and test their code
- A checksum or manifest listing the expected files
- `dataset_description.pdf`

---

## The data problem — read this before choosing a dataset

This project needs three kinds of data. **Only two of them can be downloaded.**

| Needed | Available? | Source |
| --- | --- | --- |
| Medical images + DICOM metadata | Yes | TCIA preserves real DICOM headers |
| Storage access traces (generic) | Yes | SNIA IOTTA Repository |
| **Medical image retrieval logs — the training label** | **No** | Does not exist publicly |

No public dataset records *who retrieved which scan, and when*. Those records exist only inside
hospital PACS audit trails (IHE ATNA format), they are protected patient information, and no
institution releases them.

**This means our training label cannot be downloaded. It has to be derived.**

### The workaround

Derive a proxy label from follow-up timestamps: when a patient returns for a later scan, the
radiologist almost always pulls up the earlier one to compare. So a later study for the same
patient is evidence that the earlier study was retrieved.

**State this openly in the report as a proxy, not ground truth.** It will miss retrievals that
happen without a new scan being taken — multidisciplinary team meetings, second opinions, research
requests. Pair it with a sensitivity analysis showing how much the results depend on the
assumption. Being upfront about this is far stronger than implying we have real access logs.

There is published precedent for exactly this framing: Yayan et al., *Scientific Reports*,
December 2025, "Exploratory associations between radiographic findings and metadata-derived
proxies of 90-day follow-up in 112,120 ChestX-ray14 radiographs."

---

## Candidate datasets — all free

| Dataset | Access | Notes |
| --- | --- | --- |
| **NIH ChestX-ray14** | Fully open, no registration | 112,120 images. `Data_Entry_2017.csv` has `Patient ID` **and** `Follow-up #` — a ready-made proxy signal. Best starting point. |
| **TCIA** | Mostly open | Real DICOM with headers intact. Use this if we need genuine DICOM metadata features. |
| **MIMIC-CXR / MIMIC-IV** | Free but credentialed | 377,110 images, real timestamps, patient-linked. Requires CITI training + a data use agreement. Free of charge, takes a few days. |
| **Project Imaging-X portal** | Open | Catalogue of 1000+ open datasets, filterable by modality and annotation type. Use it to search rather than hunting one at a time. |

**Warning:** many public datasets are distributed as PNG or JPEG, which destroys the DICOM header.
Half our planned features come from that header — check before committing to a dataset.

---

## `dataset_description.pdf` must document

- Which dataset(s) were used and the exact version or release date
- Where it was downloaded from, with a working link
- Licence and citation requirements — several require a specific citation
- Number of records, images, patients
- The preprocessing applied, step by step
- Train/validation/test split sizes and how the split was made
- How the label was derived, and its stated limitations
- Any class imbalance, and how it was handled
