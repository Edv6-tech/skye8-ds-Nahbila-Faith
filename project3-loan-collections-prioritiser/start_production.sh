#!/usr/bin/env bash
set -e

echo "========================================================================="
echo "SKYE8 LOAN COLLECTIONS PRIORITISER — PRODUCTION ENTERPRISE LAUNCHER"
echo "========================================================================="

if [ ! -f .env ]; then
    echo "[!] WARNING: .env file not found. Copying .env.example to .env ..."
    cp .env.example .env
    echo "[+] Created default .env file. Please edit .env with your live API credentials."
fi

echo "[1/3] Verifying Python environment and dependencies..."
pip install -r requirements.txt

echo "[2/3] Executing pipeline & validating multi-task models..."
python run_pipeline.py

echo "[3/3] Launching Production REST API (Port 8080) and Streamlit UI (Port 8501)..."
python app/server.py &
streamlit run app/app.py --server.port 8501 --server.address 0.0.0.0
