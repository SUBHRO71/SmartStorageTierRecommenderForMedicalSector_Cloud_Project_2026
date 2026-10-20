"""Current-visit technical features for the local benchmark only.

No changes to the deployed v1 feature schema. No future scan, outcome, patient
identifier, scanner identifier or absolute anonymized date becomes a predictor.
"""
import numpy as np
import pandas as pd
from data import ROOT, FEATURES, MASK_FEATURES, load_visits, examples, assign_splits

TECHNICAL = ["current_series_count", "log_source_bytes", "log_source_image_count",
             "log_mean_original_voxels", "mean_field_strength", "mean_mask_sphericity",
             "log_max_mask_diameter"]
FEATURE_SETS = {"history": FEATURES,
                "history_masks_technical": FEATURES + MASK_FEATURES + TECHNICAL}


def build_frame():
    visits, audit = load_visits()
    raw = ROOT / "dataset/raw/longitudinal"
    t = pd.read_excel(raw / "tcga/TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx")
    t = t[t.Modality == "MR"].copy()
    t["timepoint"] = pd.to_datetime(t["Study Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    t = t.drop_duplicates(["Series Instance UID"])
    t["File Size"] = pd.to_numeric(t["File Size"], errors="coerce")
    t["Image Count"] = pd.to_numeric(t["Image Count"], errors="coerce")
    tcga = t.groupby(["Patient ID", "timepoint"], as_index=False).agg(
        current_series_count=("Series Instance UID", "nunique"),
        source_bytes=("File Size", "sum"), source_image_count=("Image Count", "sum"))
    tcga = tcga.rename(columns={"Patient ID": "subject"})
    tcga["cohort"] = "TCGA-GBM"
    tcga["log_source_bytes"] = np.log1p(tcga.source_bytes)
    tcga["log_source_image_count"] = np.log1p(tcga.source_image_count)
    m = pd.read_csv(raw / "lumiere/LUMIERE-MRinfo.csv")
    for c in ("Rows", "Columns", "Slice count", "Field strength"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["voxels"] = m.Rows * m.Columns * m["Slice count"]
    l = m.groupby(["Patient", "Timepoint"], as_index=False).agg(
        current_series_count=("Sequence", "nunique"), mean_original_voxels=("voxels", "mean"),
        mean_field_strength=("Field strength", "mean"))
    l = l.rename(columns={"Patient": "subject", "Timepoint": "timepoint"})
    l["cohort"] = "LUMIERE"
    l["log_mean_original_voxels"] = np.log1p(l.mean_original_voxels)
    f = pd.read_csv(raw / "lumiere/LUMIERE-pyradiomics-deepbratumia-features.csv")
    f = f[f.Sequence == "CT1"]
    shape = f.groupby(["Patient", "Time point"], as_index=False).agg(
        mean_mask_sphericity=("original_shape_Sphericity", "mean"),
        max_diameter=("original_shape_Maximum3DDiameter", "max"))
    shape = shape.rename(columns={"Patient": "subject", "Time point": "timepoint"})
    shape["log_max_mask_diameter"] = np.log1p(shape.max_diameter)
    l = l.merge(shape, on=["subject", "timepoint"], how="left", validate="one_to_one")
    extra = pd.concat([tcga, l], ignore_index=True)
    # examples() intentionally accepts a fixed v1 mask schema. Join technical
    # predictors by the *current* visit key after labels/history are constructed.
    frame = assign_splits(examples(visits)).merge(
        extra[["cohort", "subject", "timepoint"] + TECHNICAL],
        on=["cohort", "subject", "timepoint"], how="left", validate="one_to_one")
    frame["group"] = frame.cohort + ":" + frame.subject
    frame["row_id"] = np.arange(len(frame))
    frame[TECHNICAL] = frame[TECHNICAL].replace([np.inf, -np.inf], np.nan)
    return frame, audit
