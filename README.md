# Smart Storage Tier Recommender for the Medical Sector

**AI-Based Storage Tier Recommendation for Medical Image Repositories using Deep Learning Analytics**

Project Phase-I · BCSE355L Cloud Architecture Design · 2026
Course Instructor: Dr. Priya V

---

## 1. What this project does

Hospitals generate an enormous volume of medical scans (CT, MRI, X-ray). Keeping every scan on
fast storage is expensive. Moving everything to cheap storage is also wrong, because retrieving a
file from deep archive can take hours, and a doctor cannot wait that long.

Amazon S3 offers several storage classes at very different price and speed points — S3 Standard is
fast but costly, Glacier Deep Archive is cheap but slow. **This project uses deep learning to decide
which storage class each individual scan belongs in.**

The decision is driven by three kinds of signal:

| Signal | Source | Why it matters |
| --- | --- | --- |
| Image content | Deep learning model over the scan itself | A scan showing an active finding is far likelier to be retrieved |
| DICOM metadata | Modality, body part, patient age, study description | Available at ingest, costs nothing to read, works before any access history exists |
| Access history | Past retrieval record for that study | How existing storage systems decide today |

### What makes this different

Existing storage-tiering research (Harmonia, Sibyl) is accurate and extremely fast, but judges a
file purely on block-level behaviour — request size, access count, access interval. It has never
been applied to medical data. Meanwhile medical imaging platforms (Kaapana, PARADIM) have rich
DICOM indexes and deep learning pipelines, but use them only to help the radiologist, never to
manage the storage underneath.

**Nobody has joined the two.** That is the gap this project fills. See
[`docs/`](docs/) for the full literature survey and research gap analysis.

---

## 2. System architecture

> **STATUS: UNDER DISCUSSION — NOT YET FINALISED.**
>
> The architecture is being designed and will be documented here once the team agrees on it.
> Nothing in this section should be treated as decided.

When finalised, this section will contain:

- A short prose walkthrough of the end-to-end flow, from scan ingest through to a tier decision
  being applied as an S3 lifecycle action
- An embedded system architecture diagram (`architecture/System_Architecture.png`)
- An embedded AWS deployment diagram (`architecture/AWS_Architecture.png`)
- The component/service table — what each part is responsible for and what it talks to
- Rationale for the major design decisions, so the choices can be defended at review

Open questions still to be settled:

- [ ] Where the model runs — Lambda at ingest, scheduled batch job, or both
- [ ] Whether tier decisions are applied directly via the S3 API or expressed as S3 Lifecycle rules
- [ ] Whether the image-feature model runs on every scan or only on a sampled subset
- [ ] How the training label is derived (see [`dataset/README.md`](dataset/README.md))
- [ ] Where DICOM metadata is indexed and queried from
- [ ] Which AWS services each team member owns for the individual-defence requirement

Working notes and diagram drafts go in [`architecture/`](architecture/).

---

## 3. Repository structure

| Path | Contents |
| --- | --- |
| [`docs/`](docs/) | All written deliverables — report, literature survey, research gap, objectives, novelty |
| [`architecture/`](architecture/) | System, AWS and workflow diagrams, plus the source files used to draw them |
| [`dataset/`](dataset/) | Raw data, processed data, and the dataset documentation. **No large or patient-identifiable files are committed.** |
| [`src/frontend/`](src/frontend/) | User interface |
| [`src/backend/`](src/backend/) | API layer, database integration, authentication |
| [`src/ml_model/`](src/ml_model/) | Preprocessing, training, inference, evaluation |
| [`aws/`](aws/) | Cloud infrastructure configuration and service definitions |
| [`results/`](results/) | Experiment outputs, metrics, graphs, execution screenshots |
| [`presentation/`](presentation/) | Review slides and demo material |

Every folder has its own `README.md` describing exactly what belongs in it and who owns it.

---

## 4. Branching strategy

```
main                    production / tagged releases only
 └── develop            integration branch — all work merges here first
      ├── feature/student1
      ├── feature/student2
      └── feature/student3
```

### Rules

1. `main` and `develop` are never committed to directly. All work happens on a feature branch.
2. Each member works **exclusively** inside their own `feature/studentX` branch.
3. Commit regularly and in small, meaningful units — not one giant commit at the end.
4. Raise a Pull Request from `feature/studentX` into `develop`.
5. At least one teammate reviews the PR before it is merged. Resolve conflicts on the feature branch.
6. Once the system is stable, `develop` merges into `main` and the release is tagged
   (e.g. `v1.0-Phase1`).

### Per-member expectations

Each team member must be able to show, at review:

- 20–30 meaningful commits
- At least 2 Pull Requests
- Active participation in reviewing others' PRs
- A consistent weekly commit history — not a single burst before the deadline
- Documentation updated alongside code

Every member must also be ready to individually explain their own commits and the specific
AWS services they integrated.

---

## 5. Team

| | Name | Reg No | Branch | Primary ownership |
| --- | --- | --- | --- | --- |
| Student 1 | _TBD_ | _TBD_ | `feature/student1` | Frontend, testing |
| Student 2 | _TBD_ | _TBD_ | `feature/student2` | Backend, database, auth, AWS infrastructure |
| Student 3 | _TBD_ | _TBD_ | `feature/student3` | Dataset, ML model, results |

All three members contribute to the literature survey, research gap analysis, AWS services,
documentation and presentation.

---

## 6. Getting started

```bash
git clone https://github.com/SUBHRO71/SmartStorageTierRecommenderForMedicalSector_Cloud_Project_2026.git
```

```bash
git checkout develop && git checkout -b feature/studentX
```

Setup instructions for each component live in that component's own README —
see [`src/backend/`](src/backend/), [`src/ml_model/`](src/ml_model/) and [`src/frontend/`](src/frontend/).

---

## 7. Current status

| Item | State |
| --- | --- |
| Literature survey (15 papers across the team) | Done |
| Research gap analysis | Done |
| Repository structure | Done |
| System architecture | **In discussion** |
| Dataset selection | In progress |
| Implementation | Not started |

---

## 8. Licence

MIT — see [`LICENSE`](LICENSE).
