@echo off
title Skye8 Intelligence — Launcher
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   SKYE8 LOAN COLLECTIONS INTELLIGENCE — PRODUCTION      ║
echo  ║   Bamenda Credit Union · Mezam Division, Cameroon        ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ─── Check Python ───────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.9+ and add to PATH.
    pause
    exit /b 1
)

:: ─── Install dependencies if needed ─────────────────────────────────────
echo  [1/3] Checking dependencies...
python -m pip install -q -r requirements.txt
echo  [1/3] Dependencies ready.
echo.

:: ─── Start Backend API Server (port 8080) ───────────────────────────────
echo  [2/3] Starting Skye8 REST API Server (port 8080)...
start "Skye8 API Server :8080" /min cmd /c "python app\server.py"
timeout /t 2 >nul

:: ─── Start Streamlit Frontend (port 8501) ───────────────────────────────
echo  [3/3] Starting Skye8 UI (Streamlit port 8501)...
start "Skye8 UI :8501" /min cmd /c "python -m streamlit run app\app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false"
timeout /t 4 >nul

echo.
echo  ✳  SKYE8 IS RUNNING:
echo     UI Dashboard  →  http://localhost:8501
echo     REST API      →  http://localhost:8080/api/v1/status
echo.
echo  Close this window or press Ctrl+C to stop all servers.
echo.

:: Keep window alive to show status
:loop
timeout /t 60 >nul
goto loop
