# dataset/processed/

Everything **derived from [`../raw/`](../raw/) by a script**. This folder is disposable by design:
delete it entirely and a single command should rebuild it.

## What lives here

| File | Contents |
| --- | --- |
| `features.csv` | The feature table fed to the model — one row per scan |
| `labels.csv` | The derived access/retrieval label for each scan |
| `train.csv` / `val.csv` / `test.csv` | The three splits |
| `split_seed.txt` | The random seed used, so the split is reproducible |

## Rules

- **Every file here must be regenerable.** If you cannot point to the script that produced it,
  it does not belong in this folder.
- **Split by patient, not by image.** Several scans of the same patient are highly correlated.
  If the same patient appears in both train and test, the reported accuracy will be inflated and
  meaningless. This is the single easiest way to accidentally produce a wrong result.
- **Fix the random seed** and record it. "We got 94%" is worth nothing if nobody can reproduce it.
- Data files are ignored by Git — commit the scripts in [`../../src/ml_model/`](../../src/ml_model/)
  instead. A small sample may be committed if it helps others test.

## Document each processing run

When the preprocessing changes, note what changed and why in `CHANGELOG.md` here. At review, the
question "why does this number differ from the one in your earlier slide?" is much easier to answer
with a written record.
