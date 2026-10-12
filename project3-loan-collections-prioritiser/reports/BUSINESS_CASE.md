# Business Case: Loan Collections Prioritiser (RecoverIQ)
**Product:** RecoverIQ Collections Prioritiser (Local Microfinance Edition)  
**Target Market:** Category 1 & 2 Microfinance Institutions (MFIs) & Credit Unions in Bamenda, Cameroon  
**Author:** Nahbila Faith (SKY8-DS-FP-005)  
**Track:** Skye8 Data Science and ML / AI Internship Track  
**Date:** October 2026  

---

## 1. Executive Summary & Customer Identification

### Target Customers in Bamenda & Mezam Division
The primary target market consists of licensed Category 1 and Category 2 Microfinance Institutions (MFIs) and cooperative credit unions headquartered in Bamenda, North West Region, Cameroon:
1. **Ntarinkon Cooperative Credit Union Ltd (NtaCCUL):** ~15 branches across Bamenda (Commercial Avenue, Nkwen, Up Station) managing over 80,000 active members.
2. **Azire Cooperative Credit Union Ltd (AZICCUL):** Headquartered in Azire, Bamenda; one of Cameroon's largest and oldest cooperative credit unions.
3. **Mbingo Baptist Credit Union / CBC Health Services MFI:** Serving healthcare workers, teachers, and agricultural suppliers across Mezam.
4. **Community Credit Unions (CamCCUL network affiliates):** Over 18 affiliated union branches in the greater Bamenda metropolitan and peri-urban zone (Mankon, Bafut, Santa).

---

## 2. Customer Problem & Quantified Value Proposition

### The Problem
A standard branch holds ~400 delinquent loans ($\ge 15$ days overdue) representing roughly **4,920,000 FCFA** in overdue instalments. Three field collections officers work the arrears book sorted by descending debt size ("biggest debt first"). Because massive debts are predominantly insolvent (business collapse, displacement), officers achieve only a **7.0% precision** at top-100 accounts, recovering **3,301,388 FCFA** while burning significant motorbike petrol on fruitless visits.

### The Value Delivered (In Francs CFA)
Using RecoverIQ:
* **Precision at Top 100 Accounts:** Jumps from **7.0% to 88.0%** (12.57x more accounts successfully cured).
* **Cash Recovered (Top 100 Accounts):** Jumps from **3,301,388 FCFA to 5,465,544 FCFA**.
* **Net Cash Recovered Added per Month:** **+2,164,156 FCFA** in cash collections per branch per month (+65.6%).
* **Central Bank (COBAC) Capital Protected:** Prevents **30,000,000 FCFA** in mandatory statutory loan loss reserves (COBAC R-2017/07) from being frozen in non-interest-earning vault reserves.
* **Motorbike Fuel Saved:** Saves **16.0 Liters (~13,600 FCFA/week)** per officer team through neighborhood route clustering.

---

## 3. Product Pricing & Revenue Model (Realistic & Affordable)

To ensure rapid adoption without bureaucratic delays or multi-month board approval cycles, the pricing is calibrated as an **operational petty cash expense** that a local Branch Manager can approve immediately:

### Pricing Tiers
| Tier | Target Client | Monthly Subscription | Daily Equivalent | Setup & Training (One-Off) |
| :--- | :--- | :--- | :--- | :--- |
| **Community Agency** | Small rural branches (<150 arrears accounts, 1 officer) | **25,000 FCFA / mo** | ~830 FCFA / day | 40,000 FCFA |
| **Standard Branch (Recommended)** | Typical Bamenda branch (400 accounts, 3 officers) | **35,000 FCFA / mo** | ~1,160 FCFA / day | 60,000 FCFA |
| **Enterprise / League Package** | 5 to 10 branches under same union (e.g. NtaCCUL network) | **150,000 FCFA / mo** | ~5,000 FCFA / day | 150,000 FCFA |

### Why This Pricing is Completely Affordable for the Credit Union:
* **Costs Less Than Fuel:** At **35,000 FCFA / month**, the entire monthly software fee costs less than the petrol an officer burns on 3 motorbike trips.
* **Single Loan Payback:** If RecoverIQ helps the branch recover **just one single overdue loan of 35,000 FCFA**, the entire month's software cost is 100% recovered.
* **Massive Customer ROI:**
  $$\text{Monthly Customer Net Gain} = 2,164,156\text{ FCFA} - 35,000\text{ FCFA} = \mathbf{+2,129,156\text{ FCFA/month}}$$
  **Return on Investment (ROI): 61.8x** the subscription fee in direct recovered liquidity. Payback in **under 4 hours** of collections work.

---

## 4. Developer Cost Structure & Monthly Expenditure

Because RecoverIQ is built with lean Python architecture and local machine learning models (LightGBM/scikit-learn), **the developer incurs ZERO per-token AI API fees**. Inference runs directly on the local server in milliseconds.

### Actual Monthly Operating Costs (Paid by the Developer)
| Expense Item | Provider / Specification | Monthly Cost (USD) | Monthly Cost (FCFA) |
| :--- | :--- | :--- | :--- |
| **Cloud Application Server (VPS)** | Hetzner Cloud (CX22, 2 vCPU, 4GB RAM) or DigitalOcean Droplet | \$9.00 | 5,400 FCFA |
| **Database & Automated Backups** | Local PostgreSQL on server + Daily Encrypted Google Drive Backup | \$0.00 | 0 FCFA |
| **Domain Name (`.com` or `.cm`)** | Annual registration amortized monthly | \$1.00 | 600 FCFA |
| **SSL Certificate & DDoS Shield** | Cloudflare Free Tier (Universal SSL, Edge Caching, WAF) | \$0.00 | 0 FCFA |
| **Developer Internet & Testing** | MTN / Orange 4G Monthly Data Bundle for system monitoring | \$16.60 | 10,000 FCFA |
| **TOTAL DEVELOPER EXPENDITURE** | | **\$26.60** | **~16,000 FCFA / month** |

*(Note on Member SMS / Airtime: The branch pays for their own bulk SMS credits directly or uses their existing carrier corporate accounts; zero airtime cost comes out of the developer's pocket).*

---

## 5. Break-Even Analysis & Developer Profit Margins

### Break-Even Point
$$\text{Break-Even Customers} = \frac{\text{Developer Monthly Expenses (16,000 FCFA)}}{\text{Standard Subscription (35,000 FCFA)}} = \mathbf{0.46\text{ Customers}}$$

* **Just ONE single client branch** covers more than double the developer's entire monthly hosting expenditure (**218% cost coverage**).

### Scaled Developer Income Projections
| Client Adoption | Monthly Revenue | Developer Expenses | Net Monthly Developer Profit | Annual Net Profit |
| :--- | :--- | :--- | :--- | :--- |
| **1 Branch** (NtaCCUL Commercial Ave) | 35,000 FCFA | 16,000 FCFA | **+19,000 FCFA / mo** | 228,000 FCFA |
| **3 Branches** (2 NtaCCUL + 1 AZICCUL) | 105,000 FCFA | 16,000 FCFA | **+89,000 FCFA / mo** | 1,068,000 FCFA |
| **5 Branches** (NtaCCUL, AZICCUL, CBC) | 175,000 FCFA | 16,000 FCFA | **+159,000 FCFA / mo** | 1,908,000 FCFA |
| **10 Branches** (Divisional League Network)| 350,000 FCFA | 20,000 FCFA *(server ram bump)* | **+330,000 FCFA / mo** | **3,960,000 FCFA** |

* **Upfront Cash Injection:** In addition to monthly recurring subscriptions, onboarding 5 branches with a modest 60,000 FCFA setup fee yields an immediate **300,000 FCFA upfront cash injection** for initial training and data formatting.

---

## 6. Implementation & Commercialization Roadmap

1. **Week 1–2: Pilot Trial (Free 14-Day Proof of Concept):**
   * Partner with one friendly branch (e.g. NtaCCUL Commercial Avenue).
   * Ingest their Monday delinquent list of 100 accounts into RecoverIQ.
   * Let 1 officer work using the RecoverIQ ranked list while the other 2 officers use the old manual sheet.
   * Prove the difference in cash collected at the end of the 2 weeks.
2. **Week 3: Conversion to Paid Subscription:**
   * Present the pilot results to the Branch Manager. With an extra ~500,000 FCFA recovered during the trial, signing the **35,000 FCFA/month** subscription is frictionless.
3. **Month 2–3: Word-of-Mouth Expansion:**
   * Use branch success metrics to expand into AZICCUL Azire and CamCCUL community branches across Mezam Division.
