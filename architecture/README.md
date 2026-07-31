# architecture/

All **diagrams** for the project, plus the editable source files used to produce them.

> **STATUS: The architecture is still under discussion.** Nothing here is final. Do not build
> against these diagrams until the team has agreed and the root [`README.md`](../README.md)
> section 2 has been filled in.

## What goes here

| File | Shows | Owner |
| --- | --- | --- |
| `System_Architecture.png` | Logical view — components, what each is responsible for, how data moves between them | Student 2 |
| `AWS_Architecture.png` | Deployment view — which AWS services are used, VPC/subnet layout, IAM boundaries, where data lives | Student 2 |
| `Workflow.png` | Sequence view — a scan's journey from ingest through feature extraction, prediction and tier assignment | Student 2 |

## Also commit the source files

Export the `.png` for the report, but **always commit the editable source alongside it**
(`.drawio`, `.excalidraw`, `.svg`, or the `.puml`/`.mmd` text). A PNG alone cannot be edited later,
and diagrams always need editing.

Suggested free tools: [draw.io](https://app.diagrams.net) (has an official AWS icon set),
[Excalidraw](https://excalidraw.com), or Mermaid/PlantUML if you prefer diagrams as text.

## Conventions

- **Resolution:** export at 300 DPI or higher. Diagrams that look fine on screen turn into mush
  when printed into a report or projected at a review.
- **AWS icons:** use the official AWS Architecture Icons set. Faculty recognise them, and hand-drawn
  boxes labelled "S3" look careless.
- **Label every arrow** with what actually flows along it — "DICOM metadata", "tier decision",
  "feature vector" — not bare arrowheads.
- **Legend:** if you use colour to mean something (e.g. storage tier), include a legend.
- Keep the three views genuinely distinct. `System_Architecture` is about *responsibility*,
  `AWS_Architecture` is about *deployment*, `Workflow` is about *sequence*. Do not draw the same
  picture three times.

## Open questions blocking these diagrams

These must be settled before the diagrams can be drawn:

- [ ] Where does the model run — Lambda at ingest, a scheduled batch job, or both?
- [ ] Are tier decisions applied directly through the S3 API, or expressed as S3 Lifecycle rules?
- [ ] Does the image-feature model run on every scan, or only on a sample?
- [ ] Where is DICOM metadata indexed and queried from?
- [ ] Which storage classes are in scope — all four, or a reduced set?
- [ ] Which AWS services does each member own, for the individual-defence requirement?

Record decisions and rejected alternatives in `architecture/decisions.md` as they are made.
Being able to say *why* an option was rejected is worth marks at review.
