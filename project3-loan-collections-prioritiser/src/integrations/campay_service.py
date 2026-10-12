"""
CamPay USSD Push Service for Skye8 Collections Platform.

Triggers mobile money collection requests via the CamPay API
(https://campay.net) — a local Cameroonian payment aggregator
supporting MTN MoMo and Orange Money via a single REST endpoint.

Falls back to a realistic simulation when CAMPAY_API_KEY is not set.
"""
import os
import uuid
import logging
import datetime
from typing import Dict, Any

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

logger = logging.getLogger("CamPayService")

# ── Config ────────────────────────────────────────────────────────────────────
CAMPAY_API_KEY  = os.getenv("CAMPAY_API_KEY", "")
CAMPAY_BASE_URL = os.getenv("CAMPAY_BASE_URL", "https://demo.campay.net/api")

# Simulation mode when no key is set
_SIMULATION_MODE = not bool(CAMPAY_API_KEY)


def trigger_ussd_push(
    phone: str,
    amount_fcfa: float,
    account_id: int,
    loan_id: int = 0,
    description: str = "",
) -> Dict[str, Any]:
    """
    Trigger a USSD push payment request to a borrower's mobile money wallet.

    The borrower receives a USSD prompt on their phone asking them to
    authorise the loan repayment by entering their MoMo PIN.

    Args:
        phone: Cameroonian phone number (format: 237XXXXXXXXX).
        amount_fcfa: Amount to collect in FCFA.
        account_id: Internal account identifier.
        loan_id: Internal loan identifier.
        description: Description shown on borrower's phone.

    Returns:
        Dict with keys: reference, status, message, provider, simulated.
    """
    if amount_fcfa <= 0:
        return {"error": "Amount must be positive.", "status": "FAILED"}

    phone = _normalise_phone(phone)
    if not phone:
        return {"error": "Invalid phone number.", "status": "FAILED"}

    description = description or (
        f"Remboursement prêt #{loan_id or account_id} — "
        f"Skye8 COOPEC ({datetime.date.today().strftime('%d/%m/%Y')})"
    )
    provider = _detect_provider(phone)
    reference = f"SKY8-{account_id}-{str(uuid.uuid4())[:6].upper()}"

    if _SIMULATION_MODE:
        return _simulate_push(phone, amount_fcfa, reference, provider, description)

    return _live_push(phone, amount_fcfa, reference, provider, description)


def _live_push(phone, amount_fcfa, reference, provider, description) -> Dict:
    """Call the real CamPay Collections API."""
    if not _REQUESTS_AVAILABLE:
        logger.error("requests library not available.")
        return {"error": "requests not installed", "status": "FAILED"}

    headers = {
        "Authorization": f"Token {CAMPAY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "amount":      str(int(amount_fcfa)),
        "currency":    "XAF",
        "from":        phone,
        "description": description,
        "external_reference": reference,
    }
    try:
        resp = _requests.post(
            f"{CAMPAY_BASE_URL}/collect/",
            json=payload,
            headers=headers,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("status") in ("SUCCESSFUL", "PENDING"):
            return {
                "reference":  data.get("reference", reference),
                "status":     data.get("status", "PENDING"),
                "message":    "USSD push sent successfully. Awaiting borrower PIN.",
                "provider":   provider,
                "amount_fcfa": amount_fcfa,
                "phone":      phone[:6] + "XXXXXX",
                "simulated":  False,
            }
        else:
            logger.warning(f"CamPay error: {data}")
            return {
                "reference": reference,
                "status":    "FAILED",
                "message":   data.get("message", "CamPay API error."),
                "provider":  provider,
                "simulated": False,
            }
    except Exception as e:
        logger.error(f"CamPay request failed: {e}")
        return {"reference": reference, "status": "FAILED", "message": str(e), "simulated": False}


def _simulate_push(phone, amount_fcfa, reference, provider, description) -> Dict:
    """Realistic simulation for demo/dev mode."""
    import random
    # 85% success rate simulation (realistic for USSD push)
    success = random.random() < 0.85
    logger.info(
        f"[SIMULATION] CamPay USSD push — {phone} — {amount_fcfa:,.0f} FCFA — "
        f"{'SUCCESS' if success else 'FAILED'}"
    )
    if success:
        return {
            "reference":   reference,
            "status":      "PENDING",
            "message":     (
                f"[DEMO] USSD push sent to {phone[:6]}XXXXXX via {provider}. "
                f"Borrower will receive prompt for {amount_fcfa:,.0f} FCFA. "
                f"Set CAMPAY_API_KEY in .env for live payments."
            ),
            "provider":    provider,
            "amount_fcfa": amount_fcfa,
            "phone":       phone[:6] + "XXXXXX",
            "simulated":   True,
            "demo_note":   "Add CAMPAY_API_KEY to .env to go live.",
        }
    else:
        return {
            "reference": reference,
            "status":    "FAILED",
            "message":   "[DEMO] Simulated failure (15% rate). Retry or call officer.",
            "provider":  provider,
            "simulated": True,
        }


def check_payment_status(reference: str) -> Dict[str, Any]:
    """
    Check the status of a previous USSD push by reference ID.

    Args:
        reference: The reference returned by trigger_ussd_push.

    Returns:
        Dict with current status.
    """
    if _SIMULATION_MODE:
        import random
        # Simulate payment completion
        paid = random.random() < 0.70
        return {
            "reference": reference,
            "status":    "SUCCESSFUL" if paid else "PENDING",
            "message":   "Payment confirmed." if paid else "Waiting for borrower PIN.",
            "simulated": True,
        }

    if not _REQUESTS_AVAILABLE:
        return {"error": "requests not installed", "status": "UNKNOWN"}

    headers = {"Authorization": f"Token {CAMPAY_API_KEY}"}
    try:
        resp = _requests.get(
            f"{CAMPAY_BASE_URL}/transaction/{reference}/",
            headers=headers,
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        return {"reference": reference, "status": "UNKNOWN", "error": str(e)}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalise_phone(phone: str) -> str:
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 9:
        digits = "237" + digits
    if len(digits) == 12 and digits.startswith("237"):
        return digits
    return ""


def _detect_provider(phone: str) -> str:
    """Detect MTN or Orange based on prefix."""
    mtn_prefixes    = ("23767", "23768", "23679")
    orange_prefixes = ("23765", "23769")
    for p in mtn_prefixes:
        if phone.startswith(p):
            return "MTN_MOMO"
    for p in orange_prefixes:
        if phone.startswith(p):
            return "ORANGE_MONEY"
    return "MTN_MOMO"  # Default
