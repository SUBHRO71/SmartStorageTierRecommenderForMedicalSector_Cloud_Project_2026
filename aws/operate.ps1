param(
    [ValidateSet("Start", "Stop", "Status", "Backup")][string]$Action = "Status",
    [string]$Region = "us-east-1",
    [string]$StackName = "cloudtier-v2"
)
$ErrorActionPreference = "Stop"
$InstanceId = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue | [0]" --output text
if ($LASTEXITCODE -ne 0 -or -not $InstanceId -or $InstanceId -eq "None") { throw "The study server could not be found" }
switch ($Action) {
    "Start" { aws ec2 start-instances --instance-ids $InstanceId --region $Region }
    "Stop" { aws ec2 stop-instances --instance-ids $InstanceId --region $Region }
    "Status" { aws ec2 describe-instances --instance-ids $InstanceId --region $Region --query "Reservations[0].Instances[0].{State:State.Name,Type:InstanceType,Id:InstanceId}" }
    "Backup" {
        $Parameters = @{ commands = @("systemctl start cloudtier-backup.service") } | ConvertTo-Json -Compress
        $TaskDir = Join-Path (Split-Path -Parent $PSScriptRoot) "temp/aws-v2"
        New-Item -ItemType Directory -Path $TaskDir -Force | Out-Null
        $ParametersPath = Join-Path $TaskDir "backup-command.json"
        [System.IO.File]::WriteAllText($ParametersPath, $Parameters, [System.Text.UTF8Encoding]::new($false))
        aws ssm send-command --instance-ids $InstanceId --document-name AWS-RunShellScript --parameters "file://$ParametersPath" --region $Region --query Command.CommandId --output text
    }
}
if ($LASTEXITCODE -ne 0) { throw "Server operation failed" }
