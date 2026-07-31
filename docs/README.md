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

### Consolidated document

`Research_Gap_and_Literature_Survey.pdf` is the three individual analyses concatenated into one
28-page file, in order, with **no reformatting** — each member's document appears exactly as they
wrote it. PDF bookmarks jump to each section. This single file covers both the *Research Gap
Analysis* and *Literature Survey* deliverables for all 15 papers.

| Section | Pages | Author |
| --- | --- | --- |
| Papers 1–5 | 1–8 | Pratyush Chandrasekhar |
| Papers 6–10 | 9–18 | Subhrojyoti Das |
| Papers 11–15 | 19–28 | Mehul Anand |

An editable `Research_Gap_and_Literature_Survey.docx` sits alongside it **locally only** — it is
listed in `.gitignore`. Word's PDF reflow is approximate, so treat it as a working copy for
editing, never as the master. The PDF is the master.

To rebuild either file after someone updates their section:

```bash
python docs/merge_analyses.py
```

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
