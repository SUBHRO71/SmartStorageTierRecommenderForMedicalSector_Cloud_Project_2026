param(
    [string]$Region = "us-east-1",
    [string]$StackName = "cloudtier-v2",
    [string]$NotificationEmail = "",
    [string]$ExpectedAccount = "657878533811"
)
$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectDir
try {
    python aws/build_template.py
    if ($LASTEXITCODE -ne 0) { throw "Template generation failed" }
    cfn-lint aws/template.yaml
    if ($LASTEXITCODE -ne 0) { throw "Template validation failed" }
    Push-Location src/frontend
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    } finally { Pop-Location }
    $DeployArgs = @("aws/deploy.py", "--region", $Region, "--stack", $StackName, "--expected-account", $ExpectedAccount)
    if ($NotificationEmail) { $DeployArgs += @("--notification-email", $NotificationEmail) }
    python @DeployArgs
    if ($LASTEXITCODE -ne 0) { throw "AWS deployment did not complete. Inspect CloudFormation and bootstrap logs." }
} finally { Pop-Location }
