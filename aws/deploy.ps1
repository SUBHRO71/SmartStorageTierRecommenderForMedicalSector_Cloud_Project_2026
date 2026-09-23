param(
    [string]$Region = "us-east-1",
    [string]$StackName = "smart-storage-tier",
    [string]$NotificationEmail = ""
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$AwsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $AwsDir

function Assert-LastCommand([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

$AccountId = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) { throw "AWS credentials are not configured or are invalid." }

$ArtifactBucket = "$StackName-artifacts-$AccountId-$Region".ToLower()
aws s3api head-bucket --bucket $ArtifactBucket 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($Region -eq "us-east-1") {
        aws s3api create-bucket --bucket $ArtifactBucket --region $Region | Out-Null
        Assert-LastCommand "Create artifact bucket"
    } else {
        aws s3api create-bucket --bucket $ArtifactBucket --region $Region --create-bucket-configuration LocationConstraint=$Region | Out-Null
        Assert-LastCommand "Create artifact bucket"
    }
}

python "$AwsDir\lambda\api_handler\build_package.py"
Assert-LastCommand "Build API Lambda"
python "$AwsDir\lambda\tier_inference\build_package.py"
Assert-LastCommand "Build inference Lambda"

$PackagedTemplate = Join-Path $AwsDir "packaged.yaml"
aws cloudformation package --template-file "$AwsDir\template.yaml" --s3-bucket $ArtifactBucket --output-template-file $PackagedTemplate --region $Region
Assert-LastCommand "Package CloudFormation stack"
aws cloudformation deploy --template-file $PackagedTemplate --stack-name $StackName --capabilities CAPABILITY_IAM --region $Region --parameter-overrides "NotificationEmail=$NotificationEmail"
Assert-LastCommand "Deploy CloudFormation stack"

function Get-StackOutput([string]$Key) {
    $Value = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue | [0]" --output text
    Assert-LastCommand "Read $Key stack output"
    if (-not $Value -or $Value -eq "None") { throw "Stack output $Key is missing." }
    return $Value
}

$ApiUrl = Get-StackOutput "ApiUrl"
$UserPoolId = Get-StackOutput "UserPoolId"
$UserPoolClientId = Get-StackOutput "UserPoolClientId"
$FrontendBucket = Get-StackOutput "FrontendBucketName"
$DistributionId = Get-StackOutput "FrontendDistributionId"
$FrontendDir = Join-Path $ProjectDir "src\frontend"
$ProductionEnv = Join-Path $FrontendDir ".env.production.local"

@(
    "VITE_API_URL=$ApiUrl"
    "VITE_USE_MOCK_API=false"
    "VITE_COGNITO_USER_POOL_ID=$UserPoolId"
    "VITE_COGNITO_CLIENT_ID=$UserPoolClientId"
    "VITE_AWS_REGION=$Region"
) | Set-Content -LiteralPath $ProductionEnv -Encoding utf8

Push-Location $FrontendDir
try {
    npm ci
    Assert-LastCommand "Install frontend dependencies"
    npm run build
    Assert-LastCommand "Build frontend"
    aws s3 sync dist "s3://$FrontendBucket" --delete --region $Region
    Assert-LastCommand "Publish frontend"
} finally {
    Pop-Location
}
aws cloudfront create-invalidation --distribution-id $DistributionId --paths "/*" | Out-Null
Assert-LastCommand "Invalidate CloudFront"

Write-Output "Deployment complete: $(Get-StackOutput 'FrontendUrl')"
Write-Output "Create a Cognito user and add it to viewer, archive-admin, or operator before signing in."
