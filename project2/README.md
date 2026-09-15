# Skye8 DS PR3-005 — Predicting Customs Clearance Delay

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Data
Download the four CSVs from the Skye8 platform into `data/raw/`.
They are git-ignored and must never be committed.

## Pipeline (run in order)
```bash
python -m src.clean      # writes data/processed/*.csv
python -m src.split      # sanity-check the time-based split
python -m src.baseline   # Stage A: majority-class + raw-column baselines
```

## Tests
```bash
pytest tests/ -v
```
