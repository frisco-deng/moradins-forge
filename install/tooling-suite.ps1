#!/usr/bin/env pwsh

$ErrorActionPreference = 'Stop'
$ForwardedArgs = $args
$ForgeRoot = Split-Path -Parent $PSScriptRoot
$Suite = Join-Path $ForgeRoot 'scripts/moradin_tooling_suite_native.py'
$Python = Get-Command python -ErrorAction SilentlyContinue

if ($Python) {
    & $Python.Source $Suite --platform windows --forge-root $ForgeRoot @ForwardedArgs
    exit $LASTEXITCODE
}

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
    & $Py.Source -3 $Suite --platform windows --forge-root $ForgeRoot @ForwardedArgs
    exit $LASTEXITCODE
}

Write-Error 'Python 3.11+ is required. Install the signed Python package with WinGet after review, then rerun this entrypoint.'
exit 2
