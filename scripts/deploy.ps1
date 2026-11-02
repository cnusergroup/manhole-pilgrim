# Deploy web/ to AWS Amplify Hosting (manual zip deployment, no Git connection needed).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
param(
  [string]$AppId = "d1y4wxk0wltj16",
  [string]$Branch = "main",
  [string]$Region = "ap-northeast-1"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot
$zip = Join-Path $env:TEMP "manhole-pilgrim-web.zip"
if (Test-Path $zip) { Remove-Item $zip }
python -c "import shutil,sys; shutil.make_archive(sys.argv[1][:-4], 'zip', sys.argv[2])" $zip (Join-Path $root "web")

$dep = aws amplify create-deployment --region $Region --app-id $AppId --branch-name $Branch --output json | ConvertFrom-Json
Invoke-WebRequest -Uri $dep.zipUploadUrl -Method Put -InFile $zip -ContentType "application/zip" -UseBasicParsing | Out-Null
aws amplify start-deployment --region $Region --app-id $AppId --branch-name $Branch --job-id $dep.jobId --output json | Out-Null

do {
  Start-Sleep -Seconds 4
  $status = (aws amplify get-job --region $Region --app-id $AppId --branch-name $Branch --job-id $dep.jobId --output json | ConvertFrom-Json).job.summary.status
  Write-Host "job $($dep.jobId): $status"
} while ($status -in @("PENDING", "PROVISIONING", "RUNNING"))

Remove-Item $zip
Write-Host "https://$Branch.$AppId.amplifyapp.com"
if ($status -ne "SUCCEED") { exit 1 }
