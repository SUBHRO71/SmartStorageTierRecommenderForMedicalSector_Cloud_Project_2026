# Retired v1 deployment

The previous SAM template and deployment script are preserved here, including
the changes already present before the v2 migration. They are historical reference
only. The active deployment is `aws/deploy.ps1` with the v2 `aws/template.yaml`.
Old Lambda code under `aws/lambda` and v1 fixtures remain for regression/history;
they are not included in the v2 release or deployed. The v1 frontend routes are
removed from the active application.

Do not run this historical script: its relative packaging paths no longer refer
to a supported deployment layout.
