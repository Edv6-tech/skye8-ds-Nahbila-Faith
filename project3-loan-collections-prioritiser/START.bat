@echo off
:: ═══════════════════════════════════════════════════════════════
:: Skye8 Credit Union Collections System — Startup Script
:: Run this file to start both the API server and the dashboard.
:: ═══════════════════════════════════════════════════════════════
title Skye8 Collections System

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║    Skye8 Credit Union Collections Intelligence System    ║
echo  ║              Starting all services...                    ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10 or higher.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [1/3] Checking Python dependencies...
pip install -r requirements.txt --quiet
echo       Dependencies OK.

:: Start API Server (port 8080) in background
echo [2/3] Starting API Server on port 8080...
start "Skye8-API-Server" /MIN cmd /c "set PYTHONPATH=. && python app/server.py"
timeout /t 2 /nobreak >nul
echo       API Server started.

:: Start Streamlit Dashboard (port 8501) in background
echo [3/3] Starting Dashboard on port 8501...
start "Skye8-Dashboard" /MIN cmd /c "python -m streamlit run app/app.py --server.port 8501 --server.headless true"
timeout /t 3 /nobreak >nul
echo       Dashboard started.

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  SYSTEM READY                                            ║
echo  ║  Dashboard:  http://localhost:8501                       ║
echo  ║  API Server: http://localhost:8080/api/v1/health         ║
echo  ║                                                          ║
echo  ║  Press any key to open the dashboard in your browser.   ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
pause >nul
start http://localhost:8501
