#!/usr/bin/env python3
"""Assemble the full Phase-I project report from its component PDFs.

Concatenates Parts A-C (the three individual research gap analyses, exactly as
their authors wrote them) followed by Part D (abstract, objectives, novelty,
architecture, dataset details and AWS services planning). Adds PDF bookmarks
so the report is navigable, and sets document metadata.

Part D is produced from Project_Documentation_PartD.docx via Word; this script
only assembles the PDFs. Regenerate the diagrams first if they have changed:

    python architecture/make_diagrams.py

Run this whenever any part is updated:

    python docs/merge_analyses.py

Requires PyMuPDF:  pip install pymupdf
"""

import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required.  Install it with:  pip install pymupdf")

DOCS = Path(__file__).resolve().parent

PARTS = [
    ("Research_Gap_Student1.pdf", "Part A  -  Papers 1-5  |  Pratyush Chandrasekhar (24BIT0226)"),
    ("Research_Gap_Student2.pdf", "Part B  -  Papers 6-10  |  Subhrojyoti Das (24BIT0194)"),
    ("Research_Gap_Student3.pdf", "Part C  -  Papers 11-15  |  Mehul Anand (24BIT0185)"),
    ("Project_Documentation_PartD.pdf",
     "Part D  -  Abstract, Objectives, Novelty, Architecture, Dataset, AWS Services"),
]

OUTPUT = DOCS / "Project_Report.pdf"

METADATA = {
    "title": "Project Report - AI-Based Storage Tier Recommendation for "
             "Medical Image Repositories",
    "subject": "BCSE355L Cloud Architecture Design, Project Phase-I",
    "author": "Pratyush Chandrasekhar, Subhrojyoti Das, Mehul Anand",
    "keywords": "BCSE355L, Cloud Architecture Design, Project Phase-I, AWS, "
                "medical imaging, storage tiering",
}


def main() -> int:
    missing = [name for name, _ in PARTS if not (DOCS / name).exists()]
    if missing:
        print("Missing input file(s):")
        for m in missing:
            print(f"  - docs/{m}")
        return 1

    merged = fitz.open()
    toc = []

    for name, title in PARTS:
        src = fitz.open(DOCS / name)
        start = merged.page_count + 1          # outline pages are 1-indexed
        merged.insert_pdf(src)
        toc.append([1, title, start])
        print(f"{name:34s} {src.page_count:3d} pages  ->  page {start}")
        src.close()

    merged.set_toc(toc)
    merged.set_metadata(METADATA)
    merged.save(OUTPUT, garbage=4, deflate=True)
    total = merged.page_count
    merged.close()

    print()
    print(f"Wrote {OUTPUT.name}  ({total} pages, {len(toc)} bookmarks)")
    print()
    print("Component PDFs are the master copies. The consolidated editable .docx")
    print("is gitignored -- regenerate it from this PDF in Word only if needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
