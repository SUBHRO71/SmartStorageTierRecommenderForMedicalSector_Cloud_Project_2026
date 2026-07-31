# docs/

All **written deliverables** for the project. This folder is what the faculty reads at review.
No code, no data, no diagrams (diagrams live in [`../architecture/`](../architecture/)).

## What goes here

| File | Contents | Owner |
| --- | --- | --- |
| `Project_Report.docx` | The main project report — combines every section below into one document | All |
| `Literature_Survey.docx` | Consolidated survey table covering all 15 papers studied by the team | All |
| `Research_Gap.docx` | Consolidated research gap analysis | All |
| `Objectives.docx` | Problem statement and the specific, measurable objectives of the project | All |
| `Novelty.docx` | What is new in this work and why it has not been done before | All |

### Per-member working documents

Each member also keeps their own 5-paper analysis here, so individual contribution is visible
in the commit history:

| File | Papers | Author | Reg No | Status |
| --- | --- | --- | --- | --- |
| `Research_Gap_Student1.pdf` | 1–5 | Pratyush Chandrasekhar | 24BIT0226 | Committed |
| `Research_Gap_Student2.pdf` | 6–10 | Subhrojyoti Das | 24BIT0194 | Committed |
| `Research_Gap_Student3.pdf` | 11–15 | Mehul Anand | 24BIT0185 | Committed |

Filenames keep the `StudentN` form because the course guidelines name them that way.

**PDFs are committed; the source `.docx` files are not.** A PDF renders identically everywhere,
is what a reviewer actually opens, and cannot produce a binary merge conflict. Each author keeps
their own `.docx` locally and re-exports the PDF when it changes.

Nothing in `.gitignore` blocks `.docx`, so the consolidated `Project_Report.docx` can still be
committed later if the team decides it should be.

These are later merged into the consolidated `Research_Gap.docx`.

## Conventions

- **Format:** `.docx` or `.pdf` only. Soft copy — no hard copies are required for this course.
- **Naming:** `Title_Case_With_Underscores.docx`. Do not put spaces in filenames.
- **No version suffixes.** Never commit `Report_final_v2_FINAL.docx`. Git is the version history —
  commit the change instead and write a clear commit message.
- **Reference style:** stay consistent across every document. Include DOI or arXiv ID for every
  paper so a reviewer can find it.
- Each paper cited must be **2025 or 2026** unless there is a stated reason, which must be written
  into the document itself.

## Note on binary files in Git

`.docx` files cannot be diffed or merged by Git. If two people edit the same document on different
branches, the merge will conflict and one version will have to be discarded manually.

**To avoid losing work:** only one person edits a given `.docx` at a time. Say so in the team chat
before you start editing a shared document.
