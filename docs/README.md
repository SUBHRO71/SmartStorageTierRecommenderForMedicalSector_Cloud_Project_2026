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

### The consolidated report

**`Project_Report.pdf`** is the submission document — 39 pages, four parts, with PDF bookmarks
jumping to each. Parts A–C are the individual analyses concatenated with **no reformatting**, so
each member's document appears exactly as they wrote it.

| Part | Pages | Contents | Author |
| --- | --- | --- | --- |
| A | 1–8 | Papers 1–5, research gap + literature survey | Pratyush Chandrasekhar |
| B | 9–18 | Papers 6–10, research gap + literature survey | Subhrojyoti Das |
| C | 19–28 | Papers 11–15, research gap + literature survey | Mehul Anand |
| D | 29–39 | Abstract, objectives, novelty, architecture, dataset, AWS services | All |

Part D covers the remaining guideline deliverables: the 200–300 word abstract, six measurable
objectives, the one-page novelty summary, both mandatory architecture diagrams with walkthroughs,
full dataset details, and the AWS services plan.

### Rebuilding the report

```bash
python architecture/make_diagrams.py
```

```bash
python docs/build_part_d.py
```

Then open `Project_Documentation_PartD.docx` in Word and save as PDF (Word is the only converter
available here), and assemble:

```bash
python docs/merge_analyses.py
```

Run the diagram step first if the architecture changed — Part D embeds the PNGs.

### Word files are local only

`docs/*.docx` is gitignored. PDFs are the committed artifacts; the Word files are working copies.
Git cannot merge binaries, so two people editing one on separate branches would silently lose a
version. Part D is regenerated from `build_part_d.py`, so its `.docx` is disposable.

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
