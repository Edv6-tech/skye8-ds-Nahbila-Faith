@echo off
TITLE Skye8 Loan Collections Prioritiser — Production Server Launcher
echo =========================================================================
echo SKYE8 LOAN COLLECTIONS PRIORITISER — PRODUCTION ENTERPRISE LAUNCHER
echo =========================================================================

IF NOT EXIST .env (
    echo [!] WARNING: .env file not found. Copying .env.example to .env ...
    copy .env.example .env
    echo [+] Created default .env file. Please edit .env with your live API credentials.
)

echo [1/3] Verifying Python environment and dependencies...
python -m pip install -r requirements.txt

echo [2/3] Executing pipeline & validating multi-task models...
python run_pipeline.py

echo [3/3] Launching Production REST API and Streamlit UI...
start "Skye8 Production API" /B python app/server.py
streamlit run app/app.py --server.port 8501

echo =========================================================================
echo Server active at http://localhost:8501
echo =========================================================================
pause
