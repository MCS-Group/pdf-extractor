@echo off
echo Starting PDF API Server...
echo.
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000