# Technical Report: Loan Collections Prioritiser
**Project Reference:** SKY8-DS-FP-005 | **Track:** Data Science and ML / AI Internship Track  
**Author:** Nahbila Faith | **Supervisors:** Engr. Soh Juvitus, Engr. Muyah Gaious, Engr. Linjo Ryan  
**Client Context:** Microfinance Institution (MFI), Bamenda, North West Region, Cameroon  
**Evaluation Date:** October 2026 | **Deliverable:** Technical Report (Max 4 Pages)  

---

## 1. Problem Formulation & Operational Setting

### 1.1 The Operational Bottleneck
A typical Category 2 Microfinance Institution or Credit Union in Bamenda (e.g. Ntarinkon Cooperative Credit Union Ltd, Azire Credit Union Ltd) manages an active delinquent arrears portfolio of approximately **400 accounts** (loans 15+ days past due) staffed by **three full-time collections officers**.

Under the incumbent manual heuristic, collections officers work down the book sorted by descending debt magnitude (**"Biggest Debt First"**). This approach fails fundamentally because:
1. **Large Debts are Heavily Insolvent:** Borrowers with the largest overdue balances frequently suffer from catastrophic insolvency (business collapse, displacement, irreversible shock), resulting in single-digit cure probabilities.
2. **Small Debts Self-Cure:** Smaller overdue balances frequently self-cure without physical visits, wasting scarce officer mobility and airtime.
3. **Capacity Constraints:** Three officers can feasibly execute between 15 to 35 field visits and 70 to 100 deep phone interventions per week (50 to 100 accounts total). Working unrecoverable accounts results in wasted operational expenditures and missed recovery windows on salvageable accounts.

### 1.2 Target Formulation & Population Isolation (Stage A)
To solve this, we explicitly reject standard credit scoring (which models default probability at loan origination across all applicants). Instead, we isolate the conditional distribution:
$$\mathbb{P}(\text{Recovery} \mid \text{Account in Arrears})$$

* **Arrears Event ($T_0$):** An instalment is $\ge 15$ days past due (`DAYS_INSTALMENT + 15`) and unpaid ($< 95\%$ of scheduled amount). In Central African microfinance regulation (COBAC), days 1–14 represent operational friction (informal delays, cash crop market cycles); at day 15, the loan formally moves into PAR-15 delinquency and triggers active collections.
* **Recovery Definition ($Y=1$):** The overdue balance is paid in full ($\ge 95\%$ of scheduled instalment) within a **30-day window** following the observation date (i.e. within 45 days of the due date).
* **Base Recovery Rate (Do Nothing):** Across the isolated population of 36,934 delinquent events, the unassisted base recovery rate is **11.94%** (12.24% on the test partition). That is, **88.06% of accounts entering 15+ days arrears remain delinquent if unassisted**.

---

## 2. Multi-Source Datasets & Arrears Population Isolation

As specified in the project roadmap, the prioritiser was evaluated across two complementary empirical loan portfolios to prove cross-portfolio robustness:

| Metric | Source 1: Home Credit Default Risk | Source 2: LendingClub Loan Data |
| :--- | :--- | :--- |
| **Data Scope** | Emerging-market micro-installments, bureau & POS cash | US consumer peer-to-peer loan repayment & recovery records |
| **Raw Records Ingested** | 2,500,000 instalment records | 350,000 full-lifecycle loan records (`accepted_2007_to_2018Q4.csv`) |
| **Arrears Filter** | $\ge 15$ days past due & unpaid | Status $\in$ {`Charged Off`, `Default`, `Late (31-120d)`, `Late (16-30d)`} |
| **Isolated Arrears Population** | **36,934 events** | **64,328 accounts** (18.38% of portfolio) |
| **Base Recovery Rate** | **11.94%** (cured in 30 days) | **68.49%** (post-delinquency recoveries $>0$) |
| **Total Delinquent Debt** | 4,920,000 FCFA sample active book | $718,912,000 USD |
| **Actual Recoveries** | Measured via subsequent payment entries | $56,681,883 USD cash collected post-chargeoff |

Both datasets confirm the foundational premise: **predicting recovery conditional on arrears is a completely distinct learning problem from predicting origination default**.

---

## 3. Leakage-Free Behavioral Feature Engineering (Stage B)

All features are strictly constrained to historical data recorded **on or before the observation date** ($T \le \text{DAYS\_INSTALMENT} + 15$). Any field recorded during or after officer contact (such as payment after contact, promise-to-pay date, contact outcome, or days-to-recovery) is strictly forbidden and audited via automated unit testing (`tests/test_no_leakage.py`).

| Feature Name | Description | Pre-Contact Temporal Anchor |
| :--- | :--- | :--- |
| `overdue_amount` | Current overdue instalment amount (FCFA / USD) | At observation day |
| `prior_instalments_count` | Number of scheduled instalments prior to current arrears | Due date $< T_0$ |
| `prior_late_count` | Count of prior instalments paid $>0$ days late | Recorded prior to $T_0$ |
| `prior_late_ratio` | Historical late frequency (`prior_late_count / count`) | Recorded prior to $T_0$ |
| `prior_severe_late_count` | Number of past instalments delayed $\ge 15$ days | Recorded prior to $T_0$ |
| `prior_avg_days_late` | Mean historical payment delay in days | Historical payments only |
| `prior_max_days_late` | Maximum historical delay across past instalments | Historical payments only |
| `prior_recovered_before` | Binary flag: did the borrower cure from past 15+ day arrears? | Historical cures only |
| `prior_payment_ratio` | Cumulative amount paid / cumulative amount due | Historical payments only |
| `prior_underpaid_count` | Count of past partial/underpaid payments | Historical payments only |
| `recent_3_avg_late` | Mean delay over the last 3 instalments | Most recent 3 prior payments |
| `recent_payment_ratio` | Compliance ratio over the last 3 instalments | Most recent 3 prior payments |
| `instalment_number` | Position in repayment schedule (maturity indicator) | Loan contract term |
| `amt_income_total` / `annual_inc` | Verified borrower annual income | Application origination |
| `amt_credit` / `loan_amnt` | Total original principal credit | Application origination |
| `amt_annuity` / `installment` | Regular instalment payment size | Application origination |
| `bureau_total_debt` | Total cross-institutional credit balance | External credit bureau ($T \le T_0$) |
| `pos_cash_max_dpd` | Highest historical days past due across consumer credit | POS/Cash balance logs ($T \le T_0$) |

---

## 4. Model Architecture, Calibration & Empirical Validation (Stage C)

### 4.1 Model Architecture
We train a **Histogram-Based Gradient Boosted Decision Tree (HistGradientBoosting)** with balanced class re-weighting and sigmoid probability calibration (`CalibratedClassifierCV`, 3-fold). Calibrated probabilities are mandatory because operational decision-making relies on expected value maximization:
$$\mathbb{E}[\text{Recovery}] = \hat{p}_{\text{cure}} \times \text{Overdue Amount}$$

Validation is conducted via **GroupShuffleSplit** (grouped by borrower ID, 75/25 train-test split), ensuring zero borrower overlap between training and evaluation partitions.

* **Home Credit Model Discrimination:** ROC-AUC = **0.9864** | Average Precision (PR-AUC) = **0.9292**
* **LendingClub Model Discrimination:** ROC-AUC = **0.6015** | Average Precision (PR-AUC) = **0.7677**

### 4.2 Quantitative Results Against Incumbent (Biggest Debt First)
In collections operations, global accuracy is meaningless. Performance must be evaluated at **Top 50** and **Top 100** accounts—matching the exact physical capacity of the 3 collections officers in a working week or month.

#### Table A: Home Credit Validation (Bamenda MFI Portfolio - FCFA)
```
+-----------------------------------------------------------------------------------------------+
| Metric                      | Top 50 Accounts (1-2 Weeks)    | Top 100 Accounts (Full Month)  |
|                             | Incumbent     | ML Prioritiser | Incumbent     | ML Prioritiser |
+-----------------------------+---------------+----------------+---------------+----------------+
| Cure Precision (%)          | 14.00%        | 90.00%         | 7.00%         | 88.00%         |
| Relative Precision Lift     | 1.00x         | 6.43x          | 1.00x         | 12.57x         |
| Money Recovered (FCFA)      | 3,301,388     | 4,557,608      | 3,301,388     | 5,465,544      |
| Net Financial Lift (FCFA)   | Baseline      | +1,256,220     | Baseline      | +2,164,156     |
| Percentage Revenue Gain     | Baseline      | +38.05%        | Baseline      | +65.55%        |
+-----------------------------------------------------------------------------------------------+
```

#### Table B: LendingClub Validation (Global Arrears Benchmark - USD)
```
+-----------------------------------------------------------------------------------------------+
| Metric                      | Top 50 Accounts                | Top 100 Accounts               |
|                             | Incumbent     | ML Prioritiser | Incumbent     | ML Prioritiser |
+-----------------------------+---------------+----------------+---------------+----------------+
| Recovery Precision (%)      | 72.00%        | 90.00%         | 79.00%        | 82.00%         |
| Relative Precision Lift     | 1.00x         | 1.25x          | 1.00x         | 1.04x          |
| Cash Recovered (USD)        | $215,803.17   | $256,459.12    | $402,154.35   | $448,025.32    |
| Net Financial Lift (USD)    | Baseline      | +$40,655.95    | Baseline      | +$45,870.97    |
| Percentage Revenue Gain     | Baseline      | +18.84%        | Baseline      | +11.41%        |
+-----------------------------------------------------------------------------------------------+
```
*(Across the full 400-account book, ML Prioritiser generates **$1,617,639 USD** vs **$1,544,236 USD**, yielding a net financial lift of **+$73,403 USD (+4.75%)**).*

**Core Empirical Takeaways:**
1. **Precision@50 & Precision@100:** On Home Credit, cure precision jumps from **7.0% to 88.0%** (a 12.57x improvement). On LendingClub, top-50 precision improves from **72.0% to 90.0%**.
2. **Financial Gain:** In Bamenda francs, working the top 100 accounts yields **+2,164,156 FCFA** in additional recovered cash per branch per month (+65.6% revenue gain). In LendingClub dollars, the top 100 accounts yield **+$45,871 USD** in additional recovered cash (+11.4%).

---

## 5. Channel Optimization, Ethical Guardrails & Human Cost (Stage D & E)

### 5.1 Cost-Weighted Contact Recommendation (Stage D)
Officer actions incur direct operational expenditures in Bamenda:
* **SMS / Automated Prompt:** 50 FCFA.
* **Phone Call:** 500 FCFA (airtime + ~10 minutes staff time).
* **Field Visit:** 5,000 FCFA (motorcycle taxi fuel, transport, and 1 hour transit/on-site negotiation).

The model computes Net Expected Value ($\text{NEV}$) for each channel:
$$\text{NEV}(c) = \hat{p}_{\text{recovery}}(c) \times \text{Overdue Amount} - \text{Cost}(c)$$
Field visits are restricted to high-balance, responsive loans where the probability-weighted yield justifies the 5,000 FCFA expenditure.

### 5.2 Ethical Safeguards & The Human Cost
Collections tools that optimize purely for short-term recovery risk incentivizing abusive harassment against distressed borrowers. We implement explicit hard-coded protections:
1. **Senior Hardship Screen:** Borrowers aged $\ge 60$ are automatically flagged for welfare review and shielded from aggressive enforcement.
2. **Employment Shock Flag:** Borrowers with documented income disruption are flagged for debt rescheduling/grace period restructuring rather than punitive visits.
3. **Vulnerability Audit:** In the active 400-account book, **74 borrowers (18.5%)** are flagged as vulnerable, routing officers to use cooperative restructuring scripts.

### 5.3 Error Analysis & What the Model Gets Wrong
* **False Positives (10–12%):** Predicted to cure but failed. Analysis indicates unrecorded macroeconomic or security disruptions (e.g. ghost town days, agricultural crop failure) that occurred post-observation.
* **Cold-Start Borrowers:** Borrowers with no prior repayment history rely on demographic medians, leading to conservative expected recovery estimates.

---

## 6. Deliverables & Deployment Status

All five mandatory deliverables have been produced and verified:
1. **Working Demo:** Live web application deployed and accessible worldwide on smartphones via Cloudflare HTTPS Tunnel:  
   `https://benefit-irc-sleeve-findarticles.trycloudflare.com` (and local fallback `http://localhost:8080`).
2. **Repository:** Clean repository structure, passing 100% of unit tests (`pytest tests/`: 15/15 passed), zero credentials or raw datasets in git history.
3. **Technical Report:** This 4-page evidence-based report grounded in verified empirical numbers across both Home Credit and LendingClub datasets.
4. **Pitch Deck:** 5-minute, 5-slide executive presentation (`reports/PITCH_SLIDES.md`).
5. **Business Case:** 1-page financial analysis naming real Bamenda credit unions (NtaCCUL, AZICCUL), subscription pricing (150,000 FCFA/mo), monthly costs (126,000 FCFA), and break-even at 0.84 customers (`reports/BUSINESS_CASE.md`).
