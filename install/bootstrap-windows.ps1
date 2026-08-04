#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [string]$RepoUrl,
    [string]$Ref,
    [string]$Dest,
    [string]$Target,
    [ValidateSet("none", "minimal", "full")]
    [string]$Deps,
    [switch]$DryRun,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Bootstrap = Join-Path $RepoRoot "scripts/forge_bootstrap.py"
$Args = @()

if ($RepoUrl) { $Args += @("--repo-url", $RepoUrl) }
if ($Ref) { $Args += @("--ref", $Ref) }
if ($Dest) { $Args += @("--dest", $Dest) }
if ($Target) { $Args += @("--target", $Target) }
if ($Deps) { $Args += @("--deps", $Deps) }
if ($DryRun) { $Args += "--dry-run" }
if ($Json) { $Args += "--json" }

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & python $Bootstrap @Args
    exit $LASTEXITCODE
}

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
    & py -3 $Bootstrap @Args
    exit $LASTEXITCODE
}

$OutputDir = Join-Path $RepoRoot "artifacts/bootstrap/latest"
$OutputPath = Join-Path $OutputDir "install-prerequisites.ps1"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
@'
param([switch]$Apply)
$ErrorActionPreference = "Stop"
if (-not $Apply) {
    Write-Output "dry-run packages: Git.Git, Python.Python.3.12"
    Write-Output "reversal: winget uninstall --exact --id Git.Git; winget uninstall --exact --id Python.Python.3.12"
    exit 0
}
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this reviewed script from an elevated PowerShell session."
}
winget install --exact --id Git.Git --accept-package-agreements --accept-source-agreements
winget install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
git --version
python --version
Write-Output "reversal: winget uninstall --exact --id Git.Git; winget uninstall --exact --id Python.Python.3.12"
'@ | Set-Content -Path $OutputPath -Encoding utf8
Write-Error "moradin-forge bootstrap: Python 3 is required. Review $OutputPath and run it with -Apply from a user-approved PowerShell session."
exit 127
