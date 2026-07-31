#!/usr/bin/env python3
"""Merge the three individual research gap analyses into one consolidated PDF.

Concatenates the member PDFs in order with no reformatting -- each section
appears exactly as its author wrote it. Adds PDF bookmarks so the merged file
is navigable, and sets document metadata.

Run this whenever any member updates their section:

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
    ("Research_Gap_Student1.pdf", "Papers 1-5  |  Pratyush Chandrasekhar (24BIT0226)"),
    ("Research_Gap_Student2.pdf", "Papers 6-10  |  Subhrojyoti Das (24BIT0194)"),
    ("Research_Gap_Student3.pdf", "Papers 11-15  |  Mehul Anand (24BIT0185)"),
]

OUTPUT = DOCS / "Research_Gap_and_Literature_Survey.pdf"

METADATA = {
    "title": "Research Gap Analysis and Literature Survey - All 15 Papers",
    "subject": "AI-Based Storage Tier Recommendation for Medical Image Repositories",
    "author": "Pratyush Chandrasekhar, Subhrojyoti Das, Mehul Anand",
    "keywords": "BCSE355L, Cloud Architecture Design, Project Phase-I",
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
    print("The editable .docx is NOT regenerated automatically and is gitignored.")
    print("To refresh it, open the PDF in Word and save as .docx -- Word's PDF")
    print("reflow is approximate, so the PDF stays the master copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
