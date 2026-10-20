"""Expanded current/past-only predictors for the second XGBoost experiment."""
import numpy as np
import pandas as pd
from benchmark_data import build_frame, FEATURE_SETS
from data import ROOT


def prior_features(frame, columns):
    """Add changes using strictly earlier visits; never backward-fill a value."""
    frame = frame.sort_values(["group", "day"]).copy()
    for col in columns:
        previous = frame.groupby("group")[col].shift(1)
        frame[f"previous_{col}"] = previous
        frame[f"change_{col}"] = frame[col] - previous
        frame[f"rate_{col}"] = (frame[col]-previous) / frame.last_gap_days.replace(0, np.nan)
    return frame


def build_improvement_frame():
    frame, audit = build_frame()
    histories = []
    for history in frame.history_days:
        gaps = np.diff(history)
        histories.append(dict(previous_gap2=gaps[-2] if len(gaps)>1 else np.nan,
            previous_gap3=gaps[-3] if len(gaps)>2 else np.nan,
            minimum_prior_gap=float(np.min(gaps)) if len(gaps) else np.nan,
            maximum_prior_gap=float(np.max(gaps)) if len(gaps) else np.nan,
            recent_gap_mean=float(np.mean(gaps[-3:])) if len(gaps) else np.nan,
            gap_trend=float(gaps[-1]-gaps[-2]) if len(gaps)>1 else np.nan,
            fraction_prior_gaps_90=float(np.mean(gaps<=90)) if len(gaps) else np.nan))
    history_columns = list(histories[0])
    frame = pd.concat([frame.reset_index(drop=True), pd.DataFrame(histories)], axis=1)
    frame["prior_mask_count"] = frame.groupby("group").log_mask_volume.transform(lambda x: x.notna().cumsum())
    changes = ["log_mask_volume", "enhancing_fraction", "edema_fraction", "mean_mask_sphericity",
               "log_max_mask_diameter", "log_source_bytes", "log_source_image_count", "current_series_count"]
    frame = prior_features(frame, changes)
    base = list(FEATURE_SETS["history_masks_technical"])
    temporal = base + history_columns + ["prior_mask_count"] + [f"{p}_{c}" for c in changes for p in ("previous", "change", "rate")]
    raw = ROOT / "dataset/raw/longitudinal"
    f = pd.read_csv(raw / "lumiere/LUMIERE-pyradiomics-deepbratumia-features.csv")
    shape = ["original_shape_Elongation", "original_shape_Flatness", "original_shape_MajorAxisLength",
             "original_shape_Sphericity", "original_shape_SurfaceVolumeRatio", "original_shape_VoxelVolume"]
    texture = ["original_firstorder_Entropy", "original_firstorder_Uniformity", "original_firstorder_Skewness",
        "original_firstorder_Kurtosis", "original_firstorder_InterquartileRange", "original_glcm_Contrast",
        "original_glcm_Correlation", "original_glcm_JointEntropy", "original_glrlm_RunEntropy", "original_glszm_ZoneEntropy"]
    # Each pivot key is the present visit, sequence and segmentation region.
    # CT1 shape avoids redundant copies of the same mask across four sequences.
    pieces = []
    for sequence in ("CT1", "T1", "T2", "FLAIR"):
        fields = texture + (shape if sequence == "CT1" else [])
        subset = f[f.Sequence == sequence]
        pivot = subset.pivot_table(index=["Patient", "Time point"], columns="Label", values=fields, aggfunc="median")
        pivot.columns = [f"rad_{sequence.lower()}_region{int(label)}_{field}" for field, label in pivot.columns]
        pieces.append(pivot)
    radiomics = pd.concat(pieces, axis=1).reset_index().rename(columns={"Patient": "subject", "Time point": "timepoint"})
    radiomics["cohort"] = "LUMIERE"
    rad_features = [c for c in radiomics if c.startswith("rad_")]
    frame = frame.merge(radiomics, on=["cohort", "subject", "timepoint"], how="left", validate="one_to_one")
    frame = frame.sort_values("row_id").reset_index(drop=True)
    feature_sets = dict(original=base, temporal=temporal, temporal_radiomics=temporal+rad_features)
    all_features = list(dict.fromkeys(temporal+rad_features))
    frame[all_features] = frame[all_features].replace([np.inf, -np.inf], np.nan)
    forbidden = {"subject", "group", "row_id", "next_days", "split", "timepoint", "day"}
    if forbidden.intersection(all_features): raise AssertionError("Forbidden predictor")
    return frame, feature_sets, audit
