@echo off
echo Starting pdf API Server...
echo.
python -m uvicorn dummy:app --reload --host 0.0.0.0 --port 8001