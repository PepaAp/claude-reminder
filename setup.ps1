#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UvInstallUrl = "https://docs.astral.sh/uv/getting-started/installation/"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "Error: uv is not installed or not on PATH.`nInstall uv from: $UvInstallUrl"
    exit 1
}

Set-Location $RootDir
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run python setup.py @args
exit $LASTEXITCODE
