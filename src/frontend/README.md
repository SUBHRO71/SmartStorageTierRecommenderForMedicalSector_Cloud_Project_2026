# src/frontend/

The user interface. **Owner: Pratyush Chandrasekhar.**

## What this component does

Gives a human a way to see and interrogate what the system is doing. Without it the project is
just a script producing numbers, and there is nothing to demonstrate at review.

Planned screens:

| Screen | Shows |
| --- | --- |
| Dashboard | Scans by storage tier, total storage cost, projected saving vs. keeping everything hot |
| Scan browser | Searchable list of scans with modality, body part, age, current tier, predicted tier |
| Scan detail | One scan — its DICOM metadata, access history, model prediction, and *why* the model chose that tier |
| Cost comparison | Our tiering vs. all-hot vs. a simple age-based rule |

The scan detail view matters most. A faculty member will ask "why did it put that scan in Glacier?"
and the interface should answer that directly.

## Rules

- **Talk only to the backend API.** No direct AWS calls, no direct database access, no credentials
  in frontend code — anything in the browser is public.
- **No patient-identifiable information on screen.** Use study IDs, never names or dates of birth.
- Build against a mock API first so this component is not blocked waiting for the backend.

## Setup

To be filled in by Pratyush Chandrasekhar once the framework is chosen. Must include:

- Prerequisites and versions
- Install command
- How to run locally
- Which environment variables are needed (and commit a `.env.example`)

## Do not commit

`node_modules/`, build output (`dist/`, `build/`), `.env`.
