# dataset/raw/

Data **exactly as it was downloaded**. Treat everything in this folder as read-only.

## Rules

- Never edit a file here. Never overwrite one. If the data is wrong, fix it in a preprocessing
  script and write the corrected version to [`../processed/`](../processed/).
- Never commit the actual data files — they are too large for Git and may contain patient
  information. See [`../README.md`](../README.md).
- **Do** commit the download script, so anyone can recreate this folder from scratch.

## What should be committed here

| File | Purpose |
| --- | --- |
| `download.sh` or `download.py` | Fetches the dataset from its source |
| `manifest.txt` | Expected filenames and checksums, so we can verify the download worked |
| `sample/` | 10–20 rows or a couple of images, so teammates can see the schema and test code without a 40 GB download |

Everything else in this folder is ignored by Git — see the root `.gitignore`.

## Why raw data is kept immutable

If preprocessing turns out to have a bug — and it usually does — we need to rerun it from the
original data. If the original has already been overwritten, the whole dataset has to be
downloaded again, and any result produced before the bug was found becomes impossible to
reproduce or explain at review.
