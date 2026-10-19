@echo off
echo ========================================================
echo   GitLab QA Impact Analyzer - Local Server Starting...
echo ========================================================
echo.
echo Opening Web Portal at http://localhost:8000
echo.
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
