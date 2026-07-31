# presentation/

Review slides and demonstration material. **Owned by all three members** — every member presents.

## What goes here

| File | Purpose |
| --- | --- |
| `Phase1_Review.pptx` | Slide deck for the Phase-I review |
| `demo_video.mp4` | Recorded demo, as a fallback if the live demo fails |
| `demo_script.md` | Step-by-step script for the live demonstration |

If the video is too large for Git (over 50 MB), upload it elsewhere and commit a link here.

## Suggested slide flow

| # | Slide | Point to land |
| --- | --- | --- |
| 1 | Title | Project, team, course |
| 2 | Problem | Hospitals hold huge scan archives; hot storage is expensive, archive is too slow for a doctor |
| 3 | Existing approaches | Age-based rules and S3 Intelligent-Tiering — and why they are not enough |
| 4 | Literature survey | The 15 papers, summarised |
| 5 | Research gap | The one slide that matters most — see below |
| 6 | Objectives | What we will build, stated measurably |
| 7 | System architecture | The logical view |
| 8 | AWS architecture | The deployment view |
| 9 | Dataset | What we use, and honesty about the label being a derived proxy |
| 10 | Implementation status | What is working now |
| 11 | Results | Cost saving, and how often a needed scan was wrongly archived |
| 12 | Novelty | What is new here |
| 13 | Individual contributions | Who did what, with GitHub evidence |

## The research gap slide

Make this one land, because it is what the project is judged on. It reduces to two sentences:

> Storage systems research has built fast, accurate learning-based tiering — but feeds it only
> block-level behaviour and has never tested it on medical data.
> Medical imaging research has rich deep learning models and full hospital platforms — but uses
> them only to help the doctor, never to manage the storage underneath.

Then the punchline: **nobody has joined the two.**

The strongest concrete illustration is Sibyl's six inputs — request size, read/write, access
interval, access count, free space, current location. Every one describes behaviour; not one
describes what the data *is*. A hospital already knows the modality, body part, patient age and
urgency at the moment a scan is created, free, in the DICOM header — and every existing system
throws it away.

## Be ready for these questions

- Why should a scan's *content* predict whether it will be retrieved?
- How is the training label obtained, given hospitals do not publish access logs?
  (Answer honestly: it is a derived proxy — see [`../dataset/README.md`](../dataset/README.md).)
- What happens when the model is wrong and a doctor needs an archived scan?
- Why not just use S3 Intelligent-Tiering?
- What is your individual contribution? — every member will be asked this separately, with their
  commit log open.

## Practical

- Keep text on slides minimal. Explain in speech, not on the slide.
- Every graph gets labelled axes and a legend.
- Rehearse the live demo on the machine and network you will actually use. Have the recorded video
  ready regardless.
- Export a PDF copy of the deck as a backup — PowerPoint version differences ruin layouts.
