"""Portable, dependency-free inference for the experimental visit proxy model."""
import bisect
from datetime import date, timedelta
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml_model/longitudinal_model.json"


@lru_cache(maxsize=1)
def load_model():
    raw = MODEL_PATH.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def features_from_history(history, cohort, masks=None):
    if cohort not in ("LUMIERE", "TCGA-GBM"):
        raise ValueError("The experimental model supports LUMIERE and TCGA-GBM only")
    if not isinstance(history, list) or not 1 <= len(history) <= 100:
        raise ValueError("Supply 1 to 100 historical visit days, ending at the current visit")
    if any(type(d) not in (int, float) or not math.isfinite(d) or not 0 <= d <= 36500 for d in history):
        raise ValueError("Historical visit days must be finite nonnegative relative days")
    if any(b <= a for a, b in zip(history, history[1:])):
        raise ValueError("Historical visits must be strictly increasing; collapse same-day/week visits")
    gaps = [b-a for a, b in zip(history, history[1:])]
    ordered = sorted(gaps)
    median = (ordered[(len(gaps)-1)//2] + ordered[len(gaps)//2])/2 if gaps else None
    mean = sum(gaps)/len(gaps) if gaps else None
    values = dict(cohort_lumiere=float(cohort == "LUMIERE"), visit_index=len(history), elapsed_days=history[-1]-history[0],
                  last_gap_days=gaps[-1] if gaps else None, median_gap_days=median, mean_gap_days=mean,
                  gap_std_days=math.sqrt(sum((g-mean)**2 for g in gaps)/len(gaps)) if gaps else None)
    if masks is not None and not isinstance(masks, dict):
        raise ValueError("Current-visit segmentation features must be an object")
    masks = masks or {}
    for key in ("log_mask_volume", "enhancing_fraction", "edema_fraction"):
        val = masks.get(key)
        if val is not None and (type(val) not in (int, float) or not math.isfinite(val) or val < 0 or val > (30 if key == "log_mask_volume" else 1)):
            raise ValueError("Invalid current-visit segmentation feature")
        values[key] = val
    return values


def predict_cdf(model, values):
    if model["kind"] == "empirical":
        return model["cdf"]
    missing = [values.get(f) is None or not math.isfinite(values[f]) for f in model["features"]]
    x = [m if absent else float(values[f]) for f, m, absent in zip(model["features"], model["medians"], missing)]
    x += [float(missing[i]) for i in model["missing_indicators"]]
    result = [0.] * len(model["grid_days"])
    for tree in model["trees"]:
        node = 0
        # sklearn trees compare float32 feature inputs.
        import struct
        while tree["left"][node] != -1:
            value = struct.unpack("f", struct.pack("f", x[tree["feature"][node]]))[0]
            node = tree["left"][node] if value <= tree["threshold"][node] else tree["right"][node]
        for i, survival in enumerate(tree["survival"][str(node)]):
            result[i] += (1-survival)/len(model["trees"])
    return [min(1., max(0., p)) for p in result]


def quantile(grid, cdf, q):
    return next((day for day, p in zip(grid, cdf) if p >= q), None)


def forecast(history, cohort, masks=None, anchor=None):
    values = features_from_history(history, cohort, masks)
    model, checksum = load_model()
    cdf, grid = predict_cdf(model, values), model["grid_days"]
    anchor = anchor or date.today().isoformat()
    try:
        origin = date.fromisoformat(anchor)
    except (TypeError, ValueError) as error:
        raise ValueError("Use an ISO scenario anchor date (YYYY-MM-DD)") from error
    p = lambda day: round(cdf[bisect.bisect_right(grid, day)-1], 6)
    median = quantile(grid, cdf, .5)
    low, high = quantile(grid, cdf, .1), quantile(grid, cdf, .9)
    return dict(model_id=model["model_id"], model_sha256=checksum, cohort=cohort,
                target="next recorded distinct-date/week imaging visit, conditional on a later recorded visit",
                experimental=True, actual_retrieval_model=False, history_days=history, features=values,
                probability_30d=p(30), probability_60d=p(60), probability_90d=p(90),
                median_days=median, interval_10_90_days=[low, high],
                scenario_anchor_date=anchor, scenario_predicted_date=(origin+timedelta(days=median)).isoformat() if median else None,
                calendar_date_kind="scenario anchored; historical anonymized dates are not real future dates",
                limitations="Archive follow-up proxy, not retrieval logs. Terminal outcomes unknown; probabilities are conditional. Week-level LUMIERE timing. No clinical-use validation.")
