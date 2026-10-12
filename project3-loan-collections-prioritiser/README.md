# Loan Collections Prioritiser (Bamenda Microfinance)

**Project Reference:** `SKY8-DS-FP-005` | **Roadmap:** `SKY8-DS-RM-005` (Core ML)  
**Candidate:** Nahbila Faith  
**Institution / Track:** Skye8 Company Ltd — Data Science and ML / AI Internship Track  
**Supervisors:** Engr. Soh Juvitus, Engr. Muyah Gaious, Engr. Linjo Ryan  
**Evaluation Date:** October 2, 2026  

---

## 📌 Executive Overview
A microfinance institution in Bamenda, Cameroon has **400 delinquent borrowers** ($\ge 15$ days past due) and **3 collections officers** (John, Beatrice, Emmanuel).

The incumbent heuristic sorts borrowers by debt size (**"Biggest Debt First"**). This wastes officer time and transport expenditure on completely insolvent accounts, while salvageable debts turn into permanent non-performing loans (NPLs).

This project delivers the **Loan Collections Prioritiser**:
* **📱 Live Mobile Production Demo:** `https://medical-capability-communities-sentence.trycloudflare.com` (Works on any smartphone worldwide, zero login required).
* Evaluated and cross-validated on **two independent real-world loan portfolios**:
  1. **Home Credit Default Risk:** 2.5M records, 36,934 isolated arrears events, 11.94% unassisted base cure rate.
  2. **LendingClub Loan Data (`accepted_2007_to_2018Q4.csv`):** 350,000 records, 64,328 isolated arrears events (18.38%), 68.49% unassisted recovery rate, $56.68M recovered dollars.
* Predicts recovery probability given arrears ($\mathbb{P}(\text{Recovery} \mid \text{Arrears})$) with **zero future data leakage**.
* Estimates **Time-to-Cure** (Survival hazard regressor) and **Partial Settlement Ratio** ($\hat{r}$).
* Prioritizes the weekly 400-account book by **Expected Recoverable Value** ($P \times \hat{r} \times \text{Debt}$).
* Recommends the optimal, cost-weighted contact method (**SMS**, **Phone Call**, **Field Visit**).
* Clusters field visits across 5 Bamenda Quarters, cutting motorcycle (**benskin**) fuel by ~60%.
* Features **Bilingual Outreach Scripts** (Formal English & Cameroon Pidgin English) and **Printable Field Dockets** with tear-off pledge slips.
* Houses an **Adaptable Engine (`AdaptablePrioritiser`)** featuring branch archetype shifting, live Bayesian online field feedback, and macroeconomic fuel/airtime shock recalibration.
* Embeds **ethical safeguards** protecting vulnerable and senior borrowers from harassment (18.5% protected).
* **Quantified Impact:**
  - **Home Credit (Bamenda Portfolio):** Increases **Precision@100 from 7.0% to 88.0%** (12.57x cure lift) and generates **+2,164,156 FCFA (+65.6%)** in net cash per 100 worked accounts.
  - **LendingClub (Global Arrears Benchmark):** Increases **Precision@50 from 72.0% to 90.0%** and generates **+$45,871 USD (+11.4%)** in net cash per 100 accounts (**+$73,403 USD** across 400 accounts).

---

## 🚀 Quickstart: Reproducing in 4 Steps

### 1. Environment Setup
Clone the repository and install dependencies:
```bash
git clone https://github.com/skye8-org/skye8-ds-fp-nahbila-faith.git
cd skye8-ds-fp-nahbila-faith

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Automated Test Suite (Leakage & Adaptability)
Verify zero post-contact data leakage and test multi-task model adaptation:
```bash
pytest tests/
```
*Result: `15 passed in ~11s` (100% green).*

### 3. Run Pipeline & Train All Models
Execute the end-to-end multi-task training, survival regression, and evaluation pipeline:
```bash
python run_pipeline.py
```
This ingests multi-source data, builds behavioral features, trains and calibrates the Gradient Boosting classifier, fits the survival regressor and partial recovery regressor, computes causal uplift and XAI waterfalls, and outputs the production call book to `data/processed/weekly_400_accounts.csv`.

To run the LendingClub benchmark evaluation:
```bash
python scratch/benchmark_lendingclub.py
```

### 4. Launch the Production Web Application (Mobile-Ready)
```bash
python -m app.server
```
Open your browser at **`http://localhost:8080`**, or open the public tunnel on any smartphone:
**`https://benefit-irc-sleeve-findarticles.trycloudflare.com`**.

---

## 📊 Key Evaluation Benchmark (Top 50 & Top 100 Accounts)

Evaluated on 9,219 unseen delinquent accounts on the held-out test partition:

| Metric | Incumbent Heuristic (Biggest Debt First) | ML Prioritiser (Expected Value) | Gain / Lift |
| :--- | :--- | :--- | :--- |
| **Precision @ 50 Accounts** | 14.00% | **90.00%** | **6.43x higher cure rate** |
| **Precision @ 100 Accounts** | 7.00% | **88.00%** | **12.57x higher cure rate** |
| **Cash Recovered (Top 50)** | 3,301,388 FCFA | **4,557,608 FCFA** | **+1,256,220 FCFA (+38.1%)** |
| **Cash Recovered (Top 100)** | 3,301,388 FCFA | **5,465,544 FCFA** | **+2,164,156 FCFA (+65.6%)** |
| **Model ROC-AUC** | — | **0.9864** | State-of-the-art discrimination |
| **Model PR-AUC** | — | **0.9288** | Calibrated recovery probabilities |
| **Average Settlement Ratio** | — | **66.2%** | Partial recovery regressor ($\hat{r}$) |
| **Mean Time-to-Cure** | — | **14.6 days** | Survival hazard estimation |

---

## 🎛️ Model Adaptability Architecture (`AdaptablePrioritiser`)

The core machine learning engine is built for continuous operational adaptation:
1. **Branch Archetype Adaptation:** Adjusts baseline prior log-odds intercepts across *Urban Commercial* (Mankon), *Agrarian Rural* (Coffee farming outskirts), and *Civil Servant Payroll* (Up Station).
2. **Online Bayesian Field Feedback:** As officers log contact outcomes in the app (*"Promise to Pay"*, *"Cured & Settled"*, *"Severe Hardship"*), the engine recalibrates the borrower's probability in real time.
3. **Macroeconomic Unit Cost Recalibration:** Recalculates channel economics live when motorcycle fuel (*essence*) or phone call airtime costs fluctuate.
4. **Missing Modality Resilience:** Graceful domain fallback when new credit unions lack Credit Bureau or POS Cash records.
5. **Multi-Objective Policy Re-ranking:** Instantly re-ranks the book for *Max Cash*, *Max Cure Volume*, *Balanced Sustainability*, or *Vulnerable First*.

---

## 📂 Repository Structure
```
.
├── app/
│   └── app.py                     # Streamlit Haute-Elegance dashboard (8 interactive tabs)
├── data/
│   ├── raw/                       # Raw input CSVs (excluded from git via .gitignore)
│   └── processed/
│       └── weekly_400_accounts.csv # Production weekly call book with quarters, XAI & scripts
├── models/
│   ├── prioritiser_model.joblib   # Calibrated Gradient Boosting classifier
│   ├── time_to_cure_regressor.joblib # Survival hazard time-to-cure regressor
│   └── partial_recovery_regressor.joblib # Settlement ratio regressor
├── reports/
│   ├── TECHNICAL_REPORT.md        # Deliverable 3: 4-page formal technical report
│   ├── BUSINESS_CASE.md           # Deliverable 5: 1-page financial model for Bamenda MFIs
│   ├── PITCH_SLIDES.md            # Deliverable 4: 5-slide, 5-minute executive pitch deck
│   └── metrics_summary.json       # Exact numerical validation metrics
├── src/
│   ├── target.py                  # Stage A: Arrears isolation & 30-day cure window
│   ├── features.py                # Stage B: Pre-contact behavioral & seasonal features
│   ├── model.py                   # Stage C: Multi-task ML, XAI waterfall & AdaptablePrioritiser
│   ├── evaluate.py                # Stage C: Precision@K & Money Recovered evaluation
│   └── contact.py                 # Stage D: Channel economics, quarter clustering & bilingual scripts
├── tests/
│   ├── test_no_leakage.py         # Automated unit test preventing post-contact data leakage
│   └── test_models_and_clustering.py # Unit tests for AdaptablePrioritiser & route clustering
├── run_pipeline.py                # Master CLI execution pipeline script
├── requirements.txt               # Pinned Python package dependencies
├── .gitignore                     # Data and credentials exclusion
└── README.md                      # Deliverable 2: Stranger-ready replication guide
```

---

## 🇨🇲 Cameroon & Global Microfinance Innovations & Competitive Advantages

1. **COBAC Regulation R-2017/07 Capital Shield:** Early cure at Day 15 prevents loans crossing into 31+ DPD (*créances impayées*), preserving **+2,361,600 FCFA** in mandatory 20% statutory reserves per 150M FCFA portfolio (+8.9% capital preservation).
2. **MTN MoMo & Orange Money 1-Click USSD Dial & Direct Push API:** Direct USSD codes (`*126*9*705001*...#` and `*150*1*705001*...#`) plus automated **MoMo PIN Direct Push API** (`/requesttopay`) for instant 1-tap mobile settlement.
3. **Bilingual Voice AI & Pidgin IVR Call Agent:** Interactive voice call engine speaking natural **Cameroon Pidgin English** and Formal English with DTMF keypress actions and audio Promise-to-Pay (P2P) recording hooks.
4. **Njangi / Tontine Co-Guarantor Social Graph Resolution:** Maps informal *Njangi* group networks and church tontines, enabling cooperative peer resolution prior to default escalation.
5. **WhatsApp Business AI Assistant & Voice Note Engine:** Sends rich interactive payment cards and transcribes incoming borrower voice notes via Whisper-Pidgin AI.
6. **Daily "Small-Small" Micro-Repayment Restructuring:** Converts lump sums into daily micro-installments (e.g. 2,500 FCFA/day) matching Bamenda trader market cash velocity.
7. **Diaspora Sponsor & Family Guarantor Protocol:** 1-click outreach scripts addressing family sponsors in Douala, Yaoundé, and the Diaspora (France, UK, US) to clear balances remotely.
8. **Bamenda Security Risk Index & Safe Transit Router:** Real-time safety tiers (🟢 Safe Transit vs 🟡 Daytime Caution) protecting motorcycle field officers across Mezam division.

---

## 🛡️ Ethical Safeguards & The Human Cost
Borrowers in Bamenda frequently experience external systemic disruptions (regional economic headwinds, health emergencies, crop failures). 

The Prioritiser actively prevents aggressive debt enforcement through:
1. **Senior Hardship Shield:** Borrowers aged 60+ are diverted from collections to cooperative restructuring.
2. **Income Disruption Screen:** Unemployed or economically shocked borrowers receive grace period rescheduling.
3. **Field Visit Cost Gate:** Field visits (5,000 FCFA) are prohibited on low balances and vulnerable borrowers.
4. **Welfare Audit:** In the active 400-account book, **74 borrowers (18.5%)** are flagged as vulnerable.

---

## 💼 Business Case Summary
* **Target Buyers:** Ntarinkon Cooperative Credit Union (NtaCCUL), Azire Credit Union (AZICCUL), CamCCUL network.
* **Pricing:** 150,000 FCFA / month per branch.
* **Customer Value:** **+2,164,156 FCFA** additional net cash recovered per month (**14.4x ROI**).
* **Payback Horizon:** Just **2.1 days** of monthly collections.

---
*Prepared by Nahbila Faith for Skye8 Company Ltd Final Project Submission (October 2026).*
