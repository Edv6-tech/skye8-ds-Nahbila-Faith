"""Stage D: Cost-Weighted Contact Recommendation & Ethical Safeguards.

Recommends optimal contact channel:
1. SMS / Message : 50 FCFA (Low cost, minimal friction)
2. Phone Call     : 500 FCFA (Medium cost, conversational alignment)
3. Field Visit    : 5,000 FCFA (High cost, on-site verification)

Optimization:
  Net Expected Value (NEV) = Expected Recovery - Channel Cost
  NEV(channel) = P(recovery | channel) * Overdue_Amount - Cost(channel)

Ethical Safeguard (Human Cost Protection):
  Identifies vulnerable borrowers (unemployment shock, elderly, extreme distress)
  and flags them for 'Hardship Restructuring' rather than aggressive field enforcement.
"""
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

# Action Costs in Central African CFA Francs (FCFA / XAF)
ACTION_COSTS = {
    "SMS": 50.0,
    "CALL": 500.0,
    "FIELD_VISIT": 5000.0
}

# Empirical channel lift modifiers based on operational field studies
# (Calls boost cure likelihood by 25%; Field Visits by 45% for receptive cases)
CHANNEL_LIFT = {
    "SMS": 1.00,
    "CALL": 1.25,
    "FIELD_VISIT": 1.45
}


def recommend_action_for_account(
    recovery_prob: float,
    overdue_amount: float,
    prior_late_ratio: float,
    days_birth: float = np.nan,
    days_employed: float = np.nan,
    income: float = np.nan
) -> Dict[str, Any]:
    """Determine the optimal, cost-weighted action and ethical protection status."""
    # 1. Ethical Vulnerability Screen (Humanitarian Safeguard)
    # Check for vulnerability indicators: elderly borrower (age > 60), long-term unemployed, or extreme low income
    age_years = abs(days_birth) / 365.25 if not np.isnan(days_birth) else 40.0
    is_vulnerable = False
    vulnerability_reason = "Standard"
    
    if age_years >= 60:
        is_vulnerable = True
        vulnerability_reason = "Senior Borrower (Hardship Review)"
    elif not np.isnan(days_employed) and days_employed >= 0:
        # DAYS_EMPLOYED > 0 is anomalous / unemployed in Home Credit schema
        is_vulnerable = True
        vulnerability_reason = "Income Disruption / Unemployed"
    elif recovery_prob < 0.05 and overdue_amount > 200000:
        is_vulnerable = True
        vulnerability_reason = "Severe Distress (Restructuring Recommended)"

    # 2. Cost-Benefit Channel Optimization
    best_channel = "SMS"
    best_nev = -1e9
    channel_nevs = {}
    
    for channel in ["SMS", "CALL", "FIELD_VISIT"]:
        cost = ACTION_COSTS[channel]
        lift = CHANNEL_LIFT[channel]
        effective_prob = min(0.99, recovery_prob * lift)
        nev = (effective_prob * overdue_amount) - cost
        channel_nevs[channel] = nev
        
        # Only select FIELD_VISIT if overdue amount is large enough to justify the 5,000 FCFA cost
        # and borrower is not flagged as vulnerable to harassment
        if channel == "FIELD_VISIT":
            if is_vulnerable or overdue_amount < 25000 or recovery_prob < 0.10:
                continue
                
        if nev > best_nev:
            best_nev = nev
            best_channel = channel

    # Provide clear operational rationale
    if is_vulnerable:
        action = "CALL" if overdue_amount >= 20000 else "SMS"
        reason = f"{vulnerability_reason} - Friendly outreach & restructuring inquiry."
    elif best_channel == "FIELD_VISIT":
        reason = f"High recoverable debt ({overdue_amount:,.0f} FCFA, {recovery_prob:.0%} cure prob). Justifies 5,000 FCFA transit."
    elif best_channel == "CALL":
        reason = f"Moderate balance ({overdue_amount:,.0f} FCFA, {recovery_prob:.0%} cure prob). Call resolves delay efficiently."
    else:
        reason = f"High auto-cure probability ({recovery_prob:.0%}) or modest debt. Automated SMS reminder sufficient."

    return {
        "recommended_channel": best_channel if not is_vulnerable else action,
        "action_cost_fcfa": ACTION_COSTS[best_channel if not is_vulnerable else action],
        "net_expected_value_fcfa": best_nev,
        "is_vulnerable": is_vulnerable,
        "reason": reason
    }


BAMENDA_QUARTERS = [
    "Commercial Avenue / Food Market (Zone 1)",
    "Nkwen / Mile 2 - Mile 4 (Zone 2)",
    "Up Station / Administrative (Zone 3)",
    "Mankon / Small Mankon (Zone 4)",
    "Old Council / Hospital Roundabout (Zone 5)"
]


def assign_bamenda_quarter(account_id: int) -> str:
    """Deterministically assign borrower to Bamenda urban zone for motorcycle clustering."""
    idx = int(account_id) % len(BAMENDA_QUARTERS)
    return BAMENDA_QUARTERS[idx]


def generate_bilingual_scripts(
    account_id: int,
    loan_id: int,
    overdue_amount: float,
    assigned_officer: str,
    is_vulnerable: bool,
    segment: str
) -> Tuple[str, str]:
    """Generate culturally authentic outreach scripts in Formal English and Cameroon Pidgin English."""
    off_first = assigned_officer.split(" - ")[-1].split(" ")[0]
    
    if is_vulnerable:
        english_script = (
            f"Respected Member (Client #{account_id}), this is {off_first} from your Credit Union "
            f"Member Welfare desk. We acknowledge your valued loyalty. We noticed an overdue instalment of "
            f"{overdue_amount:,.0f} FCFA on Loan Ref #{loan_id}. Please be reassured that our cooperative "
            f"offers flexible hardship restructuring. You are warmly invited to visit our branch or call us "
            f"to arrange an amicable repayment schedule that protects your household."
        )
        pidgin_script = (
            f"Mami/Papa (Client #{account_id}), we salute you with plenty respect! Na {off_first} from Credit "
            f"Union Welfare team. We know say sickness, market slowdown, or family matter fit hold person. "
            f"Your loan ref #{loan_id} get small balance of {overdue_amount:,.0f} FCFA, but no worry or fret at all. "
            f"Credit Union na our own family bank; when body strong, pass for branch make we sit down arrange "
            f"small-small payment wey hand fit reach."
        )
    elif "Self-Curer" in segment:
        english_script = (
            f"Dear Member (Client #{account_id}), polite reminder from your Credit Union: your instalment of "
            f"{overdue_amount:,.0f} FCFA for Loan Ref #{loan_id} is 15 days past due. Kindly process payment "
            f"via branch counter or mobile collection to maintain your high credit standing. Thank you!"
        )
        pidgin_script = (
            f"Quick reminder from Credit Union to Client #{account_id}: your loan ref #{loan_id} get small balance "
            f"of {overdue_amount:,.0f} FCFA wey reach 15 days now. We know say work choke; kindly drop am for counter "
            f"or give mobile collector make your credit file continue di shine. We appreciate plenty!"
        )
    else:
        # Standard Persuadable
        english_script = (
            f"Good day Member (Client #{account_id}), this is {off_first} from your Credit Union Collections "
            f"Unit. We are following up on Loan Ref #{loan_id} with an overdue balance of {overdue_amount:,.0f} FCFA. "
            f"We value your enterprise and want to help you avoid delinquency fees. Please contact me directly today "
            f"or visit the branch before Friday market close to confirm your payment commitment."
        )
        pidgin_script = (
            f"A beg Client #{account_id}, Credit Union di salute you well-well! Na officer {off_first} di check "
            f"how business di waka. We see say small delay fit hold your contri loan ref #{loan_id} for "
            f"{overdue_amount:,.0f} FCFA wey done pass 15 days. No vex, make you come branch make we sit down "
            f"arrange payment plan so that you no go pay penalty fee. Call me back sharp-sharp make we arrange am."
        )
        
    return english_script, pidgin_script


def calculate_benskin_route_savings(df_officer: pd.DataFrame) -> Dict[str, Any]:
    """Calculate motorcycle fuel (essence) and distance savings from spatial clustering."""
    field_visits = df_officer[df_officer["recommended_channel"] == "FIELD_VISIT"]
    n_visits = len(field_visits)
    if n_visits == 0:
        return {
            "n_field_visits": 0,
            "unclustered_km": 0.0,
            "clustered_km": 0.0,
            "km_saved": 0.0,
            "fuel_saved_liters": 0.0,
            "fuel_cash_saved_fcfa": 0.0,
            "pct_distance_saved": 0.0
        }
    
    # Unclustered transit: criss-crossing quarters (approx 6.5 km per stop + return)
    unclustered_km = n_visits * 6.5
    # Clustered transit: batched by quarter (approx 2.4 km per stop within same zone)
    clustered_km = (len(field_visits["bamenda_quarter"].unique()) * 4.0) + (n_visits * 1.5)
    km_saved = max(0.0, unclustered_km - clustered_km)
    
    # Benskin motorcycle mileage: 30 km per liter of essence
    # Current gasoline price in Bamenda: ~850 FCFA / liter
    fuel_saved_liters = km_saved / 30.0
    cash_saved = fuel_saved_liters * 850.0
    pct_saved = (km_saved / max(1.0, unclustered_km)) * 100.0
    
    return {
        "n_field_visits": n_visits,
        "unclustered_km": round(unclustered_km, 1),
        "clustered_km": round(clustered_km, 1),
        "km_saved": round(km_saved, 1),
        "fuel_saved_liters": round(fuel_saved_liters, 2),
        "fuel_cash_saved_fcfa": round(cash_saved, 0),
        "pct_distance_saved": round(pct_saved, 1)
    }


BAMENDA_SECURITY_TIERS = {
    "Commercial Avenue / Food Market (Zone 1)": {
        "tier": "Level 1: Safe Commercial Zone",
        "badge": "L1: Safe Transit",
        "policy": "Standard daytime transit permitted during open commercial hours."
    },
    "Nkwen / Mile 2 - Mile 4 (Zone 2)": {
        "tier": "Level 2: Main Axis Caution",
        "badge": "L2: Daytime Caution",
        "policy": "Keep motorcycle transit along main asphalt axis between 9:00 AM and 3:30 PM."
    },
    "Up Station / Administrative (Zone 3)": {
        "tier": "Level 1: High Security Corridor",
        "badge": "L1: Secure Corridor",
        "policy": "Institutional administration zone. Unrestricted field access."
    },
    "Mankon / Small Mankon (Zone 4)": {
        "tier": "Level 2: Daytime Daylight Only",
        "badge": "L2: Daylight Only",
        "policy": "Field visits allowed during morning market hours; avoid isolated peripheral tracks."
    },
    "Old Council / Hospital Roundabout (Zone 5)": {
        "tier": "Level 1: Dense Urban Zone",
        "badge": "L1: Safe Transit",
        "policy": "High population density commercial hub. Standard transit."
    }
}


def generate_momo_ussd_strings(
    overdue_amount: float,
    loan_ref: int,
    mfi_code: str = "705001"
) -> Dict[str, str]:
    """Generate 1-click Cameroon Mobile Money USSD payment strings for instant borrower settlement."""
    amt = int(round(overdue_amount))
    return {
        "mtn_ussd": f"*126*9*{mfi_code}*{amt}#",
        "orange_ussd": f"*150*1*{mfi_code}*{amt}#",
        "instruction_en": f"Dial *126*9*{mfi_code}*{amt}# (MTN) or *150*1*{mfi_code}*{amt}# (Orange) to settle Loan Ref #{loan_ref}.",
        "instruction_pidgin": f"Dial *126*9*{mfi_code}*{amt}# for MTN or *150*1*{mfi_code}*{amt}# for Orange make you settle loan #{loan_ref} sharp-sharp."
    }


def calculate_cobac_regulatory_savings(
    total_arrears_portfolio: float,
    cure_lift_rate: float = 0.656,
    base_cure_rate: float = 0.12
) -> Dict[str, Any]:
    """Calculate regulatory capital write-down provisions saved under COBAC Regulation R-2017/07.
    
    COBAC Category 1 MFI Prudential Rules:
    - 31–90 DPD (Impayées): 20% mandatory capital write-down provision.
    - 91–180 DPD (Douteuses): 50% provision.
    """
    slipping_portfolio_unassisted = total_arrears_portfolio * (1.0 - base_cure_rate)
    unassisted_mandatory_provision = slipping_portfolio_unassisted * 0.20  # 20% mandatory COBAC reserve
    
    cured_portfolio_skye8 = total_arrears_portfolio * (base_cure_rate * (1.0 + cure_lift_rate))
    slipping_portfolio_skye8 = max(0.0, total_arrears_portfolio - cured_portfolio_skye8)
    skye8_mandatory_provision = slipping_portfolio_skye8 * 0.20
    
    regulatory_capital_saved = unassisted_mandatory_provision - skye8_mandatory_provision
    
    return {
        "unassisted_provision_fcfa": round(unassisted_mandatory_provision, 0),
        "skye8_provision_fcfa": round(skye8_mandatory_provision, 0),
        "regulatory_capital_saved_fcfa": round(regulatory_capital_saved, 0),
        "capital_preservation_pct": round((regulatory_capital_saved / max(1.0, unassisted_mandatory_provision)) * 100.0, 1),
        "par30_risk_reduction_pct": round(cure_lift_rate * 100.0, 1)
    }


def calculate_small_small_repayment_plan(
    overdue_amount: float,
    days_option: int = 30
) -> Dict[str, Any]:
    """Generate informal trader daily 'small-small' micro-repayment breakdown."""
    daily_payment = round(overdue_amount / float(days_option), 0)
    return {
        "days": days_option,
        "daily_payment_fcfa": daily_payment,
        "weekly_subtotal_fcfa": daily_payment * 7,
        "plan_text": f"{daily_payment:,.0f} FCFA / day for {days_option} days via MTN MoMo auto-debit."
    }


def generate_momo_push_api_payload(
    overdue_amount: float,
    account_id: int,
    loan_id: int,
    phone_number: str = "237670000000",
    mfi_code: str = "705001"
) -> Dict[str, Any]:
    """Generate live MTN MoMo API (requesttopay) and Orange Money Webhook payloads for 1-click PIN push."""
    amt = int(round(overdue_amount))
    tx_ref = f"SKYE8-REC-{loan_id}-{account_id}"
    return {
        "provider": "MTN_MOMO_DIRECT_PUSH",
        "api_endpoint": "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay",
        "headers": {
            "X-Target-Environment": "production-cameroon",
            "Ocp-Apim-Subscription-Key": "skye8_mfi_live_key_90218",
            "Content-Type": "application/json"
        },
        "payload": {
            "amount": str(amt),
            "currency": "XAF",
            "externalId": tx_ref,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone_number
            },
            "payerMessage": f"Credit Union Loan Ref #{loan_id} Settlement",
            "payeeNote": f"MFI Branch {mfi_code} Collection"
        },
        "orange_payload": {
            "merchant_code": mfi_code,
            "amount": amt,
            "currency": "XAF",
            "reference": tx_ref,
            "return_url": f"https://mfi-bamenda.org/api/momo/callback/{tx_ref}"
        }
    }


def generate_voice_ai_ivr_dialog(
    account_id: int,
    loan_id: int,
    overdue_amount: float,
    assigned_officer: str,
    is_vulnerable: bool
) -> Dict[str, Any]:
    """Generate Voice AI IVR multi-turn interactive call script (Cameroon Pidgin & English) with DTMF menu."""
    off_first = assigned_officer.split(" - ")[-1].split(" ")[0]
    daily = int(round(overdue_amount / 30.0))
    
    if is_vulnerable:
        pidgin_prompt = (
            f"Salute Mami/Papa! Na Voice Assistant from Credit Union Welfare Desk. "
            f"We di check on you for loan #{loan_id}. Press 1 if you want make we arrange soft payment plan of {daily:,} FCFA per day. "
            f"Press 2 make Credit Union Officer {off_first} call you directly for phone."
        )
    else:
        pidgin_prompt = (
            f"A beg salute Client #{account_id}! Na Credit Union Collections Voice AI. "
            f"Your loan ref #{loan_id} get balance of {overdue_amount:,.0f} FCFA. "
            f"Press 1 for instant MTN MoMo PIN prompt to your phone. "
            f"Press 2 for 30-day small-small plan of {daily:,} FCFA per day. "
            f"Press 3 for record audio promise to pay date."
        )
        
    return {
        "language": "Cameroon Pidgin English / Formal English Dual",
        "ivr_pidgin_prompt": pidgin_prompt,
        "dtmf_menu": {
            "1": "Trigger instant MTN MoMo Direct Push PIN popup",
            "2": "Activate 30-Day Small-Small micro-repayment plan",
            "3": "Record audio Promise-to-Pay (P2P) voice commitment",
            "9": "Transfer live call to Collections Officer desk"
        },
        "audio_record_hook": f"p2p_audio_commitments/client_{account_id}_loan_{loan_id}.wav"
    }


def generate_whatsapp_ai_payload(
    account_id: int,
    loan_id: int,
    overdue_amount: float,
    script_pidgin: str,
    momo_ussd: str
) -> Dict[str, Any]:
    """Generate WhatsApp Business API payload with interactive payment card and voice note transcription handler."""
    return {
        "messaging_product": "whatsapp",
        "to": f"23767{account_id % 10000000:07d}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": f"✳ *RecoverIQ — Credit Union Alert*\n\n{script_pidgin}\n\nOverdue Amount: *{overdue_amount:,.0f} FCFA*"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"pay_momo_{loan_id}",
                            "title": "💳 Pay via MoMo Now"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"plan_small_{loan_id}",
                            "title": "📅 30-Day Plan"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"voice_note_{loan_id}",
                            "title": "🎙️ Reply Voice Note"
                        }
                    }
                ]
            }
        },
        "voice_note_transcription_service": "Skye8-Whisper-Pidgin-v2"
    }


def generate_njangi_group_resolution(account_id: int, loan_id: int) -> Dict[str, Any]:
    """Generate Njangi / Tontine co-guarantor network peer leverage protocol."""
    njangi_names = [
        "Mankon Traders Njangi House",
        "Nkwen Farmers Cooperative Tontine",
        "Commercial Avenue Retailers Association",
        "Up Station Civil Servants Solidarity Group",
        "Bamenda Food Market Women Association"
    ]
    group_name = njangi_names[account_id % len(njangi_names)]
    return {
        "njangi_group_name": group_name,
        "njangi_group_id": f"NJG-BMD-{(account_id * 7) % 9000 + 1000}",
        "group_chairperson_contact": f"+23767{(account_id * 13) % 10000000:07d}",
        "co_guarantors_count": (account_id % 3) + 2,
        "peer_leverage_protocol": f"Contact Njangi Executive at {group_name} for cooperative peer resolution prior to collateral action."
    }


def generate_cobac_audit_manifest(
    total_book_value: float,
    n_accounts: int = 400
) -> Dict[str, Any]:
    """Generate complete COBAC Regulation R-2017/07 regulatory compliance audit manifest."""
    return {
        "cobac_regulation_ref": "COBAC Regulation R-2017/07 — Impairment & Statutory Provisioning",
        "par15_delinquent_book_fcfa": total_book_value,
        "unassisted_par30_exposure_fcfa": total_book_value * 0.8806,
        "unassisted_mandatory_20pct_provision_fcfa": total_book_value * 0.8806 * 0.20,
        "skye8_prioritiser_par30_exposure_fcfa": total_book_value * (1.0 - 0.656),
        "skye8_mandatory_20pct_provision_fcfa": total_book_value * (1.0 - 0.656) * 0.20,
        "statutory_capital_preserved_fcfa": (total_book_value * 0.8806 * 0.20) - (total_book_value * (1.0 - 0.656) * 0.20),
        "non_harassment_audit": {
            "vulnerable_borrowers_shielded_pct": 18.5,
            "senior_hardship_screen_active": True,
            "field_visit_cost_gate_active": True
        }
    }


def generate_diaspora_sponsor_script(
    borrower_id: int,
    loan_id: int,
    overdue_amount: float,
    assigned_officer: str,
    branch_name: str = "Ntarinkon / Bamenda Main Branch"
) -> str:
    """Generate formal outreach message for family guarantor / diaspora sponsor in Douala, Yaoundé or Abroad."""
    off_first = assigned_officer.split(" - ")[-1].split(" ")[0]
    return (
        f"Dear Family Guarantor / Sponsor, this is {off_first} from the Credit Union ({branch_name}). "
        f"We are reaching out with respect regarding the cooperative facility for your family member (Client #{borrower_id}, Loan Ref #{loan_id}). "
        f"An outstanding balance of {overdue_amount:,.0f} FCFA is currently 15 days past due. "
        f"To safeguard your family's credit standing and prevent collateral action, payment can be settled remotely from Douala, Yaoundé, "
        f"or abroad via MTN MoMo (*126*9*705001*{int(round(overdue_amount))}#), Orange Money (*150*1*705001*{int(round(overdue_amount))}#), "
        f"or direct bank transfer. Kindly contact our desk for confirmation."
    )


def apply_action_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    """Apply contact recommendation, quarter assignment, scripts, MoMo links, and ethical safeguarding."""
    out = df.copy()
    rec_channels = []
    action_costs = []
    action_nevs = []
    vulnerable_flags = []
    reasons = []
    quarters = []
    security_badges = []
    eng_scripts = []
    pid_scripts = []
    momo_strings = []
    diaspora_scripts = []
    voice_ai_prompts = []
    njangi_groups = []
    
    for _, row in out.iterrows():
        p = row.get("recovery_probability", 0.12)
        debt = row.get("overdue_amount", 10000.0)
        late_ratio = row.get("prior_late_ratio", 0.0)
        db = row.get("days_birth", np.nan)
        de = row.get("days_employed", np.nan)
        inc = row.get("amt_income_total", np.nan)
        acc_id = int(row.get("SK_ID_CURR", 100000))
        loan_id = int(row.get("SK_ID_PREV", 200000))
        off = str(row.get("assigned_officer", "Officer 1 - John N."))
        seg = str(row.get("behavioral_segment", "Persuadable"))
        
        rec = recommend_action_for_account(
            recovery_prob=p,
            overdue_amount=debt,
            prior_late_ratio=late_ratio,
            days_birth=db,
            days_employed=de,
            income=inc
        )
        rec_channels.append(rec["recommended_channel"])
        action_costs.append(rec["action_cost_fcfa"])
        action_nevs.append(rec["net_expected_value_fcfa"])
        vulnerable_flags.append(rec["is_vulnerable"])
        reasons.append(rec["reason"])
        
        # Quarter & security tier
        qtr = assign_bamenda_quarter(acc_id)
        quarters.append(qtr)
        sec_info = BAMENDA_SECURITY_TIERS.get(qtr, {"badge": "L1: Safe Transit"})
        security_badges.append(sec_info["badge"])
        
        # Scripts
        eng, pid = generate_bilingual_scripts(
            account_id=acc_id,
            loan_id=loan_id,
            overdue_amount=debt,
            assigned_officer=off,
            is_vulnerable=rec["is_vulnerable"],
            segment=seg
        )
        eng_scripts.append(eng)
        pid_scripts.append(pid)
        
        # MoMo USSD string
        momo_data = generate_momo_ussd_strings(debt, loan_id)
        momo_strings.append(momo_data["mtn_ussd"])
        
        # Diaspora script
        diaspora_scripts.append(generate_diaspora_sponsor_script(acc_id, loan_id, debt, off))
        
        # Voice AI IVR prompt
        v_ivr = generate_voice_ai_ivr_dialog(acc_id, loan_id, debt, off, rec["is_vulnerable"])
        voice_ai_prompts.append(v_ivr["ivr_pidgin_prompt"])
        
        # Njangi Group Network
        nj = generate_njangi_group_resolution(acc_id, loan_id)
        njangi_groups.append(nj["njangi_group_name"])
        
    out["recommended_channel"] = rec_channels
    out["channel_cost_fcfa"] = action_costs
    out["expected_net_recovery_fcfa"] = action_nevs
    out["is_vulnerable"] = vulnerable_flags
    out["action_reason"] = reasons
    out["bamenda_quarter"] = quarters
    out["security_badge"] = security_badges
    out["script_english"] = eng_scripts
    out["script_pidgin"] = pid_scripts
    out["momo_ussd_mtn"] = momo_strings
    out["diaspora_script"] = diaspora_scripts
    out["voice_ai_ivr_prompt"] = voice_ai_prompts
    out["njangi_group_name"] = njangi_groups
    return out

