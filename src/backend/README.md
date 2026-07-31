# src/backend/

API layer, database integration, authentication, and the bridge to AWS. **Owner: Student 2.**

## What this component does

The backend is the only part of the system that holds credentials and the only part that talks to
AWS. Everything else goes through it.

Responsibilities:

| Responsibility | Detail |
| --- | --- |
| REST API | Serves the frontend — scan lists, scan detail, cost summaries |
| Database | Stores scan metadata, access history, and predicted tiers |
| Authentication | Login and access control |
| ML integration | Calls the model in [`../ml_model/`](../ml_model/) and stores the result |
| AWS integration | Applies tier decisions to S3 and reads back actual storage state |

## Planned endpoints

To be finalised with Student 1 before the frontend is built:

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/api/scans` | Paginated scan list with current and predicted tier |
| `GET` | `/api/scans/{id}` | One scan — metadata, access history, prediction, explanation |
| `POST` | `/api/scans/{id}/predict` | Runs the model for one scan |
| `GET` | `/api/costs` | Cost summary and comparison against baselines |
| `POST` | `/api/scans/{id}/tier` | Applies a tier change |

## Rules

- **Credentials come from environment variables only.** Never hardcode an AWS key, database
  password or endpoint. Commit `.env.example` listing the variable names; never commit `.env`.
- **Least privilege IAM.** The role this service uses should be able to do exactly what it needs
  to S3 and nothing more. Do not attach an admin policy because it is quicker.
- **Validate every input.** Anything arriving from the frontend is untrusted.
- **Log the tier decisions.** When a scan is moved, record what moved, when, and why. This
  produces the audit trail that a real hospital deployment would require — and gives us results
  to show at review.
- Never log patient-identifiable data.

## Setup

To be filled in by Student 2. Must include:

- Python version and how to create the virtual environment
- `pip install -r requirements.txt`
- Required environment variables
- How to run the database locally
- How to start the server

## Do not commit

`.env`, `__pycache__/`, `*.pyc`, `venv/`, database files, any file containing an AWS key.
