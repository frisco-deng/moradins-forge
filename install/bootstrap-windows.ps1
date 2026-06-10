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

Write-Error "moradin-forge bootstrap: Python 3 is required. No host install commands were run."
exit 127
