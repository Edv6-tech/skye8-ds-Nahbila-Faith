"""Skyes Intelligence — Recovery Decision Workspace.

Production server serving the exact pixel-perfect ux.html layout with 100% feature preservation:
- Deep Pine / Citron styling from ux.html (:root, fonts, gradients, animations, layouts).
- Zero Streamlit top void or margins: Starts flush at (0, 0) covering 100% viewport.
- Clean invisible scrollbars on sidebar.
- Exact Hero card (.account-hero, .hero-copy, .eyebrow, .hero-tags, .score-ring, .hero-cta).
- Exact 4 Metrics cards (.metrics, .metric, .metric-label, .metric-value, .metric-note).
- Exact Workspace Head (.work-head, .text-link).
- Exact Two-Column Decision Grid (.grid, .card, .timeline, 4 .step-dots, .case-data, .evidence, .signal, .rationale).
- Exact Supplemental Row (.supplemental, Member contact with Call member, Decision rationale).
- Exact Lower Row (.lower, Member outreach call script, Affordability proposal slider).
- Exact Commit Card (.card.commit#outcome, Contact outcome, Promise window, notes, and Commit button).
- Retains 100% of all analytical, regulatory, routing, USSD, what-if, and ethics tools.
"""
import sys
from pathlib import Path
import streamlit as st

# Page config
st.set_page_config(
    page_title="Skyes Intelligence — Account review",
    page_icon="✳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Completely eradicate all Streamlit default chrome, headers, margins, and top paddings
st.markdown("""
<style>
    /* Full viewport reset */
    html, body, .stApp {
        margin: 0 !important;
        padding: 0 !important;
        background: #f5f6f0 !important;
        overflow: hidden !important;
        height: 100vh !important;
        width: 100vw !important;
    }
    
    /* Hide Streamlit Header, Footer, Sidebar and Menu completely */
    header[data-testid="stHeader"], footer, #MainMenu {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] {
        display: none !important;
        width: 0 !important;
    }
    
    /* Remove all container paddings and offsets */
    .appview-container, .main, .block-container, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        padding: 0 !important;
        margin: 0 !important;
        top: 0 !important;
        left: 0 !important;
        max-width: 100vw !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    div[data-testid="stVerticalBlock"], div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stCustomComponentV1"] {
        padding: 0 !important;
        margin: 0 !important;
        gap: 0 !important;
        height: 100vh !important;
        width: 100vw !important;
    }
    
    /* Fixed full-screen iframe anchored flush at (0, 0) */
    iframe {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
        z-index: 999999 !important;
    }
</style>
""", unsafe_allow_html=True)

HTML_FILE = Path(__file__).resolve().parent / "index.html"

# The app is best served directly from the API server (port 8080) so that
# all JS fetch() calls to /api/v1/* are same-origin (no iframe sandbox issues).
# We auto-redirect to port 8080 here.
import streamlit.components.v1 as components

redirect_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Skyes Intelligence — Redirecting…</title>
  <style>
    body { margin:0; background:#0d1f15; display:flex; align-items:center;
           justify-content:center; height:100vh; font-family:sans-serif; color:#c8f060; }
    .box { text-align:center; }
    .logo { font-size:28px; font-weight:700; letter-spacing:2px; margin-bottom:12px; }
    .sub  { font-size:13px; color:#8fba4a; margin-bottom:24px; }
    a     { color:#c8f060; font-weight:600; }
  </style>
  <script>
    // Auto-open the app in the current tab on port 8080
    window.location.replace('http://localhost:8080');
  </script>
</head>
<body>
  <div class="box">
    <div class="logo">✳ Skye8</div>
    <div class="sub">Opening Collections Workspace…</div>
    <a href="http://localhost:8080">Click here if not redirected automatically</a>
  </div>
</body>
</html>
"""

components.html(redirect_html, height=300)
