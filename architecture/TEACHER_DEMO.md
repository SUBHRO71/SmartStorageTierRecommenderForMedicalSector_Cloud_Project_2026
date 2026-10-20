# Teacher demonstration

Open `/project/demo` on the deployed website for the interactive checklist and live catalog preflight.

## Eight-to-ten-minute presentation

1. Sign in using the existing private administrator credentials. Open `/project/architecture` and play the six-stage explanation. Explain that next recorded imaging visits are a proxy for possible file reuse.
2. Open `/studies/ST-8B325CB5D201`. Inspect the four MRI sequences, change the slice/plane, inspect checksums and the exact clinical join. Previews use the encrypted EBS working cache.
3. Expand saved forecast inputs and select **Re-run saved forecast**. This calls the authenticated forecast endpoint, preserves historical inputs and scenario anchor, and appends a forecast event. Expect 98-day median, 28–203-day interval, and 42.3% probability within 90 days for the prepared pilot. The scenario date is not an observed future retrieval date.
4. Select **Policy**, then **Review S3 placement**. Inspect eligible tiers, the 12-hour declared wait, the 90-day horizon and one-possible-access assumption. Opening review alone does not change S3.
5. Use the synthetic QA study to demonstrate a manual hold: record its initial setting, enable hold, enter a demo reason, save, recalculate and show Standard. Restore the original hold setting if changed.
6. Return to the real research pilot. Inspect its existing placement request and audit trail. An operator may submit the reviewed unchanged placement with a demo reason. Requested tier is not observed storage class.
7. Inspect actual S3 object classes/tags in AWS alongside the manifest. Only when objects are actually archived, request restore and inspect headers later. Do not claim a restored object until S3 reports completion. Lifecycle transitions and Glacier restores are asynchronous; they do not fit an instant classroom demo.
8. Open `/project/models` and `/project/aws`. Show all 12 local model families, which artifacts actually run, the held-out results, and infrastructure costs.

## Evidence boundaries

- On 21 October 2026 all four pilot source objects were observed as STANDARD, despite their GLACIER request. Refresh before class rather than assuming a completed transition.
- The deployed forecast is the original Random Survival Forest. The local XGBoost candidate is not promoted. No defensible 80% unseen-patient retrieval accuracy has been achieved.
- MONAI segmentation is a separate optional job. The real pilot forecast uses publisher mask summaries; do not claim these came from running MONAI on that pilot.
- No predictive restore scheduler is deployed.
- S3 tier savings estimates exclude server/cache/backup overhead and are not measured account savings.
- Baseline planning infrastructure: EC2 $69.90 + EBS $4.80 + one public IPv4 $3.65 = approximately $78.35 per 730-hour month before other usage, credits and tax. Website links the official pricing sources.

The guide pages do not upload data or change cloud placement automatically. The forecast re-run and placement buttons are explicit authenticated actions using existing role checks and study-version checks.
