# Local backend

This Flask API runs the complete product locally. SQLite is the default and requires no AWS credentials. Set `DATA_BACKEND=dynamodb` only when intentionally connecting this adapter to an existing AWS table.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r src/backend/requirements.txt
python src/backend/app.py
```

The server listens on `http://127.0.0.1:5000`. On first start it creates an ignored SQLite database, migrates its schema, and seeds public/demo metadata through the shared decision engine. Existing seed rows are refreshed when the checked-in policy version changes. The database includes append-only audit events for prediction, tier override, and restore actions.

## Environment

Copy `.env.example` only when overrides are needed. The application does not automatically load `.env`; export values through the shell or a process manager.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATA_BACKEND` | `sqlite` | `sqlite` or explicit `dynamodb` |
| `LOCAL_DB_PATH` | `local_scans.db` beside the code | Ignored local database path |
| `TABLE_NAME` | `ScanFeatures` | Existing DynamoDB table in cloud adapter mode |
| `AWS_DEFAULT_REGION` | `us-east-1` | SDK region; credentials use the standard AWS chain |
| `AUTH_MODE` | `local` | Execution-mode value returned by health |
| `CORS_ORIGIN` | both local Vite origins | Comma-separated allowed browser origins |
| `PORT` | `5000` | Flask port |

## API

- `GET /api/health`
- `GET /api/scans?page=1&limit=20&tier=ALL&search=`
- `GET /api/scans/{id}`
- `POST /api/scans/{id}/predict`
- `POST /api/scans/{id}/tier` with `{ "tier": "...", "reason": "..." }`
- `POST /api/scans/{id}/restore`
- `GET /api/dashboard/summary`
- `GET /api/costs?horizon=12`

Inputs are bounded and errors use a stable `{error: {code, message, request_id}}` shape. Local tier transitions and restores are simulated synchronously; AWS keeps transitions pending until S3 state is reconciled.

## Verify

```powershell
python -m unittest tests.test_backend_api -v
```

Never place AWS keys or patient-identifying data in this directory.
