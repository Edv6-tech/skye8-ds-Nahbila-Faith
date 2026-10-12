"""Production SMS Dispatch Integration Service.

Supports live SMS dispatch via Twilio API or Cameroon Telco REST SMS Gateways.
Falls back cleanly to sandbox/simulation logging when credentials are unset.
"""
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any
from src.config import Config

logger = logging.getLogger("SMSService")


def send_outreach_sms(
    phone_number: str,
    message_text: str,
    account_id: int
) -> Dict[str, Any]:
    """Dispatch SMS message via Twilio or Generic Telco REST SMS Gateway."""
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()
    if not clean_phone.startswith("237") and len(clean_phone) == 9:
        clean_phone = f"237{clean_phone}"

    # Option A: Twilio API Integration
    if Config.SMS_PROVIDER == "TWILIO" and Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{Config.TWILIO_ACCOUNT_SID}/Messages.json"
        data = urllib.parse.urlencode({
            "To": f"+{clean_phone}",
            "From": Config.TWILIO_PHONE_NUMBER,
            "Body": message_text
        }).encode("utf-8")
        
        # Basic auth encoding for Twilio
        import base64
        auth_str = f"{Config.TWILIO_ACCOUNT_SID}:{Config.TWILIO_AUTH_TOKEN}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "SENT",
                    "sid": body.get("sid"),
                    "provider": "TWILIO_SMS",
                    "phone": clean_phone,
                    "message": "Live SMS dispatched via Twilio Gateway."
                }
        except Exception as e:
            logger.error(f"Twilio SMS Error: {e}")
            return {"status": "ERROR", "error": str(e), "provider": "TWILIO_SMS"}

    # Option B: Generic Cameroon Telco REST Gateway Integration
    elif Config.GENERIC_SMS_API_KEY and Config.GENERIC_SMS_API_URL:
        payload = {
            "api_key": Config.GENERIC_SMS_API_KEY,
            "to": clean_phone,
            "message": message_text,
            "sender_id": Config.MFI_NAME[:11]
        }
        try:
            req = urllib.request.Request(
                Config.GENERIC_SMS_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {
                    "status": "SENT",
                    "provider": "CAMEROON_TELCO_SMS_GATEWAY",
                    "phone": clean_phone,
                    "message": "Live SMS dispatched via Local Telco SMS Gateway."
                }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "provider": "CAMEROON_TELCO_SMS_GATEWAY"}

    # Option C: Sandbox / Simulation Protocol
    else:
        return {
            "status": "SENT",
            "provider": "SIMULATED_SMS_DISPATCH",
            "mode": "SANDBOX_SIMULATION",
            "phone": clean_phone,
            "text": message_text,
            "message": f"[SIMULATION] SMS sent to {clean_phone}: '{message_text[:60]}...'"
        }
