"""
Promise-to-Pay (PTP) Tracker for Skye8 Collections Platform.

Manages officer-recorded payment promises with:
- Persistent JSON storage (zero external DB dependency)
- Automatic status transitions (PENDING → KEPT / BROKEN)
- Summary statistics for scorecard and COBAC reporting
"""
import json
import os
import uuid
import datetime
import threading
from typing import Optional, List, Dict, Any

# ── Storage path ──────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROMISES_FILE = os.path.join(_ROOT, "data", "promises.json")
_lock = threading.Lock()


def _load() -> List[Dict]:
    """Load promises from disk."""
    if not os.path.exists(_PROMISES_FILE):
        return []
    try:
        with open(_PROMISES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save(promises: List[Dict]) -> None:
    """Atomically save promises to disk."""
    os.makedirs(os.path.dirname(_PROMISES_FILE), exist_ok=True)
    tmp = _PROMISES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(promises, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _PROMISES_FILE)


# ── Public API ────────────────────────────────────────────────────────────────

def log_promise(
    account_id: int,
    officer_name: str,
    amount_fcfa: float,
    promise_date: str,          # ISO date string: "2026-10-10"
    loan_id: int = 0,
    phone: str = "",
    notes: str = "",
    channel: str = "CALL",
) -> Dict[str, Any]:
    """
    Record a new promise-to-pay.

    Returns the created promise dict with a unique promise_id.
    """
    if amount_fcfa <= 0:
        raise ValueError("Promise amount must be positive.")
    try:
        datetime.date.fromisoformat(promise_date)
    except ValueError:
        raise ValueError(f"Invalid promise_date format: '{promise_date}'. Use YYYY-MM-DD.")

    promise = {
        "promise_id":   str(uuid.uuid4())[:8].upper(),
        "account_id":   int(account_id),
        "loan_id":      int(loan_id),
        "officer_name": str(officer_name).strip() or "Officer",
        "amount_fcfa":  float(amount_fcfa),
        "promise_date": promise_date,
        "phone":        str(phone).strip(),
        "channel":      str(channel).upper(),
        "notes":        str(notes).strip(),
        "status":       "PENDING",
        "created_at":   datetime.datetime.utcnow().isoformat() + "Z",
        "resolved_at":  None,
        "resolution_note": "",
    }

    with _lock:
        promises = _load()
        promises.append(promise)
        _save(promises)

    return {"success": True, "promise": promise}


def list_promises(
    status: Optional[str] = None,
    officer_name: Optional[str] = None,
    account_id: Optional[int] = None,
    limit: int = 100,
) -> List[Dict]:
    """
    Retrieve promises with optional filters.

    Args:
        status: Filter by "PENDING", "KEPT", "BROKEN", or None for all.
        officer_name: Filter by officer (case-insensitive).
        account_id: Filter by account.
        limit: Max results to return.

    Returns:
        List of promise dicts, newest first.
    """
    with _lock:
        promises = _load()

    # Apply filters
    if status:
        promises = [p for p in promises if p.get("status", "").upper() == status.upper()]
    if officer_name:
        promises = [p for p in promises
                    if officer_name.lower() in p.get("officer_name", "").lower()]
    if account_id is not None:
        promises = [p for p in promises if p.get("account_id") == account_id]

    # Auto-resolve overdue promises
    promises = [_auto_resolve(p) for p in promises]

    # Sort newest first
    promises.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return promises[:limit]


def update_status(
    promise_id: str,
    new_status: str,
    resolution_note: str = "",
) -> Dict[str, Any]:
    """
    Update promise status to KEPT or BROKEN.

    Args:
        promise_id: The promise_id to update.
        new_status: "KEPT" or "BROKEN".
        resolution_note: Optional note on resolution.

    Returns:
        Updated promise dict.
    """
    new_status = new_status.upper()
    if new_status not in ("KEPT", "BROKEN"):
        raise ValueError("new_status must be 'KEPT' or 'BROKEN'.")

    with _lock:
        promises = _load()
        for p in promises:
            if p.get("promise_id") == promise_id.upper():
                p["status"]          = new_status
                p["resolved_at"]     = datetime.datetime.utcnow().isoformat() + "Z"
                p["resolution_note"] = str(resolution_note).strip()
                _save(promises)
                return {"success": True, "promise": p}

    raise KeyError(f"Promise '{promise_id}' not found.")


def get_summary() -> Dict[str, Any]:
    """
    Return aggregate promise statistics for the scorecard.

    Returns dict with counts, amounts, and keep rate.
    """
    with _lock:
        promises = _load()

    promises = [_auto_resolve(p) for p in promises]

    total   = len(promises)
    pending = [p for p in promises if p["status"] == "PENDING"]
    kept    = [p for p in promises if p["status"] == "KEPT"]
    broken  = [p for p in promises if p["status"] == "BROKEN"]
    resolved = len(kept) + len(broken)
    keep_rate = round(len(kept) / resolved * 100, 1) if resolved > 0 else 0.0

    return {
        "total_promises":        total,
        "pending_count":         len(pending),
        "kept_count":            len(kept),
        "broken_count":          len(broken),
        "keep_rate_pct":         keep_rate,
        "pending_amount_fcfa":   sum(p["amount_fcfa"] for p in pending),
        "kept_amount_fcfa":      sum(p["amount_fcfa"] for p in kept),
        "broken_amount_fcfa":    sum(p["amount_fcfa"] for p in broken),
        "overdue_today":         _count_overdue_today(promises),
    }


def get_reminders_due(days_ahead: int = 1) -> List[Dict]:
    """
    Return PENDING promises whose promise_date is within `days_ahead` days.
    Used by the reminder scheduler.
    """
    cutoff = (datetime.date.today() + datetime.timedelta(days=days_ahead)).isoformat()
    today  = datetime.date.today().isoformat()

    with _lock:
        promises = _load()

    return [
        p for p in promises
        if p.get("status") == "PENDING"
        and today <= p.get("promise_date", "9999-12-31") <= cutoff
    ]


# ── Private helpers ───────────────────────────────────────────────────────────

def _auto_resolve(promise: Dict) -> Dict:
    """Auto-mark PENDING promises past their due date as BROKEN."""
    if promise.get("status") == "PENDING":
        due = promise.get("promise_date", "9999-12-31")
        if due < datetime.date.today().isoformat():
            promise = dict(promise)
            promise["status"]          = "BROKEN"
            promise["resolved_at"]     = datetime.datetime.utcnow().isoformat() + "Z"
            promise["resolution_note"] = "Auto-resolved: promise date passed with no payment recorded."
            # Persist the change
            with _lock:
                promises = _load()
                for i, p in enumerate(promises):
                    if p.get("promise_id") == promise["promise_id"]:
                        promises[i] = promise
                        break
                _save(promises)
    return promise


def _count_overdue_today(promises: List[Dict]) -> int:
    today = datetime.date.today().isoformat()
    return sum(
        1 for p in promises
        if p.get("status") == "PENDING" and p.get("promise_date", "") <= today
    )
