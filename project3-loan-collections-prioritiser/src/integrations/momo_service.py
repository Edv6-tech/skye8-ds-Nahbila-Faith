"""Production MTN MoMo & Orange Money API Integration Service.

Handles live HTTP REST execution of collection requests (PIN Push) to borrower handsets
via MTN MoMo API v1.0 and Orange Money Cameroon API.
"""
import json
import logging
import urllib.request
import urllib.error
import uuid
from typing import Dict, Any
from src.config import Config

logger = logging.getLogger("MoMoService")


def trigger_momo_request_to_pay(
    amount: float,
    phone_number: str,
    account_id: int,
    loan_id: int,
    payer_message: str = "Credit Union Loan Payment"
) -> Dict[str, Any]:
    """Execute live MTN MoMo Collection API requesttopay PIN push prompt."""
    amt_int = int(round(amount))
    tx_ref = str(uuid.uuid4())
    
    # Normalize phone number format for Cameroon (+237)
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if not clean_phone.startswith("237") and len(clean_phone) == 9:
        clean_phone = f"237{clean_phone}"
        
    config_status = Config.get_status_summary()["mtn_momo"]
    
    # Check if live production / sandbox credentials exist
    if Config.MTN_MOMO_PRIMARY_KEY or Config.MTN_MOMO_SUBSCRIPTION_KEY:
        url = f"{Config.MTN_MOMO_BASE_URL}/collection/v1_0/requesttopay"
        headers = {
            "Authorization": f"Bearer {Config.MTN_MOMO_PRIMARY_KEY}",
            "X-Callback-Url": f"https://mfi-bamenda.org/api/momo/callback/{tx_ref}",
            "X-Reference-Id": tx_ref,
            "X-Target-Environment": Config.MTN_MOMO_TARGET_ENV,
            "Ocp-Apim-Subscription-Key": Config.MTN_MOMO_SUBSCRIPTION_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "amount": str(amt_int),
            "currency": "XAF",
            "externalId": f"LOAN-{loan_id}",
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": clean_phone
            },
            "payerMessage": payer_message,
            "payeeNote": f"NtaCCUL Collection Loan #{loan_id}"
        }
        
        try:
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                return {
                    "status": "ACCEPTED" if status_code in [200, 202] else "FAILED",
                    "status_code": status_code,
                    "reference_id": tx_ref,
                    "provider": "MTN_MOMO_API",
                    "mode": Config.MTN_MOMO_TARGET_ENV,
                    "phone": clean_phone,
                    "amount_fcfa": amt_int,
                    "message": "Live MTN MoMo PIN prompt sent to borrower handset."
                }
        except urllib.error.HTTPError as e:
            logger.error(f"MTN MoMo API HTTP Error: {e.code} - {e.reason}")
            return {
                "status": "ERROR",
                "status_code": e.code,
                "error": str(e.reason),
                "reference_id": tx_ref,
                "provider": "MTN_MOMO_API",
                "mode": Config.MTN_MOMO_TARGET_ENV,
                "message": f"MTN MoMo Gateway returned HTTP {e.code}"
            }
        except Exception as e:
            logger.error(f"MTN MoMo API Exception: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
                "reference_id": tx_ref,
                "provider": "MTN_MOMO_API",
                "mode": Config.MTN_MOMO_TARGET_ENV,
                "message": "Network exception communicating with MTN MoMo gateway."
            }
    else:
        # Dry-run / Sandbox Mode Protocol
        return {
            "status": "ACCEPTED",
            "status_code": 202,
            "reference_id": tx_ref,
            "provider": "MTN_MOMO_SIMULATED_PIN_PUSH",
            "mode": "SANDBOX_SIMULATION",
            "phone": clean_phone,
            "amount_fcfa": amt_int,
            "ussd_fallback": f"*126*9*{Config.MFI_CODE}*{amt_int}#",
            "message": f"[SIMULATION] MTN MoMo PIN prompt of {amt_int:,.0f} FCFA dispatched to {clean_phone}."
        }


def trigger_orange_money_payment(
    amount: float,
    phone_number: str,
    loan_id: int
) -> Dict[str, Any]:
    """Execute live Orange Money Webpay API transaction."""
    amt_int = int(round(amount))
    tx_ref = str(uuid.uuid4())
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    
    if Config.ORANGE_MONEY_MERCHANT_KEY:
        url = f"{Config.ORANGE_MONEY_BASE_URL}/webpayment"
        headers = {
            "Authorization": f"Bearer {Config.ORANGE_MONEY_AUTH_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "merchant_key": Config.ORANGE_MONEY_MERCHANT_KEY,
            "currency": "XAF",
            "order_id": f"OM-LOAN-{loan_id}-{tx_ref[:8]}",
            "amount": amt_int,
            "return_url": f"https://mfi-bamenda.org/api/orange/callback",
            "notif_url": f"https://mfi-bamenda.org/api/orange/webhook",
            "lang": "fr"
        }
        try:
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "SUCCESS",
                    "payment_url": body.get("payment_url"),
                    "reference_id": tx_ref,
                    "provider": "ORANGE_MONEY_WEBPAY",
                    "amount_fcfa": amt_int
                }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "provider": "ORANGE_MONEY_WEBPAY"}
    else:
        return {
            "status": "ACCEPTED",
            "reference_id": tx_ref,
            "provider": "ORANGE_MONEY_SIMULATED",
            "mode": "SANDBOX_SIMULATION",
            "phone": clean_phone,
            "amount_fcfa": amt_int,
            "ussd_fallback": f"*150*1*{Config.MFI_CODE}*{amt_int}#",
            "message": f"[SIMULATION] Orange Money prompt of {amt_int:,.0f} FCFA dispatched."
        }
