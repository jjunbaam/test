@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.ps1 in PowerShell first.
  exit /b 1
)
if not exist "config.local.json" (
  echo Copy config.example.json to config.local.json and review settings first.
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn portal.app:app --host 127.0.0.1 --port 8000
