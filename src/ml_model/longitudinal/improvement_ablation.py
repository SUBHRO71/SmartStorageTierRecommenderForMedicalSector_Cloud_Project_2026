"""Compare the improvement hypotheses with inner-only configuration selection."""
import argparse
import json
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from benchmark import ROOT, grouped_folds, write_json
from improve_xgboost import SEED, select_full, class_metrics
from improvement_model import ImprovedXGB


def run(run_id):
    public = ROOT / "experiments/longitudinal" / run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / run_id
    protocol = json.loads((public / "protocol.json").read_text())
    frame = pd.read_pickle(private / "input_full_precision.pkl")
    dev = frame[frame.next_days.notna() & (frame.split != "test")].reset_index(drop=True)
    folds = grouped_folds(dev, 5, SEED)
    hypotheses = {
        "Original compact features": lambda c: c["features"] == "original",
        "Add history and current/prior changes": lambda c: c["features"] == "temporal",
        "Add current radiomics": lambda c: c["features"] == "temporal_radiomics",
        "Pooled cohorts": lambda c: c["strategy"] == "pooled",
        "Separate cohort models": lambda c: c["strategy"] == "specialists",
        "Hard original training labels": lambda c: c["week91"] == "hard",
        "Soft weekly-boundary training sensitivity": lambda c: c["week91"] == "soft",
        "Native missing-value handling": lambda c: c["missing"] == "native",
        "Fixed median-imputed reference": lambda c: c["missing"] == "median",
    }
    output = []
    cache = {}
    with threadpool_limits(limits=2):
        for label, predicate in hypotheses.items():
            probability, threshold = np.zeros(len(dev)), np.zeros(len(dev))
            selections = []
            for fold, (a, b) in enumerate(folds):
                record = json.loads((public / f"folds/fold{fold}.json").read_text())
                choice = select_full([c for c in record["candidates"] if predicate(c["config"])])
                key = (fold, choice["id"])
                if key not in cache:
                    model = ImprovedXGB(choice["config"], protocol["feature_sets"][choice["config"]["features"]]).fit(dev.iloc[a])
                    cache[key] = model.predict(dev.iloc[b])
                probability[b], threshold[b] = cache[key], choice["threshold"]
                selections.append(choice["id"])
            output.append(dict(hypothesis=label, metrics=class_metrics(dev, probability, threshold), selected_by_fold=selections))
            pd.DataFrame(dict(row_id=dev.row_id, probability_90d=probability, threshold=threshold)).to_csv(private / f"ablation_{len(output)}.csv", index=False, float_format="%.17g")
    write_json(public / "ablation.json", dict(note="Each restricted search selects on inner folds and evaluates outer rows. Hypotheses overlap; this is exploratory and not a causal attribution. Median reference has one fixed setting, other groups allow tuning.", results=output))
    pd.DataFrame([dict(hypothesis=r["hypothesis"], accuracy_90d=r["metrics"]["accuracy_90d"], subject_balanced_accuracy=r["metrics"]["subject_weighted_balanced_accuracy_90d"], auc=r["metrics"]["subject_weighted_auc_90d"], brier=r["metrics"]["subject_weighted_brier_90d"]) for r in output]).to_csv(public / "ablation.csv", index=False)
    with (private / "final_models.pkl").open("rb") as stream: bundle = pickle.load(stream)
    importance = {}
    for cohort, model in bundle["classifier"].models.items():
        gains = model.get_booster().get_score(importance_type="gain")
        features = bundle["classifier"].features
        importance[cohort] = sorted([dict(feature=features[int(key[1:])] if int(key[1:]) < len(features) else "missingness_indicator_"+key, gain=float(value)) for key, value in gains.items()], key=lambda x:-x["gain"])[:20]
    write_json(public / "feature_gain.json", dict(note="Training split gain only; not causal or external feature importance", models=importance))
    print(pd.read_csv(public / "ablation.csv").to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="xgboost-improvement-20261020")
    run(parser.parse_args().run_id)
