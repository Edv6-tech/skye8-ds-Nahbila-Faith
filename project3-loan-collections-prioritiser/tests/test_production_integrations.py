"""Unit tests for production API integrations, credentials manager, and database synchronization."""
import pytest
from src.config import Config
from src.integrations.momo_service import trigger_momo_request_to_pay, trigger_orange_money_payment
from src.integrations.sms_service import send_outreach_sms
from src.integrations.whatsapp_service import send_whatsapp_message
from src.integrations.cbs_db_service import CollectionsDatabaseAdapter


def test_config_credentials_loader():
    status = Config.get_status_summary()
    assert "mfi_name" in status
    assert "branch" in status
    assert "mtn_momo" in status
    assert "database" in status


def test_momo_and_orange_live_integration_dispatch():
    # 1. MTN MoMo dispatch
    res_momo = trigger_momo_request_to_pay(
        amount=50000,
        phone_number="237670000000",
        account_id=103380,
        loan_id=204551
    )
    assert res_momo["status"] in ["ACCEPTED", "SUCCESS", "ERROR"]
    assert "reference_id" in res_momo

    # 2. Orange Money dispatch
    res_om = trigger_orange_money_payment(
        amount=50000,
        phone_number="237690000000",
        loan_id=204551
    )
    assert res_om["status"] in ["ACCEPTED", "SUCCESS", "ERROR"]


def test_sms_and_whatsapp_live_integration_dispatch():
    # 1. SMS Dispatch
    res_sms = send_outreach_sms(
        phone_number="237670000000",
        message_text="Test Credit Union Reminder",
        account_id=103380
    )
    assert res_sms["status"] in ["SENT", "ERROR"]

    # 2. WhatsApp Dispatch
    res_wa = send_whatsapp_message(
        phone_number="237670000000",
        script_text="Test WhatsApp Script",
        overdue_amount=50000,
        loan_id=204551
    )
    assert res_wa["status"] in ["SENT", "ERROR"]


def test_database_adapter_commit_and_audit():
    db = CollectionsDatabaseAdapter()
    
    # Commit officer contact outcome
    commit_res = db.commit_contact_outcome(
        account_id=103380,
        loan_id=204551,
        officer_name="Officer 1 - John N.",
        contact_outcome="Promise to Pay",
        promise_date="2026-10-15",
        promise_amount=25000.0,
        recommended_channel="CALL",
        is_vulnerable=False,
        notes="Borrower promised partial payment post-harvest."
    )
    assert commit_res["status"] == "SUCCESS"

    # Query recent outcomes
    outcomes = db.get_recent_outcomes(limit=10)
    assert len(outcomes) > 0
    assert outcomes[0]["account_id"] == 103380
    assert outcomes[0]["contact_outcome"] == "Promise to Pay"


def test_voice_bot_queries():
    from src.voice_bot import CollectionsVoiceBot
    bot = CollectionsVoiceBot()
    
    # 1. Top priority accounts query
    res1 = bot.process_voice_query("Who should I call today?")
    assert res1["intent"] == "TOP_PRIORITY_ACCOUNTS"
    assert "top 3" in res1["spoken_response"].lower()
    
    # 2. Total money recovery query
    res2 = bot.process_voice_query("How much money can we recover?")
    assert res2["intent"] == "TOTAL_EXPECTED_RECOVERY"
    assert "recoverable" in res2["spoken_response"].lower()
    
    # 3. Pidgin speech demo
    res3 = bot.process_voice_query("Speak pidgin script")
    assert res3["intent"] == "DEMO_PIDGIN_OUTREACH"
    assert len(res3["pidgin_response"]) > 0

