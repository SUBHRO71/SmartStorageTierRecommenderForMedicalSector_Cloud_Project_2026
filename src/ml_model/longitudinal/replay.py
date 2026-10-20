"""Held-out, single-placement counterfactual costing, not actual retrieval logs."""
import json
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/backend"))
from temporal_forecast import forecast
from archive import policy


def replay():
    test = pd.read_json(ROOT / "dataset/processed/longitudinal/test_predictions.json")
    manifest = json.loads((ROOT / "dataset/raw/longitudinal/lumiere/aws_sample/context.json").read_text())
    sizes = [f["bytes"] for f in manifest["manifest"]]
    examples = pd.read_json(ROOT / "dataset/processed/longitudinal/examples.json")
    prior = float((examples[(examples.split == "train") & examples.next_days.notna()].next_days <= 90).mean())
    output = []
    for extra_accesses in (0, 1, 5):
        totals = {k: 0. for k in ("all_standard", "age_only", "fixed_workload_policy", "model", "hindsight_unconstrained_lower_bound")}
        cold_events = cold_placements = 0
        for row in test.to_dict("records"):
            study = dict(access=dict(hold=False, active=False, max_hours=12), complete=True,
                         clinical=dict(status="VERIFIED"), analysis=dict(status="NOT_RUN"), age_days=0,
                         objects=[dict(bytes=size, tier="STANDARD") for size in sizes])
            study["forecast"] = forecast(row["history_days"], row["cohort"],
                {k: None if pd.isna(row[k]) else row[k] for k in ("log_mask_volume", "enhancing_fraction", "edema_fraction")}, anchor="2026-10-20")
            study["forecast"]["storage_scenario_enabled"] = True
            prediction = policy(study)
            selected = prediction["tier"]
            study.pop("forecast")
            fixed_tier = policy(study, 3, prior)["tier"]
            actual_accesses = int(row["next_days"] <= 90) + extra_accesses
            costs = {c["tier"]: c["cost"] for c in policy(study, 3, actual_accesses)["candidates"]}
            totals["all_standard"] += costs["STANDARD"]
            totals["age_only"] += costs["STANDARD"]  # Every prediction is at creation, object age zero.
            totals["model"] += costs[selected]
            totals["fixed_workload_policy"] += costs[fixed_tier]
            totals["hindsight_unconstrained_lower_bound"] += min(costs.values())
            cold_placements += selected in ("GLACIER", "DEEP_ARCHIVE")
            cold_events += selected in ("GLACIER", "DEEP_ARCHIVE") and actual_accesses > 0
        output.append(dict(extra_unmodeled_bundle_accesses=extra_accesses, totals_usd=totals,
                           savings_vs_standard_pct=100*(1-totals["model"]/totals["all_standard"]),
                           cold_placements=cold_placements, cold_bundles_with_access=cold_events))
    result = dict(n_intervals=len(test), bundle_bytes=sum(sizes), bundle_objects=len(sizes), horizon_days=90,
                  assumptions="Each held-out interval represents a fresh four-file bundle with the measured sample's size; next visit within 90 days causes one retrieval. 12-hour declared tolerance. No proactive restore. Age-only keeps age-zero objects Standard. Fixed engineering price snapshot.",
                  scenarios=output,
                  limitations="Counterfactual, not measured AWS savings or retrieval validation. Excludes compute/EBS, cache, egress, tagging/API overhead, subsequent tier changes and their exit charges. Conditional follow-up selection and unobserved retrievals limit inference.")
    (ROOT / "architecture/longitudinal_cost_replay.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__": replay()
