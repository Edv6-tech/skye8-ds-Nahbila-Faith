"""Voice AI Collections Assistant for Skye8 Loan Collections Prioritiser.

Provides natural language speech intent processing, model querying, Pidgin audio synthesis,
and interactive Voice Bot conversational logic for Credit Union officers.
"""
import json
import logging
import os
import re
from typing import Dict, Any, List

import pandas as pd
import numpy as np

from src.config import Config
from src.model import AdaptablePrioritiser, load_model
from src.contact import (
    generate_bilingual_scripts,
    generate_voice_ai_ivr_dialog,
    generate_momo_ussd_strings,
    calculate_benskin_route_savings,
    generate_cobac_audit_manifest,
)
from src.integrations.momo_service import trigger_momo_request_to_pay
from src.integrations.sms_service import send_outreach_sms

logger = logging.getLogger("VoiceBot")

# ── Intent keyword maps (broader, multi-language, Pidgin-aware) ──────────────
_INTENT_TOP_PRIORITY = [
    "who to call", "top priority", "who should i call", "first accounts",
    "call today", "best accounts", "who first", "whom to contact", "priority list",
    "highest priority", "start today", "start with", "which account", "weti account",
    "who i go call", "who i fit call", "top account", "call who", "best to call",
]
_INTENT_RECOVERY = [
    "how much money", "total cash", "expected recovery", "total value",
    "how much can we recover", "portfolio value", "total overdue", "book value",
    "money we fit recover", "how much we go get", "how much we fit make",
    "recovery forecast", "recovery total", "total balance", "total debt",
    "collect how much", "how much collectible", "recoverable",
]
_INTENT_COBAC = [
    "cobac", "regulation", "statutory reserve", "capital shield",
    "compliance", "par30", "par 30", "par 15", "par15", "provision",
    "mandatory reserve", "audit", "r-2017", "2017/07", "legal",
]
_INTENT_PIDGIN = [
    "speak pidgin", "script", "outreach call", "demo call", "pidgin script",
    "pidgin message", "voice script", "call script", "bilingual",
]
_INTENT_HELP = [
    "help", "what can you do", "what can you say", "commands", "options",
    "how do i", "what do i ask", "example", "assist", "guide",
]
_INTENT_CHANNEL = [
    "sms", "whatsapp", "call", "momo", "mobile money", "channel",
    "best way to contact", "how to contact", "reach client",
]
_INTENT_VULNERABLE = [
    "vulnerable", "hardship", "shield", "senior", "elderly", "sick",
    "medical", "hospital", "restructure", "waivers",
]


def _matches(text: str, patterns: list) -> bool:
    return any(p in text for p in patterns)


def _extract_account_id(text: str) -> int | None:
    """Extract the first 4-9 digit number from a query."""
    digits = re.findall(r"\b\d{4,9}\b", text)
    return int(digits[0]) if digits else None


class CollectionsVoiceBot:
    """Voice AI Conversational Assistant for Credit Union Collections Officers."""

    def __init__(self, book_df: pd.DataFrame = None):
        self.prioritiser = AdaptablePrioritiser()
        if book_df is not None:
            self.book_df = book_df
        else:
            try:
                self.book_df = pd.read_csv("data/processed/weekly_400_accounts.csv")
            except Exception:
                self.book_df = pd.DataFrame()

        # Cache ranked portfolio on load for fast repeated queries
        self._ranked_df: pd.DataFrame | None = None

    def _get_ranked(self) -> pd.DataFrame:
        if self._ranked_df is None or len(self._ranked_df) == 0:
            if len(self.book_df) == 0:
                return pd.DataFrame()
            try:
                self._ranked_df = self.prioritiser.rank_portfolio(self.book_df)
            except Exception:
                self._ranked_df = self.book_df.copy()
        return self._ranked_df

    def process_voice_query(self, user_text: str) -> Dict[str, Any]:
        """Process spoken or typed natural language query from officer/manager."""
        text = user_text.lower().strip()
        # Remove punctuation for matching
        clean = re.sub(r"[^\w\s]", " ", text)

        # ── Intent: App Control, Tab Navigation & Filtering ───────────────────
        action_intent = self._detect_action_intent(clean, user_text)
        if action_intent:
            return action_intent

        # ── Intent: specific account lookup (require explicit collections keyword + ID) ────
        acc_id = _extract_account_id(clean)
        _account_keywords = ("client", "account", "loan", "borrower", "check", "find", "#", "show", "open")
        if acc_id and any(kw in clean for kw in _account_keywords):
            return self._intent_account_lookup(acc_id)

        # ── Intent: top priority accounts ────────────────────────────────────
        if _matches(clean, _INTENT_TOP_PRIORITY):
            return self._intent_top_priority()

        # ── Intent: recovery forecast ─────────────────────────────────────────
        if _matches(clean, _INTENT_RECOVERY):
            return self._intent_recovery_forecast()

        # ── Intent: COBAC compliance ──────────────────────────────────────────
        if _matches(clean, _INTENT_COBAC):
            return self._intent_cobac()

        # ── Intent: channel recommendation ───────────────────────────────────
        if _matches(clean, _INTENT_CHANNEL):
            return self._intent_channel_breakdown()

        # ── Intent: vulnerable/hardship accounts ─────────────────────────────
        if _matches(clean, _INTENT_VULNERABLE):
            return self._intent_vulnerable_accounts()

        # ── Intent: pidgin script demo ────────────────────────────────────────
        if _matches(clean, _INTENT_PIDGIN):
            return self._intent_pidgin_demo()

        # ── Intent: help / commands ───────────────────────────────────────────
        if _matches(clean, _INTENT_HELP) or len(clean.strip()) < 4:
            return self._intent_help()

        # ── Fallback: partial match on any account number in text ─────────────
        if acc_id:
            return self._intent_account_lookup(acc_id)

        # ── Default fallback ──────────────────────────────────────────────────
        return self._intent_default(user_text)

    # ─────────────────────────────── APP CONTROL INTENT DETECTOR ─────────────

    def _detect_action_intent(self, clean: str, original: str) -> Dict[str, Any] | None:
        """Parse natural language commands to navigate, filter, or edit the application."""
        t = clean

        # 1. Navigation Commands
        if any(w in t for w in ["open overview", "show overview", "go to overview", "switch to overview", "portfolio overview", "call list", "today's call list"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Today's call list</b>.",
                "action": {"type": "switchTab", "tab": "overview"},
                "quick_replies": ["Show member desk", "Filter by CALL channel", "Who to call today?"]
            }
        if any(w in t for w in ["open case review", "show case review", "go to case", "switch to case", "case review", "open case", "member action desk", "action desk", "borrower profile"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Member action desk</b>.",
                "action": {"type": "switchTab", "tab": "case-review"},
                "quick_replies": ["Select Client 103380", "Show money promised", "Show call list"]
            }
        if any(w in t for w in ["open signals", "show reserves", "cobac tab", "go to reserves", "switch to signals", "statutory reserves", "branch savings", "savings & cobac", "branch savings & cobac"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Branch savings & COBAC</b>.",
                "action": {"type": "switchTab", "tab": "signals"},
                "quick_replies": ["Set COBAC portfolio to 200M", "Show field visits", "Show team ranking"]
            }
        if any(w in t for w in ["open outreach", "show outreach", "go to outreach", "switch to outreach", "momo dispatch", "benskin routes", "field visits", "field visits & momo"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Field visits & MoMo</b>.",
                "action": {"type": "switchTab", "tab": "outreach"},
                "quick_replies": ["Show money promised", "Show member desk", "Log a promise"]
            }
        if any(w in t for w in ["open promises", "show promises", "go to promises", "switch to promises", "ptp tracker", "promise to pay tracker", "money promised", "money promised tracker"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Money promised tracker</b>.",
                "action": {"type": "switchTab", "tab": "promises"},
                "quick_replies": ["Log new promise", "Filter kept promises", "Show team ranking"]
            }
        if any(w in t for w in ["open scorecard", "show scorecard", "go to scorecard", "switch to scorecard", "leaderboard", "officer leaderboard", "team ranking", "ranking"]):
            return {
                "intent": "UI_ACTION_NAVIGATE",
                "spoken_response": "Navigating to <b>Team ranking</b>.",
                "action": {"type": "switchTab", "tab": "scorecard"},
                "quick_replies": ["Show call list", "Who to call today?", "Show money promised"]
            }

        # 2. Select / Open Specific Account
        acc_match = re.search(r"(?:open|select|view|load|switch to)\s+(?:client|account|borrower|#)?\s*(\d{4,9})", t)
        if acc_match:
            acc_id = int(acc_match.group(1))
            return {
                "intent": "UI_ACTION_SELECT_ACCOUNT",
                "spoken_response": f"Loading details for <b>Client #{acc_id}</b> into the Case Review workbench.",
                "action": {"type": "loadAccount", "accountId": acc_id},
                "quick_replies": [f"Push MoMo PIN to Client #{acc_id}", "Log new promise", "Who to call today?"]
            }

        # 3. Filter Controls
        if "filter by call" in t or "channel call" in t or "show calls" in t or "only calls" in t:
            return {
                "intent": "UI_ACTION_FILTER",
                "spoken_response": "Filtering worklist by <b>Phone Call (CALL)</b> outreach channel.",
                "action": {"type": "setFilter", "filterId": "channel", "value": "CALL"},
                "quick_replies": ["Filter by SMS", "Show all channels", "Reset filters"]
            }
        if "filter by sms" in t or "channel sms" in t or "show sms" in t or "only sms" in t:
            return {
                "intent": "UI_ACTION_FILTER",
                "spoken_response": "Filtering worklist by <b>Automated SMS</b> channel.",
                "action": {"type": "setFilter", "filterId": "channel", "value": "SMS"},
                "quick_replies": ["Filter by CALL", "Show all channels", "Reset filters"]
            }
        if "reset filter" in t or "clear filter" in t or "show all channels" in t or "show all accounts" in t:
            return {
                "intent": "UI_ACTION_RESET_FILTERS",
                "spoken_response": "Resetting all filters across the entire 400-account loan book.",
                "action": {"type": "resetFilters"},
                "quick_replies": ["Filter by CALL", "Show vulnerable only", "Who to call today?"]
            }
        if "show vulnerable" in t or "filter vulnerable" in t or "senior shield filter" in t or "only hardship" in t:
            return {
                "intent": "UI_ACTION_FILTER",
                "spoken_response": "Filtering for <b>Protected / Vulnerable Hardship</b> accounts only.",
                "action": {"type": "setFilter", "filterId": "safeguard", "value": "vulnerable"},
                "quick_replies": ["Reset filters", "Show member desk", "Who to call today?"]
            }

        # 4. Interactive Dialogs & Actions (Upload CSV, Log Promise, Download Call Sheet, Bulk Campaign)
        if any(w in t for w in ["open campaign", "send messages at once", "bulk message", "send bulk", "campaign dispatch", "launch campaign", "message all", "send to all"]):
            return {
                "intent": "UI_ACTION_MODAL",
                "spoken_response": "Launching the <b>Tailored Bulk Campaign Dispatcher</b>. You can verify tailor-made messages before sending with 1-click.",
                "action": {"type": "openCampaignModal"},
                "quick_replies": ["Launch campaign now", "Filter by CALL channel", "Show call list"]
            }

        if any(w in t for w in ["open upload", "upload csv", "import csv", "upload dataset", "open csv upload"]):
            return {
                "intent": "UI_ACTION_MODAL",
                "spoken_response": "Opening the <b>CSV Dataset Upload Modal</b>. You can drop a new CSV file or paste tabular data.",
                "action": {"type": "openCSVUpload"},
                "quick_replies": ["Download call sheet", "Show call list", "Help"]
            }
        if any(w in t for w in ["download csv", "export csv", "download call sheet", "export call sheet"]):
            return {
                "intent": "UI_ACTION_EXPORT",
                "spoken_response": "Preparing and downloading your <b>RecoverIQ Call Sheet CSV</b> file now.",
                "action": {"type": "downloadCallSheet"},
                "quick_replies": ["Show call list", "Who to call today?"]
            }
        if any(w in t for w in ["log promise", "record promise", "new promise", "add promise", "log a promise"]):
            # Extract optional amount if specified
            amt_match = re.search(r"(\d{3,7})\s*(?:fcfa|cfa)?", t)
            amt = int(amt_match.group(1)) if amt_match else 25000
            acc_id = _extract_account_id(t) or 103380
            return {
                "intent": "UI_ACTION_LOG_PROMISE",
                "spoken_response": f"Opening the Promise-to-Pay form for <b>Client #{acc_id}</b> with suggested amount <b>{amt:,.0f} FCFA</b>.",
                "action": {"type": "openLogPromise", "accountId": acc_id, "amount": amt},
                "quick_replies": ["Show money promised", "Show member desk"]
            }

        # 5. Setting / Editing Sliders & Values
        cure_match = re.search(r"(?:set cure|cure threshold|min cure|minimum cure)\s+(?:to\s+)?(\d{1,3})\s*%?", t)
        if cure_match:
            val = max(0, min(100, int(cure_match.group(1))))
            return {
                "intent": "UI_ACTION_SET_VALUE",
                "spoken_response": f"Adjusting minimum cure probability threshold to <b>{val}%</b>.",
                "action": {"type": "setSlider", "sliderId": "cure", "value": val},
                "quick_replies": ["Set cure to 80%", "Reset filters", "Show member desk"]
            }

        cobac_match = re.search(r"(?:set cobac|cobac portfolio|calculate reserve for)\s+(?:to\s+)?(\d{1,4})\s*(?:m|million|000000)?", t)
        if cobac_match:
            raw_num = int(cobac_match.group(1))
            val = raw_num * 1_000_000 if raw_num < 10_000 else raw_num
            return {
                "intent": "UI_ACTION_SET_COBAC",
                "spoken_response": f"Updating COBAC portfolio simulation baseline to <b>{val:,.0f} FCFA</b>.",
                "action": {"type": "setSlider", "sliderId": "cobac-port-slider", "value": val},
                "quick_replies": ["Show reserves", "Show call list"]
            }

        # 6. Page Opening Commands ("open page ...", "open guide", "open metrics")
        if any(w in t for w in ["open guide", "open pdf", "download guide", "platform guide", "show guide"]):
            return {
                "intent": "UI_ACTION_OPEN_PAGE",
                "spoken_response": "Opening the <b>RecoverIQ Platform Guide & Metrics Reference (PDF)</b>.",
                "action": {"type": "openUrl", "url": "/guide.pdf"},
                "quick_replies": ["Show call list", "Show member desk", "Help"]
            }

        # 7. Outbound Messaging Commands (SMS, WhatsApp, MoMo PIN Push)
        if "sms" in t and any(w in t for w in ["send", "dispatch", "push", "notify"]):
            acc_id = _extract_account_id(t) or 103380
            # Look up account in portfolio
            df = self.book_df
            match = df[df["SK_ID_CURR"] == acc_id] if "SK_ID_CURR" in df.columns else pd.DataFrame()
            overdue_val = float(match.iloc[0].get("overdue_amount", 25000)) if len(match) > 0 else 25000.0
            phone_val = str(match.iloc[0].get("phone", "677123456")) if len(match) > 0 else "677123456"
            script = f"Polite reminder from your Credit Union: your instalment of {overdue_val:,.0f} FCFA for Loan #{acc_id} is past due. Kindly deposit at the counter or via MoMo to avoid fees."
            return {
                "intent": "UI_ACTION_SEND_MESSAGE",
                "spoken_response": f"Dispatching automated recovery SMS to <b>Client #{acc_id}</b> ({phone_val}) for overdue balance <b>{overdue_val:,.0f} FCFA</b>.",
                "action": {
                    "type": "sendSMS",
                    "accountId": acc_id,
                    "phone": phone_val,
                    "text": script,
                    "amount": overdue_val
                },
                "quick_replies": [f"Send WhatsApp to Client #{acc_id}", f"Push MoMo to Client #{acc_id}", "Show member desk"]
            }

        if "whatsapp" in t and any(w in t for w in ["send", "dispatch", "push", "message"]):
            acc_id = _extract_account_id(t) or 103380
            df = self.book_df
            match = df[df["SK_ID_CURR"] == acc_id] if "SK_ID_CURR" in df.columns else pd.DataFrame()
            overdue_val = float(match.iloc[0].get("overdue_amount", 25000)) if len(match) > 0 else 25000.0
            phone_val = str(match.iloc[0].get("phone", "677123456")) if len(match) > 0 else "677123456"
            text_val = f"Hello Member, friendly notice regarding Loan #{acc_id} with overdue {overdue_val:,.0f} FCFA. We offer flexible restructuring."
            return {
                "intent": "UI_ACTION_SEND_MESSAGE",
                "spoken_response": f"Sending WhatsApp repayment notice to <b>Client #{acc_id}</b> ({phone_val}).",
                "action": {
                    "type": "sendWhatsApp",
                    "accountId": acc_id,
                    "phone": phone_val,
                    "text": text_val,
                    "amount": overdue_val
                },
                "quick_replies": [f"Push MoMo to Client #{acc_id}", "Show member desk"]
            }

        if any(w in t for w in ["push momo", "send momo", "momo prompt", "ussd push", "momo pin"]):
            acc_id = _extract_account_id(t) or 103380
            df = self.book_df
            match = df[df["SK_ID_CURR"] == acc_id] if "SK_ID_CURR" in df.columns else pd.DataFrame()
            overdue_val = float(match.iloc[0].get("overdue_amount", 25000)) if len(match) > 0 else 25000.0
            phone_val = str(match.iloc[0].get("phone", "677123456")) if len(match) > 0 else "677123456"
            return {
                "intent": "UI_ACTION_SEND_MESSAGE",
                "spoken_response": f"Triggering instant MTN MoMo PIN payment prompt of <b>{overdue_val:,.0f} FCFA</b> to <b>Client #{acc_id}</b> ({phone_val}).",
                "action": {
                    "type": "sendMoMoPush",
                    "accountId": acc_id,
                    "phone": phone_val,
                    "amount": overdue_val,
                    "provider": "MTN"
                },
                "quick_replies": [f"Check Client {acc_id}", "Show promises", "Show overview"]
            }

        return None


    # ─────────────────────────────── INTENTS ────────────────────────────────

    def _intent_top_priority(self) -> Dict[str, Any]:
        ranked = self._get_ranked()
        if len(ranked) == 0:
            return self._no_data_response("TOP_PRIORITY_ACCOUNTS")
        top_n = ranked.head(5)
        recs = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (_, r) in enumerate(top_n.iterrows()):
            acc_id = int(r.get("SK_ID_CURR", 0))
            debt = float(r.get("overdue_amount", 0))
            prob = float(r.get("recovery_probability", r.get("prob", 0.88)))
            chan = str(r.get("recommended_channel", "CALL"))
            qtr = str(r.get("bamenda_quarter", r.get("quarter", "Zone")))
            recs.append({
                "id": acc_id, "debt": debt, "prob": prob,
                "chan": chan, "qtr": qtr, "medal": medals[i]
            })

        top = recs[0]
        chan_icons = {"CALL": "📞", "SMS": "💬", "WHATSAPP": "📱"}

        rows_html = "".join(
            f'<div class="bot-row">'
            f'<span class="rank">{r["medal"]}</span>'
            f'<span class="client-id">Client #{r["id"]}</span>'
            f'<span class="debt">{r["debt"]:,.0f} FCFA</span>'
            f'<span class="meta">{r["prob"]:.0%} cure &bull; '
            f'{chan_icons.get(r["chan"],"📞")} {r["chan"]}</span>'
            f'</div>'
            for r in recs
        )

        spoken = (
            f'<b>📋 Top 3 Priority Accounts</b><br><br>'
            f'{rows_html}'
            f'<div class="bot-note">'
            f'💡 Recommended action: <b>{chan_icons.get(top["chan"],"📞")} {top["chan"]} Client #{top["id"]}</b> first — '
            f'{top["prob"]:.0%} cure probability.<br>'
            f'Want me to push a <b>MoMo PIN prompt</b> to Client #{top["id"]} right now?'
            f'</div>'
        )
        pidgin = (
            f"Officer, your number one account today na Client #{top['id']} — "
            f"dem owe {top['debt']:,.0f} FCFA. Na {top['chan']} we go use. "
            f"Make I send MoMo PIN to Client #{top['id']} now?"
        )
        return {
            "intent": "TOP_PRIORITY_ACCOUNTS",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "data": recs,
            "quick_replies": [
                f"Push MoMo PIN to Client #{recs[0]['id']}",
                f"Check Client {recs[0]['id']}",
                "Show recovery total",
                "Show vulnerable accounts"
            ]
        }

    def _intent_recovery_forecast(self) -> Dict[str, Any]:
        df = self.book_df
        if len(df) == 0:
            return self._no_data_response("TOTAL_EXPECTED_RECOVERY")
        gross_col = "expected_gross_recovery_fcfa"
        prob_col = "recovery_probability"
        if gross_col in df.columns:
            total_gross = float(df[gross_col].sum())
        elif prob_col in df.columns:
            total_gross = float((df[prob_col] * df["overdue_amount"]).sum())
        else:
            total_gross = float(df["overdue_amount"].sum() * 0.72)
        total_debt = float(df["overdue_amount"].sum())
        naive_recovery = total_debt * 0.52
        lift_fcfa = max(0.0, total_gross - naive_recovery)
        pct = (total_gross / total_debt * 100) if total_debt else 0

        spoken = (
            f'<b>💰 Recovery Forecast</b><br><br>'
            f'<b>{total_gross:,.0f} FCFA</b> recoverable from <b>{len(df)} accounts</b><br>'
            f'Recovery rate: <b>{pct:.1f}%</b> of total overdue<br><br>'
            f'📈 AI lift vs baseline: <b>+{lift_fcfa:,.0f} FCFA</b> above SMS-only method'
        )
        pidgin = (
            f"For dis {len(df)} loan book, AI say we fit recover {total_gross:,.0f} FCFA! "
            f"Na {pct:.0f}% of all money owed. We dey {lift_fcfa:,.0f} FCFA pass old way!"
        )
        return {
            "intent": "TOTAL_EXPECTED_RECOVERY",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "expected_gross_fcfa": total_gross,
            "total_overdue_fcfa": total_debt,
            "lift_over_baseline_fcfa": lift_fcfa,
            "recovery_rate_pct": round(pct, 1),
            "quick_replies": ["Who to call first?", "Show COBAC compliance", "Top priority accounts"]
        }

    def _intent_account_lookup(self, target_id: int) -> Dict[str, Any]:
        df = self.book_df
        if len(df) == 0:
            return self._no_data_response("ACCOUNT_LOOKUP")
        match = df[df["SK_ID_CURR"] == target_id]
        if len(match) == 0:
            # Try fuzzy — find closest account ID
            nearest = df.iloc[(df["SK_ID_CURR"] - target_id).abs().argsort()[:1]]
            nearest_id = int(nearest.iloc[0]["SK_ID_CURR"])
            return {
                "intent": "ACCOUNT_NOT_FOUND",
                "spoken_response": (
                    f"Client #{target_id} was not found in this week's portfolio. "
                    f"The closest account I found is Client #{nearest_id}. Shall I look that up instead?"
                ),
                "pidgin_response": f"Client #{target_id} no dey for dis book. Nearest one na #{nearest_id}.",
                "quick_replies": [f"Check Client {nearest_id}", "Show top priority accounts"]
            }

        r = match.iloc[0]
        debt = float(r.get("overdue_amount", 0))
        prob = float(r.get("recovery_probability", 0.75))
        chan = str(r.get("recommended_channel", "SMS"))
        days = int(r.get("days_overdue", r.get("DAYS_CREDIT", 0)))
        is_vuln = bool(r.get("is_vulnerable", False))
        pid_script = str(r.get("script_pidgin", ""))
        vuln_text = "⚠️ Senior Hardship Shield — restructuring recommended." if is_vuln else "Standard collections protocol."

        chan_icon = {"CALL": "📞", "SMS": "💬", "WHATSAPP": "📱"}.get(chan, "📞")
        vuln_badge = "⚠️ <b>Senior Hardship Shield</b> — restructuring recommended." if is_vuln else "✅ Standard collections protocol."

        spoken = (
            f'<b>🔍 Client #{target_id}</b><br><br>'
            f'💳 Overdue balance: <b>{debt:,.0f} FCFA</b><br>'
            f'📅 Days past due: <b>{days} days</b><br>'
            f'🎯 Cure probability: <b>{prob:.0%}</b><br>'
            f'Best channel: <b>{chan_icon} {chan}</b><br><br>'
            f'{vuln_badge}'
        )
        pidgin = pid_script or f"Client #{target_id} get {debt:,.0f} FCFA balance. We go {chan} am."
        return {
            "intent": "ACCOUNT_LOOKUP",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "account_id": target_id,
            "is_vulnerable": is_vuln,
            "recommended_channel": chan,
            "overdue_fcfa": debt,
            "cure_probability": prob,
            "quick_replies": [
                f"Push MoMo PIN to Client #{target_id}",
                f"Send SMS to Client #{target_id}",
                "Show top priority accounts"
            ]
        }

    def _intent_channel_breakdown(self) -> Dict[str, Any]:
        df = self.book_df
        if len(df) == 0:
            return self._no_data_response("CHANNEL_BREAKDOWN")
        if "recommended_channel" in df.columns:
            breakdown = df["recommended_channel"].value_counts().to_dict()
        else:
            breakdown = {"CALL": len(df) // 3, "SMS": len(df) // 3, "WHATSAPP": len(df) - 2 * (len(df) // 3)}
        chan_icons = {"CALL": "📞", "SMS": "💬", "WHATSAPP": "📱"}
        rows = "".join(
            f'<div class="bot-row"><span class="rank">{chan_icons.get(k,"📡")}</span>'
            f'<span class="client-id">{k}</span><span class="debt">{v} accounts</span></div>'
            for k, v in breakdown.items()
        )
        spoken = (
            f'<b>📡 Channel Breakdown</b> — {len(df)} accounts<br><br>'
            f'{rows}'
            f'<div class="bot-note">AI routes each borrower to their highest-response channel.</div>'
        )
        pidgin = f"For dis {len(df)} account: {lines}. Each client get their best channel!"
        return {
            "intent": "CHANNEL_BREAKDOWN",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "breakdown": breakdown,
            "quick_replies": ["Top priority accounts", "Show recovery total"]
        }

    def _intent_vulnerable_accounts(self) -> Dict[str, Any]:
        df = self.book_df
        if len(df) == 0 or "is_vulnerable" not in df.columns:
            return self._no_data_response("VULNERABLE_ACCOUNTS")
        vuln_df = df[df["is_vulnerable"] == True]
        count = len(vuln_df)
        total_debt = float(vuln_df["overdue_amount"].sum()) if count else 0
        spoken = (
            f'<b>🛡️ Senior Hardship Shield</b><br><br>'
            f'<b>{count} borrowers</b> flagged for protection<br>'
            f'Combined overdue: <b>{total_debt:,.0f} FCFA</b><br><br>'
            f'<div class="bot-note">⚠️ These accounts use <b>cooperative restructuring</b> — not aggressive collection. Do not send USSD payment prompts.</div>'
        )
        pidgin = (
            f"We get {count} senior/hardship accounts. "
            f"Dem owe {total_debt:,.0f} FCFA total. No pressure dem — restructure only!"
        )
        return {
            "intent": "VULNERABLE_ACCOUNTS",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "count": count,
            "total_overdue_fcfa": total_debt,
            "quick_replies": ["Show top priority accounts", "Show COBAC compliance"]
        }

    def _intent_cobac(self) -> Dict[str, Any]:
        cobac = generate_cobac_audit_manifest(150_000_000.0)
        saved = cobac.get("statutory_capital_preserved_fcfa", 0)
        spoken = (
            f'<b>📜 COBAC Regulation R-2017/07</b><br><br>'
            f'Early PAR-15 recovery prevents loans entering <b>31-day delinquency</b>.<br>'
            f'Capital preserved: <b>{saved:,.0f} FCFA</b> in mandatory 20% statutory reserves.<br><br>'
            f'<div class="bot-note">📑 Full audit report available in the <b>COBAC tab</b>.</div>'
        )
        pidgin = f"COBAC R-2017/07 di save {saved:,.0f} FCFA for credit union capital reserve! No allow loan enter 30 day danger zone."
        return {
            "intent": "COBAC_REGULATORY_REPORT",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "cobac_data": cobac,
            "quick_replies": ["Show vulnerable accounts", "Show recovery total", "Top priority accounts"]
        }

    def _intent_pidgin_demo(self) -> Dict[str, Any]:
        df = self.book_df
        if len(df) == 0:
            return self._no_data_response("DEMO_PIDGIN_OUTREACH")
        top = self._get_ranked().iloc[0]
        acc_id = int(top.get("SK_ID_CURR", 0))
        debt = float(top.get("overdue_amount", 0))
        pid_script = str(top.get("script_pidgin", f"Credit Union di salute you! You get {debt:,.0f} FCFA balance. Abeg make we settle am."))
        return {
            "intent": "DEMO_PIDGIN_OUTREACH",
            "spoken_response": f"Here is the Pidgin outreach script for Client #{acc_id}: {pid_script}",
            "pidgin_response": pid_script,
            "account_id": acc_id,
            "quick_replies": [f"Push MoMo PIN to Client #{acc_id}", "Top priority accounts"]
        }

    def _intent_help(self) -> Dict[str, Any]:
        spoken = (
            '<b>❓ What can I help you with?</b><br><br>'
            '📋 <b>Who should I call today?</b> — Top priority accounts<br>'
            '💰 <b>How much can we recover?</b> — Portfolio forecast<br>'
            '🔍 <b>Check Client 103380</b> — Individual account details<br>'
            '📡 <b>Channel breakdown</b> — SMS vs Call vs WhatsApp<br>'
            '🛡️ <b>Show vulnerable accounts</b> — Senior Hardship Shield<br>'
            '📜 <b>COBAC compliance</b> — Regulatory capital report<br>'
            '🌍 <b>Speak pidgin script</b> — Demo outreach script'
        )
        pidgin = "Ask me: 'Who to call?', 'How much we fit recover?', 'Check Client 103380', or 'COBAC report'!"
        return {
            "intent": "HELP",
            "spoken_response": spoken,
            "pidgin_response": pidgin,
            "quick_replies": [
                "Who to call today?",
                "How much can we recover?",
                "Show vulnerable accounts",
                "COBAC compliance"
            ]
        }

    def _intent_default(self, original: str) -> Dict[str, Any]:
        """Try Gemini LLM first; fall back to a helpful static response."""
        gemini_resp = self._gemini_query(original)
        if gemini_resp:
            return gemini_resp
        # Static fallback if Gemini unavailable
        return {
            "intent": "GENERAL_ASSISTANCE",
            "spoken_response": (
                f"I did not quite understand \"{original}\". "
                "Try asking: \"Who to call today?\", \"How much can we recover?\", "
                "or \"Check Client 103380\". Type \"help\" for a full list."
            ),
            "pidgin_response": f"I no understand \"{original}\". Try: \"Who to call?\", \"How much we fit recover?\", or \"Check Client 103380\".",
            "quick_replies": [
                "Who to call today?",
                "How much can we recover?",
                "Show vulnerable accounts",
                "COBAC compliance",
                "Help"
            ]
        }

    def _gemini_query(self, question: str) -> Dict[str, Any] | None:
        """Send any question to Gemini — handles maths, general knowledge, collections, anything."""
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None

        # Build portfolio context
        df = self.book_df
        total_accounts = len(df)
        total_overdue  = float(df["overdue_amount"].sum()) if total_accounts else 0.0
        top_summary    = ""
        if total_accounts:
            try:
                ranked = self._get_ranked()
                top5   = ranked.head(5)
                top_summary = "; ".join(
                    f"Client #{int(r.get('SK_ID_CURR',0))} — {float(r.get('overdue_amount',0)):,.0f} FCFA "
                    f"({float(r.get('recovery_probability', r.get('prob', 0))):.0%} cure, {r.get('recommended_channel','?')})"
                    for _, r in top5.iterrows()
                )
            except Exception:
                top_summary = "(ranking unavailable)"

        system_prompt = (
            "You are RecoverIQ, a smart all-purpose AI assistant embedded in a loan collections "
            "platform for a COBAC-regulated credit union in Bamenda, Cameroon. "
            "Your name is RecoverIQ (or RecoverIQ AI Assistant). Never refer to yourself as Skye8. "
            "You help collections officers with ANYTHING they ask — maths, calculations, "
            "general knowledge, translations, advice, loans, COBAC regulations, and portfolio analysis. "
            "NEVER refuse to answer or say you can only answer collections questions. "
            "Rules:\n"
            "- For CALCULATIONS: show the working clearly step by step, then state the answer in bold.\n"
            "- For LISTS: use bullet points (- item).\n"
            "- For COLLECTIONS questions: be practical and empathetic.\n"
            "- Keep answers clear and well-structured.\n"
            f"Portfolio context: {total_accounts} delinquent accounts, "
            f"{total_overdue:,.0f} FCFA total overdue. Top 5: {top_summary}"
        )

        try:
            from google import genai
            client   = genai.Client(api_key=api_key)
            chat     = client.chats.create(model="gemini-2.5-flash")
            response = chat.send_message(f"{system_prompt}\n\nOfficer: {question}")
            raw      = response.text.strip()
            logger.info(f"[GEMINI] Query: '{question[:60]}' → {len(raw)} chars")

            # ── Convert Gemini markdown → HTML ───────────────────────────────
            html = raw
            # **bold** → <b>bold</b>
            html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
            # *italic* → <i>italic</i>  (only single stars remaining)
            html = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", html)
            # `code` → <code>code</code>
            html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

            out_lines = []
            for line in html.split("\n"):
                s = line.strip()
                if re.match(r"^[-*•]\s+", s):          # bullet
                    out_lines.append(f'<span style="margin-left:4px">&bull;&nbsp;{s[2:].strip()}</span>')
                elif re.match(r"^\d+\.\s+", s):         # numbered list
                    out_lines.append(f'<span style="margin-left:4px">{s}</span>')
                elif s == "":
                    out_lines.append("")
                else:
                    out_lines.append(s)

            html = "<br>".join(out_lines)
            html = re.sub(r"(<br>\s*){3,}", "<br><br>", html)   # max 2 blank lines

            return {
                "intent":          "GEMINI_RESPONSE",
                "spoken_response": html,
                "pidgin_response": raw,          # plain text for TTS
                "source":          "gemini-2.5-flash",
                "quick_replies":   [
                    "Who to call today?",
                    "How much can we recover?",
                    "Show COBAC compliance",
                    "Help"
                ]
            }
        except Exception as e:
            logger.warning(f"[GEMINI] API error: {e}")
            return None


    def _no_data_response(self, intent: str) -> Dict[str, Any]:
        return {
            "intent": intent,
            "spoken_response": "Portfolio data has not been loaded yet. Please run the pipeline first to generate account rankings.",
            "pidgin_response": "Data no load yet. Run pipeline first make we get accounts.",
            "quick_replies": []
        }
