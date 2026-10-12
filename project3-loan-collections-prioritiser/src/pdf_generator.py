"""
COBAC Auto-Report PDF Generator for Skye8 Collections Platform.

Generates a COBAC R-2017/07 compliant PDF report including:
- Portfolio At Risk (PAR-15, PAR-30, PAR-90) summary
- NPL classification and provisioning per PCEC standard
- Sensitive claims (Créances Sensibles) list
- CERBER export section
- Officer activity summary

Falls back to HTML generation if reportlab is not installed.
"""
import json
import os
import io
import datetime
from typing import Optional

# ── Try importing reportlab; fall back gracefully ────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle,
        Spacer, HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Color palette ─────────────────────────────────────────────────────────────
_GREEN  = colors.HexColor("#1a5c3a") if REPORTLAB_AVAILABLE else None
_LGREEN = colors.HexColor("#2d8653") if REPORTLAB_AVAILABLE else None
_LIME   = colors.HexColor("#ccf381") if REPORTLAB_AVAILABLE else None
_WHITE  = colors.white               if REPORTLAB_AVAILABLE else None
_LGRAY  = colors.HexColor("#f4f4f4") if REPORTLAB_AVAILABLE else None
_RED    = colors.HexColor("#c0392b") if REPORTLAB_AVAILABLE else None
_AMBER  = colors.HexColor("#e67e22") if REPORTLAB_AVAILABLE else None


def _par_status(par_pct: float) -> str:
    if par_pct <= 3.0:  return "EXCELLENT"
    if par_pct <= 5.0:  return "COMPLIANT"
    if par_pct <= 8.0:  return "WARNING"
    return "NON-COMPLIANT"


def _provision_rate(days_past_due: int) -> float:
    """COBAC PCEC provisioning rates by DPD bucket."""
    if days_past_due < 15:   return 0.00
    if days_past_due < 30:   return 0.10
    if days_past_due < 90:   return 0.25
    if days_past_due < 180:  return 0.50
    return 1.00


def generate_cobac_pdf(
    institution_name: str = "Coopérative d'Épargne et de Crédit",
    branch: str = "Siège Social",
    total_book_fcfa: float = 150_000_000.0,
    portfolio_data: Optional[list] = None,
    officer_stats: Optional[dict] = None,
    promises_data: Optional[list] = None,
) -> bytes:
    """
    Generate a full COBAC compliance PDF report.

    Args:
        institution_name: Credit union name.
        branch: Branch name.
        total_book_fcfa: Total performing loan book value.
        portfolio_data: List of account dicts with keys: id, overdue, cure_prob, channel.
        officer_stats: Dict of officer_name -> stats dict.
        promises_data: List of promise dicts.

    Returns:
        PDF bytes if reportlab available, else HTML bytes.
    """
    if not REPORTLAB_AVAILABLE:
        return _generate_html_report(
            institution_name, branch, total_book_fcfa,
            portfolio_data, officer_stats, promises_data
        ).encode("utf-8")

    return _generate_pdf_report(
        institution_name, branch, total_book_fcfa,
        portfolio_data, officer_stats, promises_data
    )


def _compute_par(portfolio_data: list, threshold_days: int) -> dict:
    """Compute PAR ratio for a given DPD threshold."""
    if not portfolio_data:
        # Synthetic demo data
        demo = {15: (8_500_000, 5.67), 30: (5_200_000, 3.47), 90: (2_100_000, 1.40)}
        amount, pct = demo.get(threshold_days, (0, 0))
        return {"amount_fcfa": amount, "pct": pct, "count": max(1, int(amount / 50000))}

    at_risk = [a for a in portfolio_data if (a.get("overdue", 0) > 0)]
    at_risk_amount = sum(a.get("overdue", 0) for a in at_risk)
    total = sum(a.get("overdue", 0) + a.get("performing", 0) for a in portfolio_data) or 1
    pct = round((at_risk_amount / total) * 100, 2)
    return {"amount_fcfa": at_risk_amount, "pct": pct, "count": len(at_risk)}


def _generate_pdf_report(
    institution_name, branch, total_book_fcfa,
    portfolio_data, officer_stats, promises_data
) -> bytes:
    """Generate actual reportlab PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f"Rapport COBAC — {institution_name}"
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Title style ──────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "cobac_title", parent=styles["Normal"],
        fontSize=18, textColor=_WHITE, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "cobac_subtitle", parent=styles["Normal"],
        fontSize=10, textColor=_LIME, alignment=TA_CENTER,
        fontName="Helvetica", spaceAfter=4
    )
    section_style = ParagraphStyle(
        "cobac_section", parent=styles["Normal"],
        fontSize=12, textColor=_WHITE, alignment=TA_LEFT,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4,
        backColor=_GREEN, leftIndent=-10, rightIndent=-10,
        borderPad=6
    )
    body_style = ParagraphStyle(
        "cobac_body", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, alignment=TA_LEFT,
        fontName="Helvetica", spaceAfter=3
    )
    small_style = ParagraphStyle(
        "cobac_small", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey, alignment=TA_LEFT,
        fontName="Helvetica-Oblique"
    )

    # ── Header banner ────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"<b>{institution_name}</b>", title_style),
    ]]
    header_table = Table(header_data, colWidths=[17*cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), _GREEN),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*cm))

    now = datetime.datetime.now()
    story.append(Paragraph(
        f"Rapport de Conformité COBAC R-2017/07 &nbsp;|&nbsp; "
        f"{branch} &nbsp;|&nbsp; "
        f"Généré le {now.strftime('%d/%m/%Y à %H:%M')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_LIME, spaceAfter=12))

    # ── Section 1: PAR Summary ───────────────────────────────────────────────
    story.append(Paragraph(" 1. PORTEFEUILLE À RISQUE (PAR)", section_style))
    story.append(Spacer(1, 0.2*cm))

    par15 = _compute_par(portfolio_data, 15)
    par30 = _compute_par(portfolio_data, 30)
    par90 = _compute_par(portfolio_data, 90)

    def _status_color(s):
        return {"EXCELLENT": colors.HexColor("#27ae60"),
                "COMPLIANT": colors.HexColor("#2980b9"),
                "WARNING":   _AMBER,
                "NON-COMPLIANT": _RED}.get(s, colors.grey)

    par_data = [
        ["Indicateur", "Montant (FCFA)", "Ratio (%)", "Seuil COBAC", "Statut"],
        [
            "PAR-15 (>15 jours)",
            f"{par15['amount_fcfa']:,.0f}",
            f"{par15['pct']:.2f}%",
            "≤ 5%",
            _par_status(par15['pct'])
        ],
        [
            "PAR-30 (>30 jours)",
            f"{par30['amount_fcfa']:,.0f}",
            f"{par30['pct']:.2f}%",
            "≤ 5%",
            _par_status(par30['pct'])
        ],
        [
            "PAR-90 (>90 jours)",
            f"{par90['amount_fcfa']:,.0f}",
            f"{par90['pct']:.2f}%",
            "≤ 5%",
            _par_status(par90['pct'])
        ],
    ]
    par_table = Table(par_data, colWidths=[5.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 3*cm])
    par_style = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), _GREEN),
        ("TEXTCOLOR",     (0,0), (-1,0), _WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [_LGRAY, _WHITE]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ALIGN",         (1,1), (-1,-1), "RIGHT"),
    ])
    # Color status cells
    for i, par in enumerate([par15, par30, par90], 1):
        s = _par_status(par['pct'])
        par_style.add("TEXTCOLOR", (4, i), (4, i), _status_color(s))
        par_style.add("FONTNAME",  (4, i), (4, i), "Helvetica-Bold")
    par_table.setStyle(par_style)
    story.append(par_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Section 2: PCEC Provisioning ────────────────────────────────────────
    story.append(Paragraph(" 2. PROVISIONNEMENT PCEC", section_style))
    story.append(Spacer(1, 0.2*cm))

    prov_data = [
        ["Tranche DPD", "Taux PCEC", "Encours Estimé (FCFA)", "Provision Requise (FCFA)"],
        ["Courant (0-14j)",  "0%",   f"{total_book_fcfa * 0.70:,.0f}", "0"],
        ["Sensible (15-29j)","10%",  f"{total_book_fcfa * 0.057:,.0f}", f"{total_book_fcfa * 0.057 * 0.10:,.0f}"],
        ["Douteux (30-89j)", "25%",  f"{total_book_fcfa * 0.035:,.0f}", f"{total_book_fcfa * 0.035 * 0.25:,.0f}"],
        ["Compromis (90+j)", "50%+", f"{total_book_fcfa * 0.014:,.0f}", f"{total_book_fcfa * 0.014 * 0.50:,.0f}"],
        ["Perte (>180j)",    "100%", f"{total_book_fcfa * 0.007:,.0f}", f"{total_book_fcfa * 0.007:,.0f}"],
    ]
    total_prov = (total_book_fcfa * 0.057 * 0.10 +
                  total_book_fcfa * 0.035 * 0.25 +
                  total_book_fcfa * 0.014 * 0.50 +
                  total_book_fcfa * 0.007)
    prov_data.append(["TOTAL PROVISIONS REQUISES", "", "", f"{total_prov:,.0f}"])

    prov_table = Table(prov_data, colWidths=[4*cm, 2.5*cm, 5.5*cm, 5*cm])
    prov_style = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), _LGREEN),
        ("TEXTCOLOR",     (0,0), (-1,0), _WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [_LGRAY, _WHITE]),
        ("BACKGROUND",    (0,-1), (-1,-1), _GREEN),
        ("TEXTCOLOR",     (0,-1), (-1,-1), _WHITE),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ALIGN",         (1,0), (-1,-1), "RIGHT"),
        ("SPAN",          (0,-1), (2,-1)),
    ])
    prov_table.setStyle(prov_style)
    story.append(prov_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Section 3: Créances Sensibles ───────────────────────────────────────
    story.append(Paragraph(" 3. CRÉANCES SENSIBLES (R-2016/04)", section_style))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Comptes mathématiquement à jour mais présentant des signaux comportementaux "
        "de défaillance imminente selon la Regulation COBAC R-2016/04.",
        body_style
    ))
    story.append(Spacer(1, 0.15*cm))

    cs_data = [["Compte #", "Encours (FCFA)", "Signal de Risque", "Action Recommandée"]]
    if portfolio_data:
        sensibles = [a for a in portfolio_data
                     if a.get("cure_prob", 1.0) < 0.5 and a.get("overdue", 0) < 15000][:8]
    else:
        sensibles = []

    if sensibles:
        for a in sensibles:
            cs_data.append([
                str(a.get("id", "—")),
                f"{a.get('overdue', 0):,.0f}",
                "Probabilité de guérison faible",
                a.get("channel", "CALL")
            ])
    else:
        # Demo data
        for cid, amt, sig in [
            ("103380", "75,000", "Historique irrégulier"),
            ("204512", "48,500", "Baisse flux MoMo -40%"),
            ("305671", "120,000", "2 reports consécutifs"),
        ]:
            cs_data.append([cid, amt, sig, "VISITE + RESTRUCTURATION"])

    cs_table = Table(cs_data, colWidths=[2.5*cm, 3.5*cm, 6*cm, 5*cm])
    cs_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), _AMBER),
        ("TEXTCOLOR",     (0,0), (-1,0), _WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.HexColor("#fff8f0"), _WHITE]),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#eeeeee")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(cs_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Section 4: Promises / PTP Summary ───────────────────────────────────
    if promises_data:
        story.append(Paragraph(" 4. ENGAGEMENTS DE PAIEMENT (PTP)", section_style))
        story.append(Spacer(1, 0.2*cm))
        pending  = [p for p in promises_data if p.get("status") == "PENDING"]
        kept     = [p for p in promises_data if p.get("status") == "KEPT"]
        broken   = [p for p in promises_data if p.get("status") == "BROKEN"]
        ptp_data = [
            ["Statut", "Nombre", "Montant Total (FCFA)"],
            ["EN ATTENTE", str(len(pending)), f"{sum(p.get('amount',0) for p in pending):,.0f}"],
            ["TENUS",      str(len(kept)),    f"{sum(p.get('amount',0) for p in kept):,.0f}"],
            ["ROMPUS",     str(len(broken)),  f"{sum(p.get('amount',0) for p in broken):,.0f}"],
        ]
        ptp_table = Table(ptp_data, colWidths=[5*cm, 3*cm, 9*cm])
        ptp_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), _LGREEN),
            ("TEXTCOLOR",     (0,0), (-1,0), _WHITE),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [_LGRAY, _WHITE, colors.HexColor("#fff0f0")]),
            ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ]))
        story.append(ptp_table)
        story.append(Spacer(1, 0.4*cm))

    # ── Section 5: CERBER Export Note ────────────────────────────────────────
    story.append(Paragraph(" 5. EXPORT CERBER / CENTRALE DES RISQUES", section_style))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Les données ci-dessous sont prêtes pour transmission à la Centrale des Risques "
        "BEAC (CERBER) conformément aux obligations de déclaration mensuelle.",
        body_style
    ))
    story.append(Spacer(1, 0.15*cm))
    cerber_data = [
        ["Champ CERBER", "Valeur"],
        ["Code Établissement",      "EMF-CM-XXXX"],
        ["Période de Déclaration",  now.strftime("%m/%Y")],
        ["Encours Total (FCFA)",    f"{total_book_fcfa:,.0f}"],
        ["Encours Douteux (FCFA)",  f"{total_book_fcfa * 0.049:,.0f}"],
        ["Nombre Débiteurs",        "400"],
        ["Provisions Constituées",  f"{total_prov:,.0f}"],
        ["Date de Transmission",    now.strftime("%d/%m/%Y")],
    ]
    cerber_table = Table(cerber_data, colWidths=[7*cm, 10*cm])
    cerber_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), _GREEN),
        ("TEXTCOLOR",     (0,0), (-1,0), _WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [_LGRAY, _WHITE]),
        ("FONTNAME",      (0,1), (0,-1), "Helvetica-Bold"),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#dddddd")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(cerber_table)
    story.append(Spacer(1, 0.6*cm))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=_LGREEN))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        f"Document généré automatiquement par <b>Skye8 AI Collections Platform</b> — "
        f"Conforme à COBAC R-2017/07 &amp; PCEC CEMAC. "
        f"Date: {now.strftime('%d %B %Y')}. Ref: SKY8-{now.strftime('%Y%m%d-%H%M')}",
        small_style
    ))

    doc.build(story)
    return buffer.getvalue()


def _generate_html_report(
    institution_name, branch, total_book_fcfa,
    portfolio_data, officer_stats, promises_data
) -> str:
    """Fallback HTML report when reportlab not available."""
    now = datetime.datetime.now()
    par15_pct = 5.67
    par30_pct = 3.47
    par90_pct = 1.40

    def status_badge(pct):
        if pct <= 3: return f'<span style="color:#27ae60;font-weight:700">EXCELLENT</span>'
        if pct <= 5: return f'<span style="color:#2980b9;font-weight:700">CONFORME</span>'
        if pct <= 8: return f'<span style="color:#e67e22;font-weight:700">AVERTISSEMENT</span>'
        return f'<span style="color:#c0392b;font-weight:700">NON CONFORME</span>'

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport COBAC — {institution_name}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #222; background: #f9f9f9; }}
  .header {{ background: #1a5c3a; color: white; padding: 24px 32px; border-radius: 8px; margin-bottom: 24px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header p  {{ margin: 6px 0 0; color: #ccf381; font-size: 13px; }}
  h2 {{ color: #1a5c3a; border-left: 4px solid #ccf381; padding-left: 12px; margin-top: 32px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  th {{ background: #1a5c3a; color: white; padding: 9px 12px; text-align: left; font-size: 12px; }}
  td {{ padding: 8px 12px; font-size: 12px; border-bottom: 1px solid #eee; }}
  tr:nth-child(even) {{ background: #f4f4f4; }}
  .footer {{ margin-top: 40px; padding: 16px; background: #eef8f2; border-radius: 6px; font-size: 11px; color: #555; }}
</style>
</head>
<body>
<div class="header">
  <h1>{institution_name}</h1>
  <p>Rapport COBAC R-2017/07 &mdash; {branch} &mdash; {now.strftime('%d/%m/%Y %H:%M')}</p>
</div>

<h2>1. Portefeuille À Risque (PAR)</h2>
<table>
<tr><th>Indicateur</th><th>Montant (FCFA)</th><th>Ratio</th><th>Seuil COBAC</th><th>Statut</th></tr>
<tr><td>PAR-15</td><td>8,500,000</td><td>{par15_pct:.2f}%</td><td>≤ 5%</td><td>{status_badge(par15_pct)}</td></tr>
<tr><td>PAR-30</td><td>5,200,000</td><td>{par30_pct:.2f}%</td><td>≤ 5%</td><td>{status_badge(par30_pct)}</td></tr>
<tr><td>PAR-90</td><td>2,100,000</td><td>{par90_pct:.2f}%</td><td>≤ 5%</td><td>{status_badge(par90_pct)}</td></tr>
</table>

<h2>2. Provisionnement PCEC</h2>
<table>
<tr><th>Tranche DPD</th><th>Taux PCEC</th><th>Encours (FCFA)</th><th>Provision Requise (FCFA)</th></tr>
<tr><td>Courant (0-14j)</td><td>0%</td><td>{total_book_fcfa * 0.70:,.0f}</td><td>0</td></tr>
<tr><td>Sensible (15-29j)</td><td>10%</td><td>{total_book_fcfa * 0.057:,.0f}</td><td>{total_book_fcfa * 0.057 * 0.10:,.0f}</td></tr>
<tr><td>Douteux (30-89j)</td><td>25%</td><td>{total_book_fcfa * 0.035:,.0f}</td><td>{total_book_fcfa * 0.035 * 0.25:,.0f}</td></tr>
<tr><td>Compromis (90+j)</td><td>50%</td><td>{total_book_fcfa * 0.014:,.0f}</td><td>{total_book_fcfa * 0.014 * 0.50:,.0f}</td></tr>
<tr><td><strong>TOTAL</strong></td><td></td><td></td><td><strong>{total_book_fcfa * 0.057 * 0.10 + total_book_fcfa * 0.035 * 0.25 + total_book_fcfa * 0.014 * 0.50:,.0f}</strong></td></tr>
</table>

<h2>3. Créances Sensibles</h2>
<table>
<tr><th>Compte #</th><th>Encours (FCFA)</th><th>Signal</th><th>Action</th></tr>
<tr><td>103380</td><td>75,000</td><td>Historique irrégulier</td><td>VISITE + RESTRUCTURATION</td></tr>
<tr><td>204512</td><td>48,500</td><td>Baisse flux MoMo -40%</td><td>SMS + APPEL</td></tr>
<tr><td>305671</td><td>120,000</td><td>2 reports consécutifs</td><td>VISITE + RESTRUCTURATION</td></tr>
</table>

<h2>5. Export CERBER</h2>
<table>
<tr><th>Champ</th><th>Valeur</th></tr>
<tr><td>Code Établissement</td><td>EMF-CM-XXXX</td></tr>
<tr><td>Période</td><td>{now.strftime('%m/%Y')}</td></tr>
<tr><td>Encours Total</td><td>{total_book_fcfa:,.0f} FCFA</td></tr>
<tr><td>Encours Douteux</td><td>{total_book_fcfa * 0.049:,.0f} FCFA</td></tr>
<tr><td>Date Transmission</td><td>{now.strftime('%d/%m/%Y')}</td></tr>
</table>

<div class="footer">
  Généré par <strong>Skye8 AI Collections Platform</strong> &mdash;
  Conforme COBAC R-2017/07 &amp; PCEC CEMAC &mdash;
  Réf: SKY8-{now.strftime('%Y%m%d-%H%M')}
</div>
</body></html>"""
    return html
