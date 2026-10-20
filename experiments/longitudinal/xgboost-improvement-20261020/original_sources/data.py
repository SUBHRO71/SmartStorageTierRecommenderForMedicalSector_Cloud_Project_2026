"""One row per current visit; predictors never read a subsequent visit.

Terminal visits have no known surveillance end and therefore no evaluable label.
The estimand is conditional on a subsequent visit being recorded in this archive.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[3]
FEATURES = ["cohort_lumiere", "visit_index", "elapsed_days", "last_gap_days", "median_gap_days", "mean_gap_days", "gap_std_days"]
MASK_FEATURES = ["log_mask_volume", "enhancing_fraction", "edema_fraction"]


def history_features(days, cohort):
    days = np.asarray(days, dtype=float)
    gaps = np.diff(days)
    return dict(cohort_lumiere=float(cohort == "LUMIERE"), visit_index=len(days), elapsed_days=float(days[-1] - days[0]),
                last_gap_days=float(gaps[-1]) if len(gaps) else np.nan,
                median_gap_days=float(np.median(gaps)) if len(gaps) else np.nan,
                mean_gap_days=float(np.mean(gaps)) if len(gaps) else np.nan,
                gap_std_days=float(np.std(gaps)) if len(gaps) else np.nan)


def load_visits():
    raw = ROOT / "dataset/raw/longitudinal"
    tcga = pd.read_excel(raw / "tcga/TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx")
    mr = tcga[tcga.Modality == "MR"].copy()
    mr["date"] = pd.to_datetime(mr["Study Date"], errors="coerce")
    mr = mr.dropna(subset=["date"])
    t = mr.groupby(["Patient ID", "date"], as_index=False).agg(series=("Series Instance UID", "nunique"))
    t["day"] = (t.date - t.groupby("Patient ID").date.transform("min")).dt.days
    t = t.rename(columns={"Patient ID": "subject"})
    t["cohort"], t["timepoint"] = "TCGA-GBM", t.date.dt.strftime("%Y-%m-%d")
    l = pd.read_csv(raw / "lumiere/LUMIERE-datacompleteness.csv")
    l["day"] = l.Timepoint.str.extract(r"week-(\d+)").astype(int) * 7
    # First available scan in a week, rather than using later same-week pixels.
    l = l.sort_values(["Patient", "day", "Timepoint"]).drop_duplicates(["Patient", "day"])
    l = l.rename(columns={"Patient": "subject", "Timepoint": "timepoint"})
    l["cohort"] = "LUMIERE"
    f = pd.read_csv(raw / "lumiere/LUMIERE-pyradiomics-deepbratumia-features.csv")
    f = f[f.Sequence == "CT1"]
    masks = f.pivot_table(index=["Patient", "Time point"], columns="Label name", values="original_shape_VoxelVolume", aggfunc="median")
    total = masks.sum(axis=1, min_count=3)
    masks["log_mask_volume"] = np.log1p(total)
    masks["enhancing_fraction"] = masks["Contrast-enhancing"] / total.replace(0, np.nan)
    masks["edema_fraction"] = masks["Edema"] / total.replace(0, np.nan)
    masks = masks.reset_index().rename(columns={"Patient": "subject", "Time point": "timepoint"})
    l = l.merge(masks[["subject", "timepoint"] + MASK_FEATURES], on=["subject", "timepoint"], how="left")
    visits = pd.concat([t, l], ignore_index=True).sort_values(["cohort", "subject", "day"]).reset_index(drop=True)
    audit = {
        "TCGA-GBM": dict(source_series=len(tcga), mr_series=len(mr), subjects=int(t.subject.nunique()),
                         study_uids=int(mr["Study Instance UID"].nunique()), distinct_dates=len(t),
                         repeated_subjects=int((t.groupby("subject").size() > 1).sum()),
                         metadata_release="2015 NBIA digest linked by current publisher page; not a pixel-access grant"),
        "LUMIERE": dict(subjects=int(l.subject.nunique()), source_timepoints=638, distinct_weeks=len(l),
                        collapsed_same_week=638-len(l), repeated_subjects=int((l.groupby("subject").size() > 1).sum()),
                        mask_features_available=int(l.log_mask_volume.notna().sum())),
    }
    return visits, audit


def examples(visits):
    rows = []
    for (cohort, subject), group in visits.groupby(["cohort", "subject"]):
        records = group.sort_values("day").to_dict("records")
        for i, current in enumerate(records):
            history = [r["day"] for r in records[:i+1]]
            row = dict(cohort=cohort, subject=subject, timepoint=current["timepoint"], day=current["day"],
                       history_days=history, **history_features(history, cohort))
            row.update({c: current.get(c, np.nan) for c in MASK_FEATURES})
            row["next_days"] = records[i+1]["day"] - current["day"] if i+1 < len(records) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def assign_splits(frame, seed=42):
    """Split *all* subjects once, including those with only unknown terminal labels."""
    frame = frame.copy()
    frame["split"] = ""
    for cohort, group in frame.groupby("cohort"):
        subjects = sorted(group.subject.unique())
        train, other = train_test_split(subjects, test_size=.30, random_state=seed)
        val, test = train_test_split(other, test_size=.5, random_state=seed)
        for name, ids in [("train", train), ("validation", val), ("test", test)]:
            frame.loc[(frame.cohort == cohort) & frame.subject.isin(ids), "split"] = name
    return frame
