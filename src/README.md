# src/

All application source code. Split into three components, each owned by one team member so that
individual contribution is visible in the commit history.

| Folder | Component | Owner |
| --- | --- | --- |
| [`frontend/`](frontend/) | User interface — dashboard, scan browser, tier visualisation | Pratyush Chandrasekhar |
| [`backend/`](backend/) | REST API, database, authentication, AWS integration | Subhrojyoti Das |
| [`ml_model/`](ml_model/) | Preprocessing, training, inference, evaluation | Mehul Anand |

## How the three fit together

```
frontend  ──HTTP──>  backend  ──calls──>  ml_model
                        │
                        └──> AWS (S3, storage tier actions)
```

The frontend never talks to the model directly and never touches AWS directly — everything goes
through the backend. This keeps credentials in exactly one place and means the frontend can be
developed against a mock API before the model is ready.

## Shared conventions

- **Language:** Python for backend and ML. Frontend framework to be decided by Pratyush Chandrasekhar.
- **Config:** never hardcode a path, bucket name, endpoint or credential. Read it from an
  environment variable or a config file. Commit a `.env.example` listing the variables needed,
  never the `.env` itself.
- **Dependencies:** each component pins its own (`requirements.txt` or `package.json`). Anyone
  should be able to install and run a component without the other two.
- **Commits:** small and meaningful. `fix: handle missing DICOM modality tag` is useful at review;
  `update` is not.
- **Never commit:** AWS keys, `.env` files, model weights over 50 MB, dataset files, `__pycache__`,
  `node_modules`.

## Interface contract

Because three people build these in parallel, the boundaries need to be agreed **before** coding
starts, not discovered during integration:

- [ ] Backend → ML: what exactly does the model receive, and what does it return?
- [ ] Frontend → Backend: what are the API endpoints and their response shapes?
- [ ] Backend → AWS: which services, and who holds the credentials?

Write these down in this file once agreed. An hour spent on this saves a painful integration week.
