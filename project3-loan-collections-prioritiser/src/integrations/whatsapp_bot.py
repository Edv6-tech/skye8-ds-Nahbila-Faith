"""
WhatsApp Collections Sequence Bot for Skye8 Collections Platform.

Orchestrates a multi-step automated outreach sequence for delinquent borrowers:
  Day 1:  Friendly French reminder
  Day 3:  Pidgin message + MoMo payment link
  Day 7:  Restructuring offer (50% now / 50% next month)
  Day 15: Flag for field officer visit

Uses the existing Twilio WhatsApp integration (WHATSAPP_ACCESS_TOKEN / TWILIO_*)
and logs all sequence activities to data/whatsapp_sequences.json.
"""
import os
import json
import uuid
import logging
import datetime
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger("WhatsAppBot")

# ── Storage ───────────────────────────────────────────────────────────────────
_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SEQ_FILE  = os.path.join(_ROOT, "data", "whatsapp_sequences.json")
_lock      = threading.Lock()


def _load_sequences() -> List[Dict]:
    if not os.path.exists(_SEQ_FILE):
        return []
    try:
        with open(_SEQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_sequences(seqs: List[Dict]) -> None:
    os.makedirs(os.path.dirname(_SEQ_FILE), exist_ok=True)
    tmp = _SEQ_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seqs, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _SEQ_FILE)


# ── Message templates ─────────────────────────────────────────────────────────

def _build_message(step: int, account_id: int, overdue_fcfa: float,
                   client_name: str = "", loan_id: int = 0) -> Dict[str, str]:
    """Return message text for a given sequence step."""
    name    = client_name or f"Client #{account_id}"
    amount  = f"{overdue_fcfa:,.0f} FCFA"
    half    = f"{overdue_fcfa / 2:,.0f} FCFA"
    # CamPay pay link (simulated)
    pay_url = f"https://pay.campay.net/skye8/{account_id}"

    messages = {
        1: {
            "lang": "French",
            "subject": "Rappel de remboursement",
            "text": (
                f"Cher(e) {name},\n\n"
                f"Nous vous rappelons que votre remboursement de *{amount}* "
                f"est dû. Veuillez effectuer votre paiement dès que possible "
                f"pour maintenir votre bon dossier de crédit.\n\n"
                f"Paiement rapide : {pay_url}\n\n"
                f"Merci de votre confiance.\n"
                f"— Votre Coopérative (Skye8)"
            ),
        },
        3: {
            "lang": "Pidgin",
            "subject": "Friendly Pidgin follow-up + MoMo link",
            "text": (
                f"Bother {name}!\n\n"
                f"We remember say yu get *{amount}* wey yu owe. "
                f"No worry, e easy to pay now. "
                f"Click dis link make yu pay with MoMo or Orange Money:\n"
                f"{pay_url}\n\n"
                f"If yu get problem, call we officer. We de here help yu. "
                f"Make we sort am together!\n"
                f"— Skye8 COOPEC"
            ),
        },
        7: {
            "lang": "French + Pidgin",
            "subject": "Restructuring offer",
            "text": (
                f"Cher(e) {name},\n\n"
                f"Nous comprenons que les difficultés financières peuvent survenir. "
                f"Nous vous proposons un arrangement :\n\n"
                f"✅ *Option Flexible :*\n"
                f"   • Payez {half} maintenant\n"
                f"   • {half} le mois prochain\n\n"
                f"Pour accepter, payez {half} ici : {pay_url}\n\n"
                f"[Pidgin] Bother, we fit help yu. Pay {half} now, "
                f"den {half} next month. Link: {pay_url}\n\n"
                f"— Skye8 COOPEC"
            ),
        },
        15: {
            "lang": "French",
            "subject": "Field officer visit notice",
            "text": (
                f"Cher(e) {name},\n\n"
                f"Malgré nos rappels, votre solde impayé de *{amount}* "
                f"n'a pas encore été réglé. Un agent de notre coopérative "
                f"vous rendra visite prochainement pour discuter d'une solution.\n\n"
                f"Pour éviter cette démarche, payez maintenant : {pay_url}\n\n"
                f"— Direction, Skye8 COOPEC"
            ),
        },
    }
    return messages.get(step, messages[1])


# ── Public API ────────────────────────────────────────────────────────────────

def start_sequence(
    account_id: int,
    phone: str,
    overdue_fcfa: float,
    loan_id: int = 0,
    client_name: str = "",
    officer_name: str = "System",
) -> Dict[str, Any]:
    """
    Start a WhatsApp outreach sequence for a delinquent account.

    Sends Step 1 immediately and schedules Steps 3, 7, 15.

    Returns the sequence record.
    """
    seq_id = f"WA-{str(uuid.uuid4())[:8].upper()}"
    now    = datetime.datetime.utcnow()

    # Build schedule
    schedule = [
        {"step": 1, "day_offset": 0,  "scheduled_at": now.isoformat() + "Z",
         "status": "PENDING", "sent_at": None},
        {"step": 3, "day_offset": 3,  "scheduled_at": (now + datetime.timedelta(days=3)).isoformat() + "Z",
         "status": "PENDING", "sent_at": None},
        {"step": 7, "day_offset": 7,  "scheduled_at": (now + datetime.timedelta(days=7)).isoformat() + "Z",
         "status": "PENDING", "sent_at": None},
        {"step": 15,"day_offset": 15, "scheduled_at": (now + datetime.timedelta(days=15)).isoformat() + "Z",
         "status": "PENDING", "sent_at": None},
    ]

    sequence = {
        "seq_id":       seq_id,
        "account_id":   int(account_id),
        "loan_id":      int(loan_id),
        "phone":        str(phone),
        "overdue_fcfa": float(overdue_fcfa),
        "client_name":  str(client_name),
        "officer_name": str(officer_name),
        "status":       "ACTIVE",   # ACTIVE / COMPLETED / STOPPED (payment received)
        "created_at":   now.isoformat() + "Z",
        "schedule":     schedule,
        "messages_sent": [],
    }

    # Send Step 1 immediately
    result = _send_step(sequence, step_index=0)
    sequence["messages_sent"].append(result)
    sequence["schedule"][0]["status"] = "SENT" if result.get("sent") else "FAILED"
    sequence["schedule"][0]["sent_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    with _lock:
        seqs = _load_sequences()
        seqs.append(sequence)
        _save_sequences(seqs)

    return {
        "success":    True,
        "seq_id":     seq_id,
        "step_sent":  1,
        "next_step":  3,
        "next_date":  schedule[1]["scheduled_at"][:10],
        "message_preview": result.get("text", "")[:120] + "...",
        "simulated":  result.get("simulated", True),
    }


def list_sequences(
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Return sequence records with optional filters."""
    with _lock:
        seqs = _load_sequences()

    if account_id is not None:
        seqs = [s for s in seqs if s.get("account_id") == account_id]
    if status:
        seqs = [s for s in seqs if s.get("status", "").upper() == status.upper()]

    seqs.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return seqs[:limit]


def stop_sequence(seq_id: str, reason: str = "Payment received") -> Dict[str, Any]:
    """Stop an active sequence (e.g. when payment is confirmed)."""
    with _lock:
        seqs = _load_sequences()
        for s in seqs:
            if s.get("seq_id") == seq_id:
                s["status"] = "STOPPED"
                s["stop_reason"] = reason
                s["stopped_at"] = datetime.datetime.utcnow().isoformat() + "Z"
                _save_sequences(seqs)
                return {"success": True, "seq_id": seq_id, "status": "STOPPED"}
    raise KeyError(f"Sequence '{seq_id}' not found.")


def get_pending_sends() -> List[Dict]:
    """Return scheduled messages that are due to be sent now (for scheduler)."""
    now = datetime.datetime.utcnow()
    due = []
    with _lock:
        seqs = _load_sequences()
    for seq in seqs:
        if seq.get("status") != "ACTIVE":
            continue
        for i, step in enumerate(seq.get("schedule", [])):
            if step.get("status") != "PENDING":
                continue
            scheduled = datetime.datetime.fromisoformat(
                step["scheduled_at"].replace("Z", "")
            )
            if scheduled <= now:
                due.append({"seq": seq, "step_index": i})
    return due


def get_summary() -> Dict[str, Any]:
    """Return aggregate WhatsApp sequence stats."""
    with _lock:
        seqs = _load_sequences()
    active    = [s for s in seqs if s.get("status") == "ACTIVE"]
    stopped   = [s for s in seqs if s.get("status") == "STOPPED"]
    total_sent = sum(len(s.get("messages_sent", [])) for s in seqs)
    return {
        "total_sequences":  len(seqs),
        "active_sequences": len(active),
        "stopped_sequences":len(stopped),
        "total_messages_sent": total_sent,
        "accounts_in_sequence": list({s["account_id"] for s in active}),
    }


# ── Private ───────────────────────────────────────────────────────────────────

def _send_step(sequence: Dict, step_index: int) -> Dict[str, Any]:
    """Send one sequence step via Twilio WhatsApp or simulate."""
    step_num  = sequence["schedule"][step_index]["step"]
    msg_data  = _build_message(
        step_num,
        sequence["account_id"],
        sequence["overdue_fcfa"],
        sequence.get("client_name", ""),
        sequence.get("loan_id", 0),
    )
    text  = msg_data["text"]
    phone = sequence["phone"]

    # Try Twilio
    sent = _send_whatsapp(phone, text)

    return {
        "step":        step_num,
        "lang":        msg_data["lang"],
        "text":        text,
        "sent":        sent["success"],
        "sent_at":     datetime.datetime.utcnow().isoformat() + "Z",
        "simulated":   sent.get("simulated", True),
        "provider":    sent.get("provider", "simulation"),
        "error":       sent.get("error", ""),
    }


def _send_whatsapp(phone: str, text: str) -> Dict[str, Any]:
    """Send via Meta Cloud API → Twilio fallback → simulation."""

    # ── 1. Meta WhatsApp Cloud API (preferred) ───────────────────────────────
    wa_token   = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id   = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()

    if wa_token and phone_id:
        return _send_via_meta(phone, text, wa_token, phone_id)

    # ── 2. Twilio WhatsApp fallback ───────────────────────────────────────────
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    if account_sid and auth_token:
        return _send_via_twilio(phone, text, account_sid, auth_token)

    # ── 3. Simulation (no credentials) ───────────────────────────────────────
    logger.info(f"[SIMULATION] WhatsApp → {phone[:6]}XXXXXX: {text[:60]}...")
    return {"success": True, "simulated": True, "provider": "simulation"}


def _send_via_meta(phone: str, text: str, token: str, phone_number_id: str) -> Dict[str, Any]:
    """Send text message via Meta WhatsApp Cloud API v20."""
    import urllib.request
    import urllib.error

    # Normalise phone: strip leading + and spaces
    to_phone = phone.strip().lstrip("+").replace(" ", "")

    url     = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                to_phone,
        "type":              "text",
        "text":              {"preview_url": False, "body": text}
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data    = payload,
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        },
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg_id = data.get("messages", [{}])[0].get("id", "")
            logger.info(f"[META] WhatsApp → {to_phone[:6]}XXXXXX — id={msg_id}")
            return {"success": True, "message_id": msg_id, "simulated": False, "provider": "meta"}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"[META] WhatsApp HTTP {e.code}: {body[:200]}")
        # Surface a clear error — don't silently simulate on real credential failure
        return {"success": False, "error": f"Meta API {e.code}: {body[:120]}", "simulated": False, "provider": "meta"}
    except Exception as e:
        logger.error(f"[META] WhatsApp error: {e}")
        return {"success": False, "error": str(e), "simulated": False, "provider": "meta"}


def _send_via_twilio(phone: str, text: str, account_sid: str, auth_token: str) -> Dict[str, Any]:
    """Twilio fallback sender."""
    wa_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=text, from_=wa_from, to=f"whatsapp:{phone}"
        )
        logger.info(f"[TWILIO] WhatsApp → {phone[:6]}XXXXXX — SID: {msg.sid}")
        return {"success": True, "sid": msg.sid, "simulated": False, "provider": "twilio"}
    except Exception as e:
        logger.error(f"Twilio WhatsApp error: {e}")
        return {"success": False, "error": str(e), "simulated": False, "provider": "twilio"}
