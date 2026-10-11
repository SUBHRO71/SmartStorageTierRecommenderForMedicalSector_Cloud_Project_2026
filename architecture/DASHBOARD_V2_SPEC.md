# CloudTierRecommender v2 — Dashboard Design Specification

**Date:** 11 October 2026\
**Status:** Proposed screen and interaction design for implementation\
**Product authority:** [v2 PRD](PRD_V2_TCIA_BRATS.md)\
**Surface mode:** Operate — inspect an archive, resolve issues, review placement, and retrieve complete studies.

## 1. Design goal

Help an archive administrator answer three questions quickly: **Which studies can I use? Which need attention? Why is this storage recommendation appropriate?** The interface should bring clinical linkage, MRI sequence completeness, access requirements, and actual storage state into the same workflow.

The existing dashboard emphasizes a headline, four statistics, a tier pie chart, and recent scan decisions. The redesign centers the operational queue and complete studies. The important unit is a usable MRI study, whose many files may be in different states.

## 2. Navigation and information architecture

| Navigation | Purpose | Primary action |
| --- | --- | --- |
| Overview | Archive state, coverage and actionable issues | Review issues |
| Studies | Search/filter complete and incomplete studies | Open study |
| Data Quality | Resolve source, linkage, sequence and analysis problems | Inspect issue |
| Policy & Costs | Inspect access assumptions and compare baselines | Run comparison |
| Operations | Imports, model runs, placements and restores | Inspect operation |

Collection and active filters persist when moving between Overview, Studies, and Data Quality. Study detail supports shareable paths and a predictable back link. Subject details and the MRI Workbench live inside study detail rather than adding more top-level sections.

Global header: product name, selected collection/release, **Local demo / Live AWS / Synthetic scenario** indicator, user role, and most recent refresh time. Every displayed evaluation also names its workload source. A live inventory with simulated costs must show both facts.

## 3. Overview layout

This structural wireframe contains placeholders, not measured project results.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ CloudTierRecommender    Collection / release       Mode        Role       │
├──────────────┬────────────────────────────────────────────────────────────┤
│ Overview     │ Archive overview                       Import collection   │
│ Studies      │ Collection • source • last refresh • active filters        │
│ Data Quality │                                                            │
│ Policy &     │ Studies / Stored GiB / Complete MRI sets / Clinical links  │
│ Costs        │ Counts include denominators and links to filtered records  │
│ Operations   │                                                            │
│              │ Review queue                         Current placement     │
│              │ Issue • affected study • next step   Tier by stored bytes  │
│              │ Missing sequence / unresolved join   Actual vs requested   │
│              │ Failed analysis / partial restore    Pending member count  │
│              │                                                            │
│              │ Study inventory                                            │
│              │ Search   Collection   Completeness   Tier   Access window  │
│              │ Subject / Study / T1 T1ce T2 FLAIR / Clinical / State      │
│              │                                                            │
│              │ Cost comparison                      Recent operations     │
│              │ Assumptions and baseline visible     Job / state / action  │
└──────────────┴────────────────────────────────────────────────────────────┘
```

### Reading order

1. **Scope and evidence:** collection/release, data mode, freshness, and any API failure.
2. **Inventory strip:** study count, actual stored bytes, complete four-sequence sets, clinical join coverage. Show `verified / eligible` denominators and link each measure to its corresponding filter.
3. **Review queue:** highest-priority access/operation failures first, followed by integrity, sequence and clinical issues. Each row has a specific next action.
4. **Actual placement:** horizontal stacked bar by bytes with a labeled table; show object/study counts as alternate views. Keep requested distribution separate and label mixed studies.
5. **Study inventory:** use the same filters and columns as the full Studies page, with bounded pagination.
6. **Cost and operations:** concise comparison with assumptions and progress links. No promised savings banner.

A healthy empty queue says "No studies need review in this scope" with the active scope visible. It does not imply that an unavailable backend or unprocessed collection has no issues.

## 4. Studies explorer

Use one row per study. Expand a row to inspect sequences/series and their object counts without loading all volume data.

| Column | Behavior |
| --- | --- |
| Subject / study | Opaque internal ID, collection and relative acquisition context; full source identifiers only in permitted detail view |
| Modality / format | MR/CT/other and DICOM/NIfTI as distinct properties |
| MRI sequence set | Labeled T1, T1ce, T2, FLAIR indicators: present, missing, ambiguous, invalid |
| Clinical linkage | Verified, unmatched, ambiguous, conflicting; source and missing-field detail on inspection |
| Size | Actual stored GiB/MiB, with raw/derived/object-count breakdown |
| Access need | Declared access requirement, active-use window or manual hold |
| Analysis | Ready, queued, skipped, failed; model version in detail |
| Storage | Actual tier or Mixed; smaller separate Requested label when different |
| Next action | Open study, resolve issue, inspect transition, or track restore |

Filters: collection/release, modality, format, complete sequence set, clinical status, analysis state, access hold, requested/observed tier, and operation state. Search supports permitted IDs and descriptions. Applied filters remain visible as removable labels with Clear all.

Sort only on defined fields. Server-side filters and pagination must apply to the whole result set. Show returned count and total when the API provides it; do not imply that a page count represents the archive total.

Batch selection is P1. A batch review summarizes eligible, blocked and changed-manifest studies before an admin requests placement. It binds to decision versions and does not hide partial failures.

## 5. Study detail and MRI Workbench

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Back to studies   Subject / Study   Completeness   Observed / Requested  │
│ Source collection • release • measured size • operation state           │
├────────────────────────────────────────┬─────────────────────────────────┤
│ MRI Workbench                          │ Study context                   │
│                                        │ Metadata | Clinical | Policy    │
│   T1 view          T1ce view            │                                 │
│   T2 view          FLAIR view           │ Clinical join + source          │
│                                        │ Diagnosis / age context         │
│ Plane • slice • linked scroll          │ Missing fields remain explicit  │
│ WT / TC / ET overlays • opacity        │                                 │
│ Region volumes • model/source labels   │ Access requirements + holds     │
│                                        │ Recommendation + constraints    │
│ Preview availability / restore state   │ Compare eligible tiers          │
├────────────────────────────────────────┴─────────────────────────────────┤
│ Sequences & files | Analysis provenance | Operations | Audit             │
│ Actor • time • reason • model/policy version • member operation results  │
└──────────────────────────────────────────────────────────────────────────┘
```

### MRI inspection

- Use a 2×2 sequence grid on wide screens. Each viewport displays its sequence name and image source. Provide single-viewport mode on narrower screens.
- Offer axial/coronal/sagittal selection, keyboard-accessible slice controls, window/level where supported, zoom/reset, and linked scrolling only when alignment is verified.
- Toggle WT, TC, and ET overlays independently with a persistent legend. Identify manual reference annotation versus model prediction; never mix them without labels.
- Region measurements include units, model version and analysis status. A voxel score is not displayed as clinical confidence.
- Preserve orientation and slice metadata. A preview must be resampled from the volume using its affine; do not resize unrelated image slices into apparent alignment.
- P0 can use verified, pre-generated orthogonal preview stacks with masks. It must identify them as research previews. A full DICOM viewer can be integrated later; a thumbnail grid is not a volumetric viewer.
- If raw files are archived, small derived previews may remain available. Label the distinction: "Preview available; original volumes require restore." Preview storage is included in cost estimates.

### Clinical panel

Start with clinical join state and provenance. Display permitted diagnosis, grade, age reference, sex, molecular markers, and available follow-up fields in readable groups. Distinguish absent values from a failed join. A source outcome field is descriptive context; active-use flags are separate operator-maintained requirements.

Clinical metadata must not suggest a complete health record when the source provides only a few fields. Use "Reported clinical fields" and show coverage rather than "Patient history complete."

### Policy panel

Lead with the recommended class and the decisive access constraint. Under it show:

- Current observed tier, requested tier, manifest and decision versions.
- Declared access time, active-use/hold state and evidence source.
- A candidate-tier table with eligibility, monetary estimate, and access implications.
- Policy version, workload provenance, price snapshot and horizon.
- Relevant archive/restore operation state.

**Review placement** opens a concrete summary of members, constraints, changes, cost assumptions and failures. **Request restore** gives the required member count, retrieval mode, estimated timing and applicable charges. Role-limited users can inspect reasons for disabled actions. Admin override requires a reason and records changed access requirements if an explicit constraint is being changed.

## 6. Data Quality and Operations

Data Quality groups issues by action rather than a generic red/green score:

| Issue | Useful action |
| --- | --- |
| Unmatched/ambiguous clinical ID | Inspect crosswalk and source namespaces |
| Missing/ambiguous MRI sequence | Inspect candidate series and confirm permitted assignment |
| Invalid geometry or checksum | Inspect validator details and re-import affected object |
| Analysis skipped/failed | Inspect prerequisite/model run; retry after resolving cause |
| Incomplete archive bundle | Inspect member manifest and upload status |
| Placement/restore partially failed | Open member operation results and retry eligible members |

Operations uses explicit steps: validated → preprocessing → analysis → decision → placement → reconciliation. Show completed member counts and the current step. Progress percentages appear only when a real denominator exists. A queued model run shows whether the offline worker is connected.

Allow retries with visible eligibility and idempotency. A retry creates a linked attempt and retains the original failure in the audit history. Copy complete-restore status from reconciled state, not from a successful request submission.

## 7. Policy & Costs

Use grouped horizontal bars plus a cost-component table for all-Standard, age-based, current and proposed policy. Keep denominators and horizons identical. Offer a separate delay/access-violation chart with its own units.

Controls: collection, saved workload, observed/synthetic provenance, horizon, region/price snapshot, access intensity, retrieval mode and constraints. Changing a scenario updates modeled results only. Placement has a separate reviewed action.

Every result shows:

- Stored raw and derived bytes, actual object count, hot preview/metadata costs.
- Storage, transitions, requests, restores, temporary copies and duration charges.
- Scope, evaluated event count, delayed-access events and protected-study violations.
- Generator/version/seed for a synthetic trace, or provenance for observed events.
- Absolute monetary difference and percentage against a named baseline, calculated only where valid.

If there is no workload evidence, show "Choose a workload to compare costs"; do not produce a retrieval forecast from segmentation output.

## 8. Proposed visual system

This is a recommended design direction for the v2 implementation, not an audited or shipped interface. Use a quiet light archive workspace with a dark viewer canvas; precise hierarchy and readable data outrank decoration.

| Token | Proposed value | Use |
| --- | --- | --- |
| Workspace | `#F6F8FA` | Main background |
| Surface | `#FFFFFF` | Tables, panels and dialogs |
| Primary ink | `#172B3A` | Headings and navigation |
| Secondary ink | `#526273` | Supporting text |
| Action/focus | `#146C66` | Primary actions and visible focus |
| Border | `#D7DFE5` | Structure and component edges |
| Success | `#176A45` | Verified/applied states |
| Attention | `#8A4B08` | Review and pending states |
| Error | `#A92E3B` | Failed/blocked states |
| MRI canvas | `#101820` | Image inspection only |

Typography: readable system sans-serif or a bundled equivalent; 16 px default body, 14 px dense table text with comfortable line height, 24–28 px page titles, and tabular numerals for measurements. Long identifiers wrap in detail views and truncate with an accessible full-value reveal in rows. Use 4/8 px spacing increments, modest 6–8 px corners, borders rather than heavy shadows, and labeled existing Heroicons where useful.

Tier colors remain stable across charts and badges: Standard teal, Standard-IA blue, Flexible Retrieval amber, Deep Archive muted slate. State labels and patterns accompany colors. MRI overlay colors are reserved for tumor-region legends and must be checked for grayscale/color-vision usability separately from tier colors.

Local design-search suggestions returned portfolio/marketing patterns that did not fit this operating console. The task-first structure above is a project-specific fallback based on the verified archive workflows; those mismatched templates are not treated as design authority.

## 9. Responsive behavior and accessibility

- At 1440 px: compact left navigation, two-column overview/quality composition, 2×2 MRI viewer with a contextual side panel.
- At 1024 px: narrower navigation, stacked context below or beside one enlarged viewer; retain named actions.
- At 768 px: collapsible navigation, single-column summary, progressive disclosure for secondary columns.
- At 390 px: readable study list summaries, one sequence viewer, tabs for context, full-width reviewed actions. Dense comparative tables get an explicitly labeled local scroll region rather than overflowing the whole page.
- Verify text contrast to at least 4.5:1 for normal text, visible keyboard focus, semantic headings/tables, labeled inputs, keyboard-operable filters and dialogs, and useful screen-reader status messages.
- Dialog focus is contained and returns to the initiating action. Errors identify the failed field or operation and preserve user input.
- Target controls at 44×44 px where practical. Provide explicit buttons for actions that would otherwise depend on drag, hover or color.
- Respect reduced motion. Use brief transitions for state feedback, not animated KPI counters or decorative charts.

## 10. Required states and verification

| State | Required presentation |
| --- | --- |
| First use | Import/source instructions and a labeled sample option |
| Loading | Stable placeholders and busy status; no zero-valued metrics |
| Backend unavailable | Clear error and retry; retain stale data only with freshness warning |
| No records match | Show active filters and Clear filters |
| Clinical data missing | Exact join/field status and source action |
| Missing MRI inputs | Named missing roles, inference skipped, quality queue link |
| Model running/failed | Real job state, prerequisites and retry guidance |
| Cold originals | Preview status distinct from original availability; restore action |
| Transition/restore pending | Requested/observed state and required member counts |
| Partial failure | Failed members and preserved successful results |
| Insufficient permission | Reason and current role; server enforces action restrictions |
| Synthetic scenario | Persistent provenance label on metrics and exports |

The UI implementation must pass one complete user journey: import a permitted cohort, inspect a verified clinical join and MRI analysis, resolve a missing-input case, review a constraint-driven recommendation, request placement, inspect mixed member state, and track a full-study restore. Keyboard and 1440/1024/768/390 px checks are release requirements. No claim of completed UI testing is made by this specification.
