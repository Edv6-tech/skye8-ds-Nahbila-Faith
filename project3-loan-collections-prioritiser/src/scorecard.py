"""
Officer Scorecard & Leaderboard for Skye8 Collections Platform.

Aggregates per-officer performance from:
- Promise-to-Pay records (promises.json)
- Contact outcomes (cbs_db_service / outcomes store)
- WhatsApp sequences (whatsapp_sequences.json)

Provides ranked leaderboard and individual KPI cards.
"""
import os
import json
import datetime
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("Scorecard")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_json(path: str) -> list:
    """Safely load a JSON file, returning [] on any error."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_promises() -> List[Dict]:
    return _load_json(os.path.join(_ROOT, "data", "promises.json"))


def _load_outcomes() -> List[Dict]:
    # Try the standard outcomes file used by cbs_db_service
    for fname in ("outcomes.json", "collections_outcomes.json"):
        data = _load_json(os.path.join(_ROOT, "data", fname))
        if data:
            return data
    return []


def _load_sequences() -> List[Dict]:
    return _load_json(os.path.join(_ROOT, "data", "whatsapp_sequences.json"))


# ── KPI Computation ───────────────────────────────────────────────────────────

def _compute_officer_kpis(officer_name: str, promises: List, outcomes: List, sequences: List) -> Dict:
    """Compute all KPIs for a single officer."""
    today = datetime.date.today()
    week_ago = (today - datetime.timedelta(days=7)).isoformat()

    # ── Promises
    my_promises = [p for p in promises if p.get("officer_name", "").lower() == officer_name.lower()]
    pending  = [p for p in my_promises if p.get("status") == "PENDING"]
    kept     = [p for p in my_promises if p.get("status") == "KEPT"]
    broken   = [p for p in my_promises if p.get("status") == "BROKEN"]
    resolved = len(kept) + len(broken)
    keep_rate = round(len(kept) / resolved * 100, 1) if resolved > 0 else 0.0

    # ── Outcomes (calls / visits this week)
    my_outcomes = [o for o in outcomes
                   if o.get("officer_name", "").lower() == officer_name.lower()]
    this_week = [o for o in my_outcomes if o.get("timestamp", "")[:10] >= week_ago]
    contacts_this_week = len(this_week)

    # ── FCFA collected (kept promises)
    fcfa_collected = sum(p.get("amount_fcfa", 0) for p in kept)
    fcfa_pending   = sum(p.get("amount_fcfa", 0) for p in pending)

    # ── WhatsApp sequences started by this officer
    my_seqs = [s for s in sequences if s.get("officer_name", "").lower() == officer_name.lower()]

    # ── Score formula (0-100)
    # 40% keep_rate + 30% contact_activity + 30% collection_amount (normalised)
    score = min(100, round(
        keep_rate * 0.40
        + min(contacts_this_week * 5, 30)   # 6 contacts/week = full 30 pts
        + min(fcfa_collected / 10_000, 30)  # 300K FCFA collected = full 30 pts
    ))

    return {
        "officer_name":         officer_name,
        "score":                score,
        "promises_total":       len(my_promises),
        "promises_kept":        len(kept),
        "promises_broken":      len(broken),
        "promises_pending":     len(pending),
        "keep_rate_pct":        keep_rate,
        "contacts_this_week":   contacts_this_week,
        "fcfa_collected":       fcfa_collected,
        "fcfa_pending":         fcfa_pending,
        "wa_sequences_started": len(my_seqs),
        "rank":                 0,  # Filled in after sorting
        "badge":                _badge(score),
    }


def _badge(score: int) -> str:
    if score >= 85: return "🏆 CHAMPION"
    if score >= 70: return "⭐ TOP PERFORMER"
    if score >= 50: return "✅ ON TRACK"
    if score >= 30: return "⚠️ NEEDS SUPPORT"
    return "🔴 CRITICAL"


# ── Public API ────────────────────────────────────────────────────────────────

def get_leaderboard(limit: int = 20) -> Dict[str, Any]:
    """
    Return officer leaderboard with KPI cards, sorted by score descending.

    Returns:
        Dict with keys: officers (list), team_summary, generated_at.
    """
    promises  = _load_promises()
    outcomes  = _load_outcomes()
    sequences = _load_sequences()

    # Discover all unique officer names across all data sources
    names = set()
    for p in promises:
        n = p.get("officer_name", "").strip()
        if n and n.lower() not in ("system", "officer", ""):
            names.add(n)
    for o in outcomes:
        n = o.get("officer_name", "").strip()
        if n and n.lower() not in ("system", "officer", ""):
            names.add(n)
    for s in sequences:
        n = s.get("officer_name", "").strip()
        if n and n.lower() not in ("system", ""):
            names.add(n)

    # Add demo officers if no data yet
    if not names:
        names = {"Amara Bello", "Grace Nkemelu", "Paul Tchouamou", "Fatime Oumarou"}

    # Compute KPIs
    officers = []
    for name in names:
        kpis = _compute_officer_kpis(name, promises, outcomes, sequences)
        officers.append(kpis)

    # If no real data, inject demo scores
    if not any(o["promises_total"] > 0 or o["contacts_this_week"] > 0 for o in officers):
        officers = _demo_leaderboard()
    else:
        # Sort and rank
        officers.sort(key=lambda o: o["score"], reverse=True)
        for i, o in enumerate(officers):
            o["rank"] = i + 1

    # Team summary
    total_collected = sum(o.get("fcfa_collected", 0) for o in officers)
    total_promises  = sum(o.get("promises_total",  0) for o in officers)
    team_keep_rate  = round(
        sum(o.get("keep_rate_pct", 0) * o.get("promises_total", 0) for o in officers)
        / max(total_promises, 1), 1
    )

    return {
        "officers":       officers[:limit],
        "total_officers": len(officers),
        "team_summary": {
            "total_fcfa_collected":   total_collected,
            "total_promises":         total_promises,
            "team_keep_rate_pct":     team_keep_rate,
            "total_contacts_week":    sum(o.get("contacts_this_week", 0) for o in officers),
        },
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def get_officer_detail(officer_name: str) -> Dict[str, Any]:
    """Return detailed KPIs for a single officer."""
    promises  = _load_promises()
    outcomes  = _load_outcomes()
    sequences = _load_sequences()
    kpis = _compute_officer_kpis(officer_name, promises, outcomes, sequences)

    # Add recent promises
    my_promises = [p for p in promises
                   if p.get("officer_name", "").lower() == officer_name.lower()]
    my_promises.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    kpis["recent_promises"] = my_promises[:10]

    return kpis


# ── Demo data ─────────────────────────────────────────────────────────────────

def _demo_leaderboard() -> List[Dict]:
    """Return realistic demo officer data for first-run / no-data state."""
    demo = [
        {
            "officer_name": "Grace Nkemelu",
            "score": 92, "rank": 1, "badge": "🏆 CHAMPION",
            "promises_total": 24, "promises_kept": 20, "promises_broken": 3, "promises_pending": 1,
            "keep_rate_pct": 87.0, "contacts_this_week": 18, "fcfa_collected": 1_240_000,
            "fcfa_pending": 85_000, "wa_sequences_started": 7,
        },
        {
            "officer_name": "Paul Tchouamou",
            "score": 78, "rank": 2, "badge": "⭐ TOP PERFORMER",
            "promises_total": 19, "promises_kept": 14, "promises_broken": 4, "promises_pending": 1,
            "keep_rate_pct": 77.8, "contacts_this_week": 14, "fcfa_collected": 890_000,
            "fcfa_pending": 120_000, "wa_sequences_started": 5,
        },
        {
            "officer_name": "Amara Bello",
            "score": 61, "rank": 3, "badge": "✅ ON TRACK",
            "promises_total": 15, "promises_kept": 9, "promises_broken": 5, "promises_pending": 1,
            "keep_rate_pct": 64.3, "contacts_this_week": 10, "fcfa_collected": 540_000,
            "fcfa_pending": 200_000, "wa_sequences_started": 3,
        },
        {
            "officer_name": "Fatime Oumarou",
            "score": 38, "rank": 4, "badge": "⚠️ NEEDS SUPPORT",
            "promises_total": 8, "promises_kept": 3, "promises_broken": 4, "promises_pending": 1,
            "keep_rate_pct": 42.9, "contacts_this_week": 5, "fcfa_collected": 180_000,
            "fcfa_pending": 310_000, "wa_sequences_started": 1,
        },
    ]
    return demo
