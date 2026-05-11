#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForgeArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($Uv) {
    & uv run python (Join-Path $RepoRoot "scripts/moradin_forge.py") @ForgeArgs
    exit $LASTEXITCODE
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & python (Join-Path $RepoRoot "scripts/moradin_forge.py") @ForgeArgs
    exit $LASTEXITCODE
}

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
    & py -3 (Join-Path $RepoRoot "scripts/moradin_forge.py") @ForgeArgs
    exit $LASTEXITCODE
}

Write-Error "moradin-forge: Python 3 is required; write an install request from another host or install Python manually."
exit 127
