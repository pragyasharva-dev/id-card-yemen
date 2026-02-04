
@echo off
echo Starting e-KYC API Server...
".\.venv\Scripts\uvicorn.exe" main:app --reload
pause
