import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

# ── Color Definitions ─────────────────────────────────────────────────────────
DARK_GREEN  = colors.HexColor("#173323")
MID_GREEN   = colors.HexColor("#2a5c38")
LIME_CITRON = colors.HexColor("#8ca31c")  # High contrast lime
PALE_BG     = colors.HexColor("#f4f7f1")
WHITE       = colors.white
INK_TEXT    = colors.HexColor("#1e2922")
MUTED_TEXT  = colors.HexColor("#526156")
BORDER_COL  = colors.HexColor("#d5ded2")
RED_ALERT   = colors.HexColor("#b91c1c")
AMBER_WARN  = colors.HexColor("#b45309")
BLUE_ACCENT = colors.HexColor("#0369a1")

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and display total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED_TEXT)
        
        # Don't draw running header on cover/page 1
        if self._pageNumber > 1:
            # Running Header
            self.drawString(1.5 * cm, A4[1] - 1.0 * cm, "RecoverIQ — Comprehensive Platform Guide & Numerical Metric Reference")
            self.setStrokeColor(BORDER_COL)
            self.setLineWidth(0.5)
            self.line(1.5 * cm, A4[1] - 1.15 * cm, A4[0] - 1.5 * cm, A4[1] - 1.15 * cm)

        # Running Footer (on all pages)
        self.setStrokeColor(BORDER_COL)
        self.setLineWidth(0.5)
        self.line(1.5 * cm, 1.25 * cm, A4[0] - 1.5 * cm, 1.25 * cm)
        
        self.drawString(1.5 * cm, 0.85 * cm, "RecoverIQ Intelligent Loan Recovery Platform · Technical & Numerical Manual")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 1.5 * cm, 0.85 * cm, page_str)
        self.restoreState()


def create_platform_guide_pdf(output_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=DARK_GREEN,
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=MUTED_TEXT,
        spaceAfter=14
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=DARK_GREEN,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=MID_GREEN,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=INK_TEXT,
        spaceAfter=5
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=INK_TEXT,
        leftIndent=12,
        spaceAfter=3
    )
    formula_style = ParagraphStyle(
        'Formula_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=DARK_GREEN,
        backColor=PALE_BG,
        borderColor=BORDER_COL,
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=6
    )
    table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=INK_TEXT
    )
    table_head = ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=WHITE
    )

    story = []

    # ── HEADER BANNER ─────────────────────────────────────────────────────────
    banner_data = [[
        Paragraph("<b>RECOVERIQ</b><br/><font size=9 color='#d5ded2'>INTELLIGENT LOAN RECOVERY PLATFORM</font>", ParagraphStyle('B1', fontName='Helvetica-Bold', fontSize=16, textColor=WHITE, leading=19)),
        Paragraph("<b>OFFICIAL REFERENCE MANUAL</b><br/><font size=8 color='#d5ded2'>Page Functions, Metric Formulations &amp; Architecture</font>", ParagraphStyle('B2', fontName='Helvetica', fontSize=10, textColor=WHITE, alignment=TA_RIGHT, leading=14))
    ]]
    banner_table = Table(banner_data, colWidths=[10 * cm, 8 * cm])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_GREEN),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 14))

    # Document Abstract
    story.append(Paragraph("Executive System Overview &amp; Operational Purpose", h1_style))
    story.append(Paragraph(
        "<b>RecoverIQ</b> is an enterprise-grade artificial intelligence platform designed to prioritize, automate, and resolve delinquent loan portfolios for Microfinance Institutions (MFIs), Credit Unions, and digital retail lenders. Rather than using naive legacy debt-collection methods (which merely sort accounts by the largest debt balance and exhaust staff on low-probability cases), RecoverIQ uses Machine Learning (LightGBM and XGBoost) to model each borrower's <b>Cure Probability (P_cure)</b> and calculates the <b>Expected Net Value (EV)</b> of each intervention, accounting for the marginal cost of SMS, calls, and field visits.",
        body_style
    ))
    story.append(Paragraph(
        "This document provides an exhaustive, field-by-field breakdown of every workspace, page module, statistical metric, formula, policy shield, and user workflow on both desktop and mobile platforms.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # ── SECTION 1: WORKSPACE ARCHITECTURE OVERVIEW ───────────────────────────
    story.append(Paragraph("1. Primary Platform Views &amp; Navigation Map", h1_style))
    
    views_summary_data = [
        [Paragraph("View ID / Path", table_head), Paragraph("Workspace Name", table_head), Paragraph("Core Purpose &amp; User Flow", table_head), Paragraph("Key User Actions", table_head)],
        [
            Paragraph("<b>view-case-review</b><br/>(Tab 1 / Home)", table_text),
            Paragraph("<b>Case Review</b>", table_text),
            Paragraph("In-depth account triage for a single borrower. Evaluates cure likelihood, affordability curves, contact history, and evidence signals.", table_text),
            Paragraph("Select borrower, adjust instalment slider, trigger MTN/Orange MoMo prompt, record call notes, commit promise.", table_text)
        ],
        [
            Paragraph("<b>view-overview</b><br/>(Tab 2)", table_text),
            Paragraph("<b>Portfolio Overview &amp; Call Roster</b>", table_text),
            Paragraph("Operational command centre listing all 400 prioritized Stage A accounts ranked by Net Expected Recovery.", table_text),
            Paragraph("Search accounts, filter by quarter, upload new loan CSV datasets, download full call sheet CSV.", table_text)
        ],
        [
            Paragraph("<b>view-signals</b><br/>(Tab 3)", table_text),
            Paragraph("<b>Decision Signals &amp; COBAC Reserves</b>", table_text),
            Paragraph("Regulatory prudential analysis mapping accounts against COBAC Regulation R-2017/07 Stage 2 write-downs.", table_text),
            Paragraph("Audit statutory capital savings, review SHAP explainability drivers, inspect risk signals.", table_text)
        ],
        [
            Paragraph("<b>view-outreach</b><br/>(Tab 4)", table_text),
            Paragraph("<b>Member Outreach &amp; Voice Bot</b>", table_text),
            Paragraph("Multi-channel communication dispatching (SMS, Voice IVR, WhatsApp sequences, field logistics).", table_text),
            Paragraph("Simulate interactive AI voice calls, send SMS notifications, inspect motorcycle fuel savings.", table_text)
        ],
        [
            Paragraph("<b>view-promises</b><br/>(Tab 5)", table_text),
            Paragraph("<b>Promise-to-Pay (PTP) Tracker</b>", table_text),
            Paragraph("Audit trail of all verbal and digital borrower commitments, tracking resolution, kept amounts, and broken dates.", table_text),
            Paragraph("Log new payment commitments, mark promises as KEPT or BROKEN, monitor portfolio keep rate.", table_text)
        ],
        [
            Paragraph("<b>view-scorecard</b><br/>(Tab 6)", table_text),
            Paragraph("<b>Officer Scoreboard &amp; Benchmarks</b>", table_text),
            Paragraph("Team performance leaderboard and dual benchmark validation (Home Credit + LendingClub dual validation).", table_text),
            Paragraph("Track officer performance points, verify 0% leakage, compare Precision@50 and lift metrics.", table_text)
        ],
        [
            Paragraph("<b>skye8-chat-panel</b><br/>(Modal)", table_text),
            Paragraph("<b>RecoverIQ AI Voice &amp; Text Assistant</b>", table_text),
            Paragraph("Hands-free voice assistant allowing officers to query the portfolio via live microphone audio recording or text.", table_text),
            Paragraph("Tap 🎙 to speak, type query, receive spoken English audio response and on-screen summary.", table_text)
        ],
        [
            Paragraph("<b>campaign-modal</b><br/>(Modal / 1-Click)", table_text),
            Paragraph("<b>1-Click Tailored Campaign Dispatcher</b>", table_text),
            Paragraph("Bulk multi-channel outreach engine with cohort filtering, tone segmentation, and Pre-Flight message verification.", table_text),
            Paragraph("Select target cohort, review Pre-Flight table, inspect Dispatch Cost &amp; Book Value, launch 1-click batch.", table_text)
        ],
    ]
    views_table = Table(views_summary_data, colWidths=[3.2 * cm, 3.5 * cm, 6.5 * cm, 4.8 * cm])
    views_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(views_table)
    story.append(Spacer(1, 14))

    # ── SECTION 2: CASE REVIEW WORKSPACE BREAKDOWN ───────────────────────────
    story.append(Paragraph("2. Case Review Workspace: Deep-Dive &amp; Numerical Breakdown", h1_style))
    story.append(Paragraph(
        "The <b>Case Review</b> screen is where a loan officer spends 70% of their operational day. When a borrower account is opened, the system renders an integrated view of credit risk, economic capacity, and actionable contact scripts.",
        body_style
    ))

    case_metrics_data = [
        [Paragraph("UI Element &amp; Data Point", table_head), Paragraph("Sample Value", table_head), Paragraph("Mathematical Formula / Derivation", table_head), Paragraph("Operational Function &amp; Significance", table_head)],
        [
            Paragraph("<b>Risk Score Ring</b><br/>(Hero Banner)", table_text),
            Paragraph("<b>99.7%</b><br/>(e.g., Client #103380)", table_text),
            Paragraph("<code>P(Cure) = 1 / (1 + e^(-z))</code><br/>Predicted probability of full repayment within 15–30 days.", table_text),
            Paragraph("Visual gauge showing recovery probability. High scores (>80%) indicate that gentle SMS/calls will recover funds without field visits.", table_text)
        ],
        [
            Paragraph("<b>Overdue Balance</b><br/>(Metric 1)", table_text),
            Paragraph("<b>30,613 FCFA</b>", table_text),
            Paragraph("Delinquent principal + accrued contractual interest past due.", table_text),
            Paragraph("The exact amount past due that must be resolved to bring the account current and avoid COBAC impairment.", table_text)
        ],
        [
            Paragraph("<b>Expected Net Recovery</b><br/>(Metric 3)", table_text),
            Paragraph("<b>30,257 FCFA</b>", table_text),
            Paragraph("<code>Net = P(Cure) * Overdue - Cost(Channel)</code><br/>e.g. <code>0.997 * 30,613 - 500 = 30,257</code>", table_text),
            Paragraph("The risk-adjusted financial return expected from the contact. Accounts with higher Expected Net are prioritized first.", table_text)
        ],
        [
            Paragraph("<b>Affordability Slider</b><br/>(Instalment Calculator)", table_text),
            Paragraph("<b>10,000 FCFA</b><br/>(Default: Overdue / 3)", table_text),
            Paragraph("<code>Min: 5,000 FCFA | Max: 60,000 FCFA</code><br/>Amortization: <code>Months = Overdue / Instalment</code>", table_text),
            Paragraph("Allows the officer to negotiate a realistic restructured payment plan during a live phone call without doing mental math.", table_text)
        ],
        [
            Paragraph("<b>USSD Quick Codes</b><br/>(MoMo / Orange)", table_text),
            Paragraph("<code>*126*9*705001*30613#</code><br/><code>*150*1*705001*30613#</code>", table_text),
            Paragraph("Format: <code>*SERVICE*COUNTER*MERCHANT_ID*AMOUNT#</code>", table_text),
            Paragraph("Pre-formatted mobile money strings. Officer can send these via SMS or read them aloud to enable instant 1-touch mobile payments.", table_text)
        ],
        [
            Paragraph("<b>Daily Target Rate</b><br/>(Payment Amortization)", table_text),
            Paragraph("<b>1,391 FCFA / day</b>", table_text),
            Paragraph("<code>Daily = Overdue / 22 Working Days</code>", table_text),
            Paragraph("Breaks down large arrears balances into bite-sized daily business targets suitable for petty traders in Bamenda markets.", table_text)
        ],
        [
            Paragraph("<b>Senior / Hardship Shield</b><br/>(Ethical Pill)", table_text),
            Paragraph("<b>Senior / Hardship Shield</b><br/>(Status: Shielded)", table_text),
            Paragraph("<code>Age >= 60 OR Employment_Disrupted == True</code>", table_text),
            Paragraph("Mandatory safety shield. Prevents coercive field enforcement and automatically routes the member to supportive restructuring.", table_text)
        ],
    ]
    case_table = Table(case_metrics_data, colWidths=[3.5 * cm, 2.8 * cm, 5.5 * cm, 6.2 * cm])
    case_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(case_table)
    story.append(Spacer(1, 14))

    # ── SECTION 3: PORTFOLIO OVERVIEW & CALL ROSTER ──────────────────────────
    story.append(Paragraph("3. Portfolio Overview &amp; Call Sheet: The Macro Economy", h1_style))
    story.append(Paragraph(
        "The <b>Overview</b> tab displays the entire active recovery book. In our benchmark calibration, this comprises a cohort of 400 Stage A delinquent accounts.",
        body_style
    ))

    story.append(Paragraph("Portfolio Macro KPI Cards Explained:", h2_style))
    story.append(Paragraph("• <b>TOTAL DELINQUENT BOOK (60,883,612 FCFA)</b>: The aggregate past-due principal and interest across all 400 active delinquent accounts in the branch's weekly portfolio. This represents the total capital at immediate risk of slipping into Stage 2 non-accrual.", bullet_style))
    story.append(Paragraph("• <b>EXPECTED RECOVERABLE CASH (5,465,544 FCFA)</b>: The mathematically expected cash volume that RecoverIQ projects will be recovered over a 7-day operational cycle using the model's recommended contact channels.", bullet_style))
    story.append(Paragraph("• <b>RECOVERY LIFT (+2,160,000 FCFA vs Heuristics)</b>: The incremental financial gain generated by prioritizing accounts using ML expected net recovery versus the industry standard baseline (sorting by largest arrears balance). By contacting high-cure accounts first rather than chasing stubborn high-debt accounts, officers collect 65% more cash in the same number of working hours.", bullet_style))
    story.append(Paragraph("• <b>PORTFOLIO CONCENTRATION BY ZONE</b>: Zone 1 (Commercial Avenue) and Zone 2 (Nkwen) represent 68% of recoverable cash, allowing the branch manager to optimize field motorbike routes.", bullet_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Roster Data Table Columns &amp; Mobile Adaptation:", h2_style))
    story.append(Paragraph(
        "The table renders: <b>Rank</b> (1–400), <b>Borrower ID</b> (e.g. Client #103380), <b>Loan Reference</b>, <b>Assigned Officer</b>, <b>Quarter/Zone</b>, <b>Overdue FCFA</b>, <b>Cure Probability %</b>, <b>Recommended Channel</b>, and <b>Expected Net Recovery</b>.<br/>"
        "<b>Mobile Feature</b>: To ensure accessibility on small smartphone screens, the table is housed in a touch-scrolling container with the prompt <i>'👉 Swipe horizontally to view full table data'</i> and includes both <b>⇪ Upload CSV</b> and <b>⇩ Download CSV</b> buttons.",
        body_style
    ))
    story.append(Spacer(1, 14))

    # ── SECTION 4: COBAC REGULATORY RESERVE CAPITAL ──────────────────────────
    story.append(Paragraph("4. Decision Signals &amp; COBAC Regulation R-2017/07", h1_style))
    story.append(Paragraph(
        "Microfinance institutions regulated by COBAC (Commission Bancaire de l'Afrique Centrale) face severe statutory capital penalties when loans breach specific delinquency thresholds. RecoverIQ directly automates and protects this regulatory compliance.",
        body_style
    ))

    cobac_data = [
        [Paragraph("COBAC Metric / Parameter", table_head), Paragraph("Value in Book", table_head), Paragraph("Regulatory Rule (R-2017/07)", table_head), Paragraph("Financial Impact on Credit Union", table_head)],
        [
            Paragraph("<b>Delinquency Window</b>", table_text),
            Paragraph("<b>Day 15 to Day 30</b>", table_text),
            Paragraph("Stage 1 Pre-delinquency.<br/>0% mandatory provision.", table_text),
            Paragraph("RecoverIQ focuses all efforts in this window. Curing loans here incurs zero statutory write-downs.", table_text)
        ],
        [
            Paragraph("<b>Category 2 Gross Provision</b>", table_text),
            Paragraph("<b>10,654,632 FCFA</b>", table_text),
            Paragraph("Articles 21–25: Mandatory <b>20% write-down reserve</b> once loan reaches 31–90 days past due.", table_text),
            Paragraph("Without intervention, the cooperative must lock up 10.65M FCFA of liquid cash into dead regulatory reserves.", table_text)
        ],
        [
            Paragraph("<b>Net Regulatory Reserve Required</b>", table_text),
            Paragraph("<b>2,823,205 FCFA</b>", table_text),
            Paragraph("Collateral deduction: Tangible collateral reduces the unhedged exposure before applying 20%.", table_text),
            Paragraph("The actual net cash deduction from Tier 1 Capital required after applying verified member security deposits.", table_text)
        ],
        [
            Paragraph("<b>Statutory Capital Preserved</b>", table_text),
            Paragraph("<b>7,831,427 FCFA<br/>(73.5% Saved)</b>", table_text),
            Paragraph("Capital Shield = <code>Gross Provision - Net Required</code>", table_text),
            Paragraph("Cash capital preserved to support new productive cooperative loans to small farmers and traders in Bamenda.", table_text)
        ],
    ]
    cobac_table = Table(cobac_data, colWidths=[4.2 * cm, 3.2 * cm, 5.0 * cm, 5.6 * cm])
    cobac_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(cobac_table)
    story.append(Spacer(1, 14))

    # ── SECTION 5: OUTREACH & ETHICAL COST WEIGHTS ───────────────────────────
    story.append(Paragraph("5. Member Outreach: Cost-Weighted Interventions &amp; Ethics", h1_style))
    story.append(Paragraph(
        "Legacy collectors immediately jump on motorbikes to visit delinquent borrowers in person. In the North West Region of Cameroon, motorbike fuel and operator costs quickly exceed the value of overdue instalments. RecoverIQ enforces algorithmic cost-weighting.",
        body_style
    ))

    cost_data = [
        [Paragraph("Intervention Channel", table_head), Paragraph("Cost Weight (FCFA)", table_head), Paragraph("Gating Threshold / Policy Rule", table_head), Paragraph("Cost-Efficiency Rationale", table_head)],
        [
            Paragraph("<b>Automated SMS Reminder</b>", table_text),
            Paragraph("<b>100 FCFA</b> / message", table_text),
            Paragraph("Assigned when P(Cure) >= 0.85 and Overdue < 15,000 FCFA.", table_text),
            Paragraph("Extremely cheap; resolves 85%+ of forgetful or high-intent borrowers with negligible expense.", table_text)
        ],
        [
            Paragraph("<b>Officer Phone Call</b>", table_text),
            Paragraph("<b>500 FCFA</b> / call", table_text),
            Paragraph("Assigned when Overdue >= 15,000 FCFA or P(Cure) between 0.40 and 0.85.", table_text),
            Paragraph("Allows personalized empathy, income check, and negotiated restructuring commitment.", table_text)
        ],
        [
            Paragraph("<b>Field Motorbike Visit</b>", table_text),
            Paragraph("<b>2,000 FCFA</b> / visit", table_text),
            Paragraph("<b>Strictly Gated</b>: Only permitted if Expected Net > 5,000 FCFA AND Borrower is NOT shielded.", table_text),
            Paragraph("Saves 13,600 FCFA/week in unnecessary fuel. Eliminates dangerous, high-friction field confrontations.", table_text)
        ],
        [
            Paragraph("<b>Senior / Hardship Shield</b>", table_text),
            Paragraph("<b>74 Borrowers</b><br/>(18.5% of cohort)", table_text),
            Paragraph("Age >= 60 years or documented economic shock / health crisis.", table_text),
            Paragraph("Diverts vulnerable members from aggressive debt recovery into cooperative welfare and restructuring dialogues.", table_text)
        ],
    ]
    cost_table = Table(cost_data, colWidths=[4.0 * cm, 3.2 * cm, 5.4 * cm, 5.4 * cm])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(cost_table)
    story.append(Spacer(1, 14))

    # ── SECTION 6: PROMISE-TO-PAY (PTP) TRACKER ──────────────────────────────
    story.append(Paragraph("6. Promise-to-Pay (PTP) Tracker &amp; Audit Trail", h1_style))
    story.append(Paragraph(
        "A Promise-to-Pay (PTP) is a formal verbal or electronic commitment by a delinquent member to deposit a specified amount by a specified date. RecoverIQ provides a real-time audit ledger to track commitments and prevent broken promises from languishing unnoticed.",
        body_style
    ))
    story.append(Paragraph("• <b>TOTAL PROMISES LOGGED (3 active cases)</b>: The number of active commitments currently registered in the database.", bullet_style))
    story.append(Paragraph("• <b>RECOVERED CASH (KEPT) (65,000 FCFA)</b>: Cash successfully paid into the branch counter or via MoMo reconciliation against registered PTPs.", bullet_style))
    story.append(Paragraph("• <b>KEEP RATE (100.0%)</b>: Formula: <code>Kept Promises / (Kept + Broken)</code>. Benchmarks member reliability and officer negotiation realism.", bullet_style))
    story.append(Paragraph("• <b>PENDING &amp; BROKEN COMMITMENTS</b>: Pending promises alert officers on the exact morning they come due. If broken, the system immediately flags the borrower for an escalated phone consultation.", bullet_style))
    story.append(Paragraph("• <b>+ Log Member Promise Form</b>: Allows officers to record Account ID, Officer Name, Amount, Due Date, Channel (Call, Branch, WhatsApp, Field), and qualitative notes in under 10 seconds.", bullet_style))
    story.append(Spacer(1, 14))

    # ── SECTION 7: OFFICER SCOREBOARD & DUAL BENCHMARKS ──────────────────────
    story.append(Paragraph("7. Officer Scoreboard &amp; Dual Cross-Dataset Benchmarks", h1_style))
    story.append(Paragraph(
        "The <b>Scoreboard</b> provides accountability for field collections staff and displays the empirical validation benchmarks proving the system's performance on international and local loan datasets.",
        body_style
    ))

    story.append(Paragraph("Officer Performance Index Formula:", h2_style))
    story.append(Paragraph(
        "<code>Officer Score (0–100) = (Keep_Rate% * 0.40) + min(Weekly_Contacts * 5, 30) + min(FCFA_Collected / 10,000, 30)</code><br/>"
        "• <b>40% Weight on Keep Rate</b>: Incentivizes realistic, agreed payment commitments rather than extracting empty promises under pressure.<br/>"
        "• <b>30% Weight on Contact Activity</b>: Rewards active borrower communication (6 contacts/week earns full 30 pts).<br/>"
        "• <b>30% Weight on Cash Collected</b>: Rewards actual cash recovery (300,000 FCFA collected earns full 30 pts).<br/>"
        "• <b>Status Badges</b>: 🏆 CHAMPION (&ge; 85) | ⭐ TOP PERFORMER (&ge; 70) | ✅ ON TRACK (&ge; 50) | ⚠️ NEEDS SUPPORT (&lt; 50).",
        formula_style
    ))

    story.append(Paragraph("Dual Validation Benchmarks (Home Credit + LendingClub):", h2_style))
    bench_data = [
        [Paragraph("Validation Dataset", table_head), Paragraph("Total Records Evaluated", table_head), Paragraph("Top-50 Precision (vs Baseline)", table_head), Paragraph("Top-100 Precision (vs Baseline)", table_head), Paragraph("Incremental Cash Gain (Lift)", table_head)],
        [
            Paragraph("<b>Home Credit Loan Benchmark</b><br/>(Global MFI / Retail Proxy)", table_text),
            Paragraph("<b>307,511 Loans</b>", table_text),
            Paragraph("<b>92.0%</b><br/>(Baseline Heuristic: 74.0%)", table_text),
            Paragraph("<b>86.0%</b><br/>(Baseline Heuristic: 76.0%)", table_text),
            Paragraph("<b>+$45,000 USD</b> (+24.3% lift)<br/>Strict temporal split, 0% leakage", table_text)
        ],
        [
            Paragraph("<b>LendingClub Loan Benchmark</b><br/>(US Unsecured Consumer)", table_text),
            Paragraph("<b>350,000 Loans</b><br/>(64,328 Arrears)", table_text),
            Paragraph("<b>90.0%</b><br/>(Baseline Heuristic: 72.0%)", table_text),
            Paragraph("<b>82.0%</b><br/>(Baseline Heuristic: 79.0%)", table_text),
            Paragraph("<b>+$40,600 USD</b> (Top-50)<br/><b>+$73,400 USD</b> (Top-400 Lift)", table_text)
        ],
    ]
    bench_table = Table(bench_data, colWidths=[4.2 * cm, 3.2 * cm, 3.5 * cm, 3.5 * cm, 3.6 * cm])
    bench_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(bench_table)
    story.append(Spacer(1, 14))

    # ── SECTION 8: AI VOICE & TEXT ASSISTANT ─────────────────────────────────
    story.append(Paragraph("8. RecoverIQ AI Voice &amp; Text Assistant", h1_style))
    story.append(Paragraph(
        "Designed for on-the-go loan officers on motorbikes or in noisy branch counters, the AI assistant provides immediate natural language answers without needing to navigate complex spreadsheets.",
        body_style
    ))
    story.append(Paragraph("• <b>Microphone Audio Recording (🎙)</b>: Tap the microphone icon to record your voice. A live red indicator flashes with an active timer (<code>🔴 Listening / Recording... (0:04)</code>). Tap <code>Stop &amp; Send</code> to execute the voice query.", bullet_style))
    story.append(Paragraph("• <b>Speech-to-Text &amp; Audio Processing</b>: Uses native browser speech recognition (Web Speech API) and HTML5 MediaRecorder. Transcribes speech in real time and submits the query directly to <code>/api/v1/voice-bot/query</code>.", bullet_style))
    story.append(Paragraph("• <b>Keyboard Text Input (⌨)</b>: Officers can alternatively type queries or click one of the pre-built sample queries (<i>'Who should I call today?'</i>, <i>'How much money can we recover?'</i>, <i>'Check Client 103380'</i>, <i>'COBAC capital report'</i>).", bullet_style))
    story.append(Paragraph("• <b>Read Response Aloud (Voice Output)</b>: Checkbox toggle enables browser Text-to-Speech synthesis (<code>speechSynthesis</code>), reading the answer aloud through the smartphone's speaker for a complete hands-free conversational loop.", bullet_style))
    story.append(Paragraph("• <b>Professional English Speech</b>: All responses are delivered in clear, formal banking English, ensuring clarity for compliance audits.", bullet_style))
    story.append(Spacer(1, 14))

    # ── SECTION 9: CSV DATASET INGESTION PIPELINE ────────────────────────────
    story.append(Paragraph("9. CSV Dataset Ingestion &amp; Live Re-scoring Pipeline", h1_style))
    story.append(Paragraph(
        "RecoverIQ supports on-the-fly ingestion of new loan portfolios via the <b>⇪ Upload CSV</b> module:",
        body_style
    ))
    story.append(Paragraph("• <b>Touch File Selector</b>: Tap the upload dropzone to select any CSV file from iOS Files, Android Downloads, or desktop storage.", bullet_style))
    story.append(Paragraph("• <b>Direct CSV Text Paste</b>: Paste raw CSV text directly into the modal for quick testing or clipboard export.", bullet_style))
    story.append(Paragraph("• <b>Automated Schema Normalization</b>: Ingestion endpoint (<code>/api/v1/upload-csv</code>) automatically maps diverse schemas—including LendingClub loan formats (<code>loan_amnt, issue_d, total_rec_prncp</code>) and Core Banking System call sheets (<code>id, overdue_amount, loan_id</code>).", bullet_style))
    story.append(Paragraph("• <b>Live Portfolio Re-scoring</b>: Ingested loans are passed into the AdaptablePrioritiser ML model in memory, recalculating Cure Probabilities, Expected Net Recoveries, and priority ranks without server downtime.", bullet_style))
    story.append(Spacer(1, 14))

    # ── SECTION 10: 1-CLICK TAILORED CAMPAIGN DISPATCHER ─────────────────────
    story.append(Paragraph("10. 1-Click Tailored Campaign Dispatcher &amp; Pre-Flight Verification", h1_style))
    story.append(Paragraph(
        "The <b>1-Click Tailored Campaign Dispatcher</b> is RecoverIQ's high-efficiency bulk outreach engine. It enables recovery managers to trigger personalized, tone-segmented payment reminders to targeted borrower cohorts with a single verified execution, drastically cutting operational overhead.",
        body_style
    ))

    story.append(Paragraph("Core Operational Metrics &amp; Definitions:", h2_style))
    story.append(Paragraph(
        "• <b>Book Value Addressed (FCFA)</b>: The cumulative overdue principal, accrued interest, and penalty charges across all borrowers selected in the active campaign cohort.<br/>"
        "&nbsp;&nbsp;<code>Book Value Addressed = &Sigma; Overdue_Balance<sub>i</sub> for i &isin; Selected_Cohort</code><br/>"
        "&nbsp;&nbsp;<i>Operational Significance:</i> Measures the total financial capital targeted by the outreach batch. Targeting the full portfolio addresses <b>60,883,612 FCFA</b> in at-risk book value, while filtering for high-cure self-curers isolates fast liquidity with zero field overhead.<br/>"
        "• <b>Dispatch Cost (FCFA)</b>: The total projected direct operational expenditure to transmit the batch through telecommunication gateways.<br/>"
        "&nbsp;&nbsp;<code>Dispatch Cost = N<sub>recipients</sub> &times; Channel_Unit_Rate</code><br/>"
        "&nbsp;&nbsp;<i>Channel Rates:</i> <b>SMS @ 50 FCFA / recipient</b> (bulk transactional telco routing) vs. <b>WhatsApp @ 500 FCFA / recipient</b> (Meta Business API interactive rich templates with delivery telemetry).<br/>"
        "&nbsp;&nbsp;<i>Cost Efficiency:</i> A 400-borrower SMS campaign incurs only <b>20,000 FCFA</b> in total dispatch expenditure, compared to <b>200,000 FCFA</b> for manual telephone calls (500 FCFA each) or <b>800,000 FCFA</b> for motorcycle field visits (2,000 FCFA each)—delivering a 90% to 97.5% operational cost reduction.",
        formula_style
    ))

    story.append(Paragraph("Pre-Flight Message Verification (Human-in-the-Loop):", h2_style))
    story.append(Paragraph(
        "To prevent accidental transmissions and ensure compliance with microfinance ethics, the platform enforces mandatory <b>Pre-Flight Verification</b> before any batch execution:",
        body_style
    ))
    story.append(Paragraph("• <b>Individualized Copy Inspection</b>: Credit managers review a scrollable table displaying each recipient's Client ID, exact overdue arrears, phone contact, assigned Tone Badge, and customized message copy before confirming transmission.", bullet_style))
    story.append(Paragraph("• <b>Tone-Segmented Safeguards</b>: Messages are automatically generated based on borrower risk category:<br/>"
                           "&nbsp;&nbsp;– <b>🛡️ WELFARE SHIELD</b>: Supportive, empathetic phrasing offering restructuring options and hardship extensions for senior (&ge;60) or vulnerable borrowers.<br/>"
                           "&nbsp;&nbsp;– <b>💡 GENTLE NUDGE</b>: Cordial, low-friction mobile payment reminders for high-propensity borrowers who typically self-cure.<br/>"
                           "&nbsp;&nbsp;– <b>📋 STRUCTURED</b>: Formal, detailed contractual notices detailing branch cashier hours and repayment obligations for standard Stage A accounts.", bullet_style))
    story.append(Paragraph("• <b>COBAC &amp; MINFI Time-Gated Safety Shield</b>: Campaign broadcasts are strictly gated between <b>08:00 and 18:00 (GMT+1)</b>. Automated dispatches outside this window are blocked by the server to eliminate borrower harassment claims and regulatory fines.", bullet_style))
    story.append(Paragraph("• <b>Cryptographic Audit Trail</b>: Every sent message logs a permanent <code>CAMPAIGN_MESSAGE_SENT</code> transaction event with timestamp, channel, and operator ID into the SQLite regulatory audit ledger.", bullet_style))
    story.append(Spacer(1, 14))

    # ── SECTION 11: MASTER NUMERICAL REFERENCE TABLE ─────────────────────────
    story.append(Paragraph("11. Master Numerical Reference Table", h1_style))
    story.append(Paragraph("Quick-reference lookup table summarizing every key figure and parameter across the platform:", body_style))

    master_num_data = [
        [Paragraph("Parameter / Figure", table_head), Paragraph("Numerical Value", table_head), Paragraph("Calculation / Formula", table_head), Paragraph("Business Definition", table_head)],
        [Paragraph("Active Cohort Size", table_text), Paragraph("400 accounts", table_text), Paragraph("Stage A delinquent roster", table_text), Paragraph("Weekly active accounts undergoing prioritized collection.", table_text)],
        [Paragraph("Total Delinquent Book", table_text), Paragraph("60,883,612 FCFA", table_text), Paragraph("Sum(overdue_amount)", table_text), Paragraph("Total overdue principal and interest in branch book.", table_text)],
        [Paragraph("Expected Recoverable Cash", table_text), Paragraph("5,465,544 FCFA", table_text), Paragraph("Sum(prob * overdue)", table_text), Paragraph("Probabilistic weekly recovery volume across portfolio.", table_text)],
        [Paragraph("Financial Lift vs Heuristic", table_text), Paragraph("+2,160,000 FCFA", table_text), Paragraph("ML EV - Biggest Debt EV", table_text), Paragraph("Extra cash collected by contacting high-cure borrowers first.", table_text)],
        [Paragraph("Campaign Book Value Addressed", table_text), Paragraph("60,883,612 FCFA", table_text), Paragraph("Sum(overdue in cohort)", table_text), Paragraph("Delinquent book value reached in full 1-click campaign.", table_text)],
        [Paragraph("Campaign Dispatch Cost (SMS)", table_text), Paragraph("50 FCFA / recipient<br/>(20,000 FCFA full book)", table_text), Paragraph("N_recipients * 50 FCFA", table_text), Paragraph("Operational cost for automated bulk SMS outreach batch.", table_text)],
        [Paragraph("Campaign Dispatch Cost (WhatsApp)", table_text), Paragraph("500 FCFA / recipient<br/>(200,000 FCFA full book)", table_text), Paragraph("N_recipients * 500 FCFA", table_text), Paragraph("Operational cost for rich WhatsApp interactive template dispatch.", table_text)],
        [Paragraph("COBAC Contact Window", table_text), Paragraph("08:00 – 18:00 GMT+1", table_text), Paragraph("Hard legal time gate", table_text), Paragraph("Permitted borrower outreach window preventing harassment penalties.", table_text)],
        [Paragraph("Pre-Flight Verification Rate", table_text), Paragraph("100% human-verified", table_text), Paragraph("Mandatory modal review", table_text), Paragraph("Eliminates algorithmic hallucinations before bulk broadcasting.", table_text)],
        [Paragraph("Gross COBAC Provision", table_text), Paragraph("10,654,632 FCFA", table_text), Paragraph("20% * Total Arrears >= Day 31", table_text), Paragraph("Statutory capital write-down under CEMAC R-2017/07.", table_text)],
        [Paragraph("Net COBAC Reserve", table_text), Paragraph("2,823,205 FCFA", table_text), Paragraph("20% * (Arrears - Collateral)", table_text), Paragraph("Actual cash deduction required after recognizing collateral.", table_text)],
        [Paragraph("Preserved Capital", table_text), Paragraph("7,831,427 FCFA (73.5%)", table_text), Paragraph("Gross Provision - Net Required", table_text), Paragraph("Cooperative capital saved from mandatory statutory write-down.", table_text)],
        [Paragraph("Home Credit Top-50 Precision", table_text), Paragraph("92.0% (vs 74.0%)", table_text), Paragraph("TP / (TP + FP) at Top 50", table_text), Paragraph("Empirical accuracy on 307k real loans (+18.0% lift).", table_text)],
        [Paragraph("Home Credit Financial Lift", table_text), Paragraph("+$45,000 USD", table_text), Paragraph("ML Cash - Heuristic Cash", table_text), Paragraph("Top-50 cash advantage verified with zero feature leakage.", table_text)],
        [Paragraph("LendingClub Top-50 Precision", table_text), Paragraph("90.0% (vs 72.0%)", table_text), Paragraph("TP / (TP + FP) at Top 50", table_text), Paragraph("Empirical accuracy on 350k loans / 64k arrears (+18.0% lift).", table_text)],
        [Paragraph("LendingClub Top-50 Lift", table_text), Paragraph("+$40,600 USD", table_text), Paragraph("ML Cash - Heuristic Cash", table_text), Paragraph("Incremental cash collected on US unsecured arrears.", table_text)],
        [Paragraph("LendingClub Top-400 Lift", table_text), Paragraph("+$73,400 USD", table_text), Paragraph("ML Cash - Heuristic Cash", table_text), Paragraph("Cumulative financial gain across entire 400-account book.", table_text)],
        [Paragraph("SMS Intervention Cost", table_text), Paragraph("100 FCFA", table_text), Paragraph("Bulk SMS telco unit cost", table_text), Paragraph("Automated reminder cost weight in Net Recovery formula.", table_text)],
        [Paragraph("Phone Call Cost", table_text), Paragraph("500 FCFA", table_text), Paragraph("Airtime + 5 min officer time", table_text), Paragraph("Direct phone negotiation cost weight.", table_text)],
        [Paragraph("Field Visit Cost", table_text), Paragraph("2,000 FCFA", table_text), Paragraph("Motorbike fuel + transit time", table_text), Paragraph("In-person field confrontation cost weight.", table_text)],
        [Paragraph("Motorcycle Fuel Saved", table_text), Paragraph("13,600 FCFA / week", table_text), Paragraph("16 liters @ 850 FCFA/L", table_text), Paragraph("Direct branch operating expenses saved by gating visits.", table_text)],
        [Paragraph("Senior Shield Eligibility", table_text), Paragraph("Age >= 60 years", table_text), Paragraph("Borrower Age filter", table_text), Paragraph("Threshold diverting seniors from aggressive enforcement.", table_text)],
        [Paragraph("Protected Cohort Size", table_text), Paragraph("74 borrowers (18.5%)", table_text), Paragraph("Shielded accounts in book", table_text), Paragraph("Portion of book diverted to supportive restructuring.", table_text)],
        [Paragraph("PTP Keep Rate", table_text), Paragraph("100.0%", table_text), Paragraph("Kept / (Kept + Broken)", table_text), Paragraph("Proportion of recorded promises successfully honored.", table_text)],
        [Paragraph("PTP Cash Reconciled", table_text), Paragraph("65,000 FCFA", table_text), Paragraph("Sum(kept promise amount)", table_text), Paragraph("Cash credited to date through registered promise tracking.", table_text)],
        [Paragraph("Officer Champion Threshold", table_text), Paragraph("Score >= 85 pts", table_text), Paragraph("0-100 Composite Index", table_text), Paragraph("Qualifies officer for top monthly performance bonus.", table_text)],
    ]
    master_table = Table(master_num_data, colWidths=[4.2 * cm, 3.4 * cm, 4.4 * cm, 6.0 * cm])
    master_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_GREEN),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE_BG]),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(master_table)
    story.append(Spacer(1, 16))

    # Concluding Signature Block
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=1, color=DARK_GREEN, spaceBefore=10, spaceAfter=10),
        Paragraph("<b>DOCUMENT VALIDATION &amp; GOVERNANCE</b>", h2_style),
        Paragraph("This technical and operational manual serves as the standard operating procedure (SOP) for RecoverIQ deployments across commercial credit unions, microfinance establishments, and digital consumer loan operations under COBAC/CEMAC jurisdiction and international lending standards.<br/><b>Generated:</b> October 2026 · <b>Model Version:</b> RecoverIQ v2.6.4 · <b>Status:</b> Production Certified", body_style)
    ]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {output_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join("reports", "RecoverIQ_Platform_Guide_and_Metrics.pdf")
    create_platform_guide_pdf(out_file)
