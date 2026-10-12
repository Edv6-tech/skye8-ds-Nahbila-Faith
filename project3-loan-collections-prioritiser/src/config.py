"""Production Configuration Manager for Skye8 Loan Collections Prioritiser.

Loads environment variables from .env file (or system environment) safely.
Handles API credentials for MTN MoMo, Orange Money, SMS Gateways, WhatsApp,
and Credit Union Core Banking Databases (PostgreSQL / MySQL / SQLite).
"""
import os
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parents[1]

# Try importing python-dotenv if available
try:
    from dotenv import load_dotenv
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Check user home directory
        home_env = Path.home() / ".env"
        if home_env.exists():
            load_dotenv(home_env)
except ImportError:
    pass


class Config:
    """Production Environment Settings."""
    
    # -------------------------------------------------------------
    # 1. INSTITUTION & BRANCH METADATA
    # -------------------------------------------------------------
    MFI_NAME: str = os.getenv("MFI_NAME", "Ntarinkon Cooperative Credit Union (NtaCCUL)")
    BRANCH_CODE: str = os.getenv("BRANCH_CODE", "BMD-001")
    BRANCH_NAME: str = os.getenv("BRANCH_NAME", "Commercial Avenue Main Branch")
    MFI_CODE: str = os.getenv("MFI_CODE", "705001")
    
    # -------------------------------------------------------------
    # 2. MTN MOMO COLLECTION API CREDENTIALS
    # -------------------------------------------------------------
    MTN_MOMO_PRIMARY_KEY: str = os.getenv("MTN_MOMO_PRIMARY_KEY", "")
    MTN_MOMO_USER_ID: str = os.getenv("MTN_MOMO_USER_ID", "")
    MTN_MOMO_API_SECRET: str = os.getenv("MTN_MOMO_API_SECRET", "")
    MTN_MOMO_SUBSCRIPTION_KEY: str = os.getenv("MTN_MOMO_SUBSCRIPTION_KEY", "")
    MTN_MOMO_TARGET_ENV: str = os.getenv("MTN_MOMO_TARGET_ENV", "sandbox")  # "production" or "sandbox"
    MTN_MOMO_BASE_URL: str = os.getenv(
        "MTN_MOMO_BASE_URL",
        "https://proxy.momoapi.mtn.com" if MTN_MOMO_TARGET_ENV == "production" else "https://sandbox.momodeveloper.mtn.com"
    )
    
    # -------------------------------------------------------------
    # 3. ORANGE MONEY MERCHANT API CREDENTIALS
    # -------------------------------------------------------------
    ORANGE_MONEY_MERCHANT_KEY: str = os.getenv("ORANGE_MONEY_MERCHANT_KEY", "")
    ORANGE_MONEY_AUTH_TOKEN: str = os.getenv("ORANGE_MONEY_AUTH_TOKEN", "")
    ORANGE_MONEY_BASE_URL: str = os.getenv("ORANGE_MONEY_BASE_URL", "https://api.orange.com/orange-money-webpay/cm/v1")

    # -------------------------------------------------------------
    # 4. SMS GATEWAY CREDENTIALS (Twilio / Local Telco REST Gateway)
    # -------------------------------------------------------------
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "GENERIC_REST")  # "TWILIO", "GENERIC_REST", "MOCK"
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    GENERIC_SMS_API_URL: str = os.getenv("GENERIC_SMS_API_URL", "https://api.sms-gateway.cm/v1/send")
    GENERIC_SMS_API_KEY: str = os.getenv("GENERIC_SMS_API_KEY", "")

    # -------------------------------------------------------------
    # 5. WHATSAPP BUSINESS API CREDENTIALS
    # -------------------------------------------------------------
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_BASE_URL: str = os.getenv("WHATSAPP_BASE_URL", "https://graph.facebook.com/v18.0")

    # -------------------------------------------------------------
    # 6. CORE BANKING SYSTEM (CBS) DATABASE CONNECTION
    # -------------------------------------------------------------
    DB_TYPE: str = os.getenv("DB_TYPE", "sqlite")  # "sqlite", "postgres", "mysql"
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "skye8_collections_db")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_SQLITE_PATH: str = os.getenv("DB_SQLITE_PATH", str(ROOT_DIR / "data" / "collections_production.db"))

    @classmethod
    def get_status_summary(cls) -> Dict[str, Any]:
        """Check presence of live credentials and system integration health."""
        return {
            "mfi_name": cls.MFI_NAME,
            "branch": f"{cls.BRANCH_NAME} ({cls.BRANCH_CODE})",
            "mtn_momo": {
                "configured": bool(cls.MTN_MOMO_PRIMARY_KEY or cls.MTN_MOMO_SUBSCRIPTION_KEY),
                "environment": cls.MTN_MOMO_TARGET_ENV
            },
            "orange_money": {
                "configured": bool(cls.ORANGE_MONEY_MERCHANT_KEY)
            },
            "sms_gateway": {
                "configured": bool(cls.TWILIO_ACCOUNT_SID or cls.GENERIC_SMS_API_KEY),
                "provider": cls.SMS_PROVIDER
            },
            "whatsapp_business": {
                "configured": bool(cls.WHATSAPP_API_TOKEN)
            },
            "database": {
                "type": cls.DB_TYPE,
                "configured": True if cls.DB_TYPE == "sqlite" else bool(cls.DB_PASSWORD)
            }
        }
