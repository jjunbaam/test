$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run .\setup.ps1 first.' }
if (-not (Test-Path 'config.local.json')) { throw 'Copy config.example.json to config.local.json and review settings.' }
Write-Host 'Open http://127.0.0.1:8000 on this PC. Ctrl+C stops the portal.'
& .\.venv\Scripts\python.exe -m uvicorn portal.app:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
