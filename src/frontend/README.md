# Frontend

The React/Vite UI provides local and AWS-backed workflows for sign-in, dashboard metrics, scan search/filtering, decision explanations, tier overrides, restores, audit events, and policy cost comparisons.

## Setup

```powershell
cd src/frontend
npm ci
npm start
```

Open `http://127.0.0.1:5173`. With no Cognito values, the sign-in screen clearly identifies local mock authentication and displays the demo identity. API data remains live unless mock API mode is explicitly enabled.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:5000/api` | Backend API root |
| `VITE_USE_MOCK_API` | `false` | Explicit static fixture mode |
| `VITE_COGNITO_USER_POOL_ID` | empty | Enables real Cognito authentication |
| `VITE_COGNITO_CLIENT_ID` | empty | Cognito browser client |
| `VITE_AWS_REGION` | `us-east-1` | Cognito region |

Anything prefixed with `VITE_` is public browser configuration. Never put AWS access keys or secrets there.

## Build

```powershell
npm run build
npm audit
```

Vite writes the production site to `dist/`. Live API failures render error states; they never become successful mock mutations. The navbar identifies whether the data client is in live or explicit mock mode.
