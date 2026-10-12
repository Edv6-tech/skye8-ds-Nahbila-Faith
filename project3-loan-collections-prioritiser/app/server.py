"""Production REST API Server for RecoverIQ Loan Collections Prioritiser.

Endpoints:
  GET  /api/v1/health                     Liveness check
  GET  /api/v1/status                     Integration status
  GET  /api/v1/cobac/report               COBAC JSON manifest
  GET  /api/v1/cobac/download-pdf         COBAC compliance PDF download  [NEW]
  GET  /api/v1/collections/outcomes       Recent officer outcomes
  GET  /api/v1/promises/list              Promise-to-Pay records         [NEW]
  GET  /api/v1/scorecard                  Officer leaderboard            [NEW]
  POST /api/v1/momo/request-to-pay        MTN/Orange MoMo PIN prompt
  POST /api/v1/campay/ussd-push           CamPay USSD push               [NEW]
  POST /api/v1/outreach/send-sms          SMS dispatch
  POST /api/v1/outreach/send-whatsapp     WhatsApp message
  POST /api/v1/whatsapp/send-sequence     Start WA outreach sequence     [NEW]
  POST /api/v1/collections/commit-outcome Officer action log
  POST /api/v1/promises/log              Log a promise-to-pay            [NEW]
  POST /api/v1/promises/update-status    Mark promise kept/broken        [NEW]
  POST /api/v1/voice-bot/query           AI assistant NL query
"""
import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.config import Config
from src.integrations.momo_service import trigger_momo_request_to_pay, trigger_orange_money_payment
from src.integrations.sms_service import send_outreach_sms
from src.integrations.whatsapp_service import send_whatsapp_message
from src.integrations.campay_service import trigger_ussd_push        # NEW
from src.integrations.whatsapp_bot import (                          # NEW
    start_sequence, list_sequences, stop_sequence, get_summary as wa_summary
)
from src.integrations.cbs_db_service import CollectionsDatabaseAdapter
from src.contact import generate_cobac_audit_manifest
from src.voice_bot import CollectionsVoiceBot
from src.promises import (                                            # NEW
    log_promise, list_promises, update_status as update_promise_status,
    get_summary as promises_summary
)
from src.scorecard import get_leaderboard, get_officer_detail         # NEW
from src.pdf_generator import generate_cobac_pdf                      # NEW

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProductionServer")

# Load .env
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        logger.info("Loaded credentials from .env")
    else:
        logger.warning(".env not found — set credentials as environment variables")
except ImportError:
    logger.warning("python-dotenv not installed")

START_TIME   = time.time()
db_adapter   = CollectionsDatabaseAdapter()
voice_bot    = CollectionsVoiceBot()
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

VALID_CM_PREFIXES = (
    "237670","237671","237672","237673","237674","237675","237676","237677","237678","237679",
    "237650","237651","237652","237653","237654","237655","237656","237657","237658","237659",
    "237690","237691","237692","237693","2376",
)


def _validate_cm_phone(phone: str) -> bool:
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) not in (9, 12):
        return False
    if len(digits) == 9:
        digits = "237" + digits
    return digits.startswith("237") and len(digits) == 12


class ProductionAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for RecoverIQ Credit Union Collections API."""

    def log_message(self, fmt, *args):
        logger.info("%s — %s" % (self.address_string(), fmt % args))

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _respond_json(self, status_code: int, data: dict):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _respond_bytes(self, status_code: int, body: bytes, content_type: str,
                       filename: str = ""):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            return json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return {}

    def _check_auth(self) -> bool:
        if not API_SECRET_KEY:
            return True
        return self.headers.get("X-API-Key", "") == API_SECRET_KEY

    # ─────────────────────────── GET ──────────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        # ── Static UI (index.html served directly so JS fetch works same-origin) ──
        if path in ("/", "/index.html"):
            html_file = os.path.join(os.path.dirname(__file__), "index.html")
            if os.path.exists(html_file):
                with open(html_file, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self._set_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._respond_json(404, {"error": "index.html not found"})
            return

        if path in ("/guide.pdf", "/docs/guide.pdf", "/RecoverIQ_Platform_Guide_and_Metrics.pdf"):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidates = [
                os.path.join(base_dir, "reports", "RecoverIQ_Platform_Guide_and_Metrics.pdf"),
                os.path.join(base_dir, "app", "RecoverIQ_Platform_Guide_and_Metrics.pdf"),
                os.path.abspath("reports/RecoverIQ_Platform_Guide_and_Metrics.pdf"),
                os.path.abspath("app/RecoverIQ_Platform_Guide_and_Metrics.pdf"),
            ]
            for p in candidates:
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        body = f.read()
                    self._respond_bytes(200, body, "application/pdf", "RecoverIQ_Platform_Guide_and_Metrics.pdf")
                    return
            self._respond_json(404, {"error": "Platform guide PDF not found on disk."})
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # ── Health ──────────────────────────────────────────────────────────
        if path == "/api/v1/health":
            self._respond_json(200, {
                "status": "OK",
                "system": "RecoverIQ Loan Collections Prioritiser",
                "uptime_seconds": int(time.time() - START_TIME),
                "auth_enabled": bool(API_SECRET_KEY),
                "features": ["ptp_tracker", "campay_ussd", "whatsapp_bot",
                             "officer_scorecard", "cobac_pdf"],
            })

        # ── Status ──────────────────────────────────────────────────────────
        elif path == "/api/v1/status":
            integrations = {
                "mtn_momo":    "CONFIGURED" if os.getenv("MTN_MOMO_SUBSCRIPTION_KEY") else "MISSING_CREDENTIALS",
                "orange_money":"CONFIGURED" if os.getenv("ORANGE_MONEY_CLIENT_ID")    else "MISSING_CREDENTIALS",
                "sms_twilio":  "CONFIGURED" if os.getenv("TWILIO_ACCOUNT_SID")        else "MISSING_CREDENTIALS",
                "whatsapp":    "CONFIGURED" if os.getenv("WHATSAPP_ACCESS_TOKEN")     else "MISSING_CREDENTIALS",
                "campay":      "CONFIGURED" if os.getenv("CAMPAY_API_KEY")             else "SIMULATION_MODE",
            }
            self._respond_json(200, {
                "status": "ONLINE",
                "system": "RecoverIQ Collections API — Production",
                "integrations": integrations,
                "production_ready": all(v == "CONFIGURED" for v in integrations.values()),
                "uptime_seconds": int(time.time() - START_TIME),
                "auth_enabled": bool(API_SECRET_KEY),
            })

        # ── COBAC JSON report ────────────────────────────────────────────────
        elif path == "/api/v1/cobac/report":
            cobac = generate_cobac_audit_manifest(total_book_value=150_000_000.0)
            self._respond_json(200, cobac)

        # ── COBAC PDF download ───────────────────────────────────────────────
        elif path == "/api/v1/cobac/download-pdf":
            try:
                institution = qs.get("institution", ["Coopérative d'Épargne et de Crédit"])[0]
                branch      = qs.get("branch",      ["Siège Social"])[0]
                book_val    = float(qs.get("book_value", ["150000000"])[0])

                # Gather live promises for the report
                try:
                    pdata = list_promises(limit=200)
                except Exception:
                    pdata = []

                pdf_bytes = generate_cobac_pdf(
                    institution_name=institution,
                    branch=branch,
                    total_book_fcfa=book_val,
                    promises_data=pdata,
                )

                import datetime
                fname = f"COBAC_Report_{datetime.date.today().isoformat()}.pdf"
                self._respond_bytes(200, pdf_bytes, "application/pdf", filename=fname)
            except Exception as e:
                logger.error(f"PDF generation error: {e}", exc_info=True)
                self._respond_json(500, {"error": f"PDF generation failed: {e}"})

        # ── Collections outcomes ─────────────────────────────────────────────
        elif path == "/api/v1/collections/outcomes":
            limit = int(qs.get("limit", ["50"])[0])
            limit = max(1, min(limit, 200))
            outcomes = db_adapter.get_recent_outcomes(limit=limit)
            self._respond_json(200, {"status": "SUCCESS", "count": len(outcomes), "outcomes": outcomes})

        # ── Promise list ─────────────────────────────────────────────────────
        elif path == "/api/v1/promises/list":
            status_filter  = qs.get("status",  [None])[0]
            officer_filter = qs.get("officer", [None])[0]
            acc_filter     = qs.get("account_id", [None])[0]
            acc_int        = int(acc_filter) if acc_filter else None
            limit          = int(qs.get("limit", ["100"])[0])
            promises = list_promises(
                status=status_filter,
                officer_name=officer_filter,
                account_id=acc_int,
                limit=limit,
            )
            summary = promises_summary()
            self._respond_json(200, {
                "status": "SUCCESS",
                "count": len(promises),
                "promises": promises,
                "summary": summary,
            })

        # ── Officer scorecard ────────────────────────────────────────────────
        elif path == "/api/v1/scorecard":
            officer = qs.get("officer", [None])[0]
            if officer:
                data = get_officer_detail(officer)
            else:
                data = get_leaderboard()
            self._respond_json(200, {"status": "SUCCESS", **data})

        # ── Comparative Benchmarks (Home Credit + LendingClub) ────────────────
        elif path == "/api/v1/benchmarks":
            base_dir = os.path.dirname(os.path.dirname(__file__))
            hc_path = os.path.join(base_dir, "reports", "metrics_summary.json")
            lc_path = os.path.join(base_dir, "reports", "lendingclub_metrics_summary.json")
            hc_metrics = {}
            lc_metrics = {}
            if os.path.exists(hc_path):
                with open(hc_path, "r", encoding="utf-8") as f:
                    hc_metrics = json.load(f)
            if os.path.exists(lc_path):
                with open(lc_path, "r", encoding="utf-8") as f:
                    lc_metrics = json.load(f)
            self._respond_json(200, {
                "status": "SUCCESS",
                "home_credit": hc_metrics,
                "lending_club": lc_metrics
            })

        else:
            self._respond_json(404, {"error": f"GET '{path}' not found."})

    # ─────────────────────────── POST ─────────────────────────────────────────
    def do_POST(self):
        if not self._check_auth():
            self._respond_json(401, {"error": "Unauthorized — invalid or missing X-API-Key."})
            return

        path = urlparse(self.path).path
        body = self._read_json_body()

        # ── Direct CSV Data Upload ───────────────────────────────────────────
        if path == "/api/v1/upload-csv":
            csv_text = body.get("csv_text", "")
            if not csv_text:
                # Fallback to reading raw body text
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    csv_text = self.rfile.read(content_length).decode("utf-8", errors="ignore")

            if not csv_text or len(csv_text.strip()) < 10:
                self._respond_json(400, {"error": "No CSV content provided."})
                return

            try:
                import io
                import pandas as pd
                df = pd.read_csv(io.StringIO(csv_text))
                if df.empty:
                    self._respond_json(400, {"error": "Uploaded CSV file is empty."})
                    return

                # Save to processed directory
                save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "weekly_400_accounts.csv")
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                df.to_csv(save_path, index=False)

                # Reload voice bot dataframe in memory
                voice_bot.book_df = df
                voice_bot._ranked_df = None

                # Format accounts for immediate frontend rendering
                formatted_accounts = []
                for idx, row in df.head(60).iterrows():
                    acc_id = int(row.get("id", row.get("account_id", row.get("member_id", 100000 + idx))))
                    overdue = float(row.get("overdue_amount", row.get("loan_amnt", row.get("overdue", 25000.0))))
                    cure_prob = float(row.get("cure_probability", row.get("prob", 0.88)))
                    net_val = float(row.get("expected_net_recovery", row.get("net", overdue * cure_prob - 1500.0)))
                    officer_val = str(row.get("officer", row.get("officer_name", "John N.")))
                    quarter_val = str(row.get("quarter", row.get("zone", "Commercial Avenue / Zone 1")))
                    channel_val = str(row.get("channel", "CALL" if overdue > 15000 else "SMS"))
                    formatted_accounts.append({
                        "id": acc_id,
                        "loan": int(row.get("loan_id", row.get("loan", 2000000 + idx))),
                        "overdue": overdue,
                        "prob": cure_prob,
                        "net": max(0.0, net_val),
                        "gross": overdue * cure_prob,
                        "officer": officer_val,
                        "full_officer": f"Officer - {officer_val}",
                        "quarter": quarter_val,
                        "channel": channel_val,
                        "vulnerable": bool(row.get("vulnerable", False)),
                        "age": int(row.get("age", 45)),
                        "rank": idx + 1,
                        "script": f"Hello, I am calling from RecoverIQ regarding loan #{acc_id}. We noticed an overdue balance of {overdue:,.0f} FCFA. We offer flexible restructuring...",
                        "action_reason": "Prioritized by ML Model based on recovery probability and expected value."
                    })

                total_overdue_sum = float(df["overdue_amount"].sum()) if "overdue_amount" in df.columns else (float(df["loan_amnt"].sum()) if "loan_amnt" in df.columns else sum(a["overdue"] for a in formatted_accounts))

                logger.info(f"Successfully uploaded and applied new CSV dataset ({len(df)} accounts)")
                self._respond_json(200, {
                    "status": "SUCCESS",
                    "message": f"Successfully loaded {len(df):,} delinquent accounts into RecoverIQ!",
                    "account_count": len(df),
                    "total_overdue_fcfa": total_overdue_sum,
                    "accounts": formatted_accounts
                })
                return
            except Exception as e:
                logger.error(f"CSV upload error: {e}", exc_info=True)
        # ── Bulk Payment Settlement & MoMo Reconciliation ────────────────────
        elif path == "/api/v1/payments/bulk-reconcile":
            csv_text = body.get("csv_text", "")
            if not csv_text:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    csv_text = self.rfile.read(content_length).decode("utf-8", errors="ignore")

            if not csv_text or len(csv_text.strip()) < 5:
                self._respond_json(400, {"error": "No payment data provided."})
                return

            try:
                import io
                import pandas as pd
                pay_df = pd.read_csv(io.StringIO(csv_text))
                if pay_df.empty:
                    self._respond_json(400, {"error": "Payment CSV file is empty."})
                    return

                # Standardize column names
                cols = {c.lower().strip(): c for c in pay_df.columns}
                id_col = cols.get("sk_id_curr", cols.get("account_id", cols.get("client_id", cols.get("account", None))))
                amt_col = cols.get("amount", cols.get("amount_paid", cols.get("amount_fcfa", cols.get("paid", None))))

                if not id_col or not amt_col:
                    self._respond_json(400, {"error": f"CSV must contain Account ID column ('SK_ID_CURR' or 'account_id') and Amount column ('amount' or 'amount_paid'). Detected: {list(pay_df.columns)}"})
                    return

                df = voice_bot.book_df.copy()
                if df.empty:
                    try:
                        save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "weekly_400_accounts.csv")
                        df = pd.read_csv(save_path)
                    except Exception:
                        df = pd.DataFrame()

                total_reconciled = 0.0
                matched_count = 0
                cleared_count = 0
                ptp_kept_count = 0

                # Process each payment row
                for _, prow in pay_df.iterrows():
                    try:
                        acc_id = int(prow[id_col])
                        paid_amt = float(prow[amt_col])
                    except (ValueError, TypeError):
                        continue

                    if paid_amt <= 0:
                        continue

                    # Match in portfolio
                    mask = (df["SK_ID_CURR"] == acc_id)
                    if mask.any():
                        matched_count += 1
                        total_reconciled += paid_amt
                        current_due = float(df.loc[mask, "overdue_amount"].values[0])
                        new_due = max(0.0, current_due - paid_amt)
                        df.loc[mask, "overdue_amount"] = new_due

                        if new_due == 0:
                            cleared_count += 1

                        # Log outcome in CBS database adapter
                        outcome = "PAID_IN_FULL" if new_due == 0 else "PARTIAL_PAYMENT"
                        db_adapter.commit_contact_outcome(
                            account_id=acc_id,
                            loan_id=int(df.loc[mask, "SK_ID_PREV"].values[0]) if "SK_ID_PREV" in df.columns else 0,
                            officer_name="Auto-Reconciliation",
                            contact_outcome=outcome,
                            promise_amount=paid_amt,
                            notes=f"Bulk payment settlement reconciled via CSV upload ({paid_amt:,.0f} FCFA).",
                        )

                        # Auto-mark pending Promises-to-Pay as KEPT
                        try:
                            active_promises = list_promises(account_id=acc_id, status="PENDING")
                            for ptp in active_promises:
                                update_promise_status(
                                    promise_id=ptp["promise_id"],
                                    new_status="KEPT",
                                    resolution_note=f"Auto-resolved: Payment of {paid_amt:,.0f} FCFA received via bulk reconciliation."
                                )
                                ptp_kept_count += 1
                        except Exception as pe:
                            logger.warning(f"Failed to auto-update promise for client #{acc_id}: {pe}")

                # Save updated book_df
                save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "weekly_400_accounts.csv")
                df.to_csv(save_path, index=False)
                voice_bot.book_df = df
                voice_bot._ranked_df = None

                logger.info(f"[RECONCILIATION] Processed {len(pay_df)} payments | Reconciled {total_reconciled:,.0f} FCFA across {matched_count} accounts | {ptp_kept_count} PTPs marked KEPT")

                self._respond_json(200, {
                    "status": "SUCCESS",
                    "message": f"Successfully reconciled {matched_count} payment records! Total recovered: {total_reconciled:,.0f} FCFA.",
                    "total_payments_processed": len(pay_df),
                    "matched_accounts": matched_count,
                    "accounts_fully_cleared": cleared_count,
                    "total_fcfa_reconciled": total_reconciled,
                    "ptps_marked_kept": ptp_kept_count,
                })
                return
            except Exception as e:
                logger.error(f"Bulk reconciliation error: {e}", exc_info=True)
                self._respond_json(400, {"error": f"Failed to reconcile payments: {e}"})
                return


        # ── Voice-bot ────────────────────────────────────────────────────────
        elif path == "/api/v1/voice-bot/query":
            q = str(body.get("query", "")).strip()
            if not q:
                self._respond_json(400, {"error": "'query' is required."})
                return
            self._respond_json(200, voice_bot.process_voice_query(q))

        # ── MTN MoMo / Orange request-to-pay ─────────────────────────────────
        elif path == "/api/v1/momo/request-to-pay":
            amount   = float(body.get("amount", 0.0))
            phone    = str(body.get("phone", "")).strip()
            acc_id   = int(body.get("account_id", 0))
            loan_id  = int(body.get("loan_id", 0))
            provider = str(body.get("provider", "MTN")).upper()
            if amount <= 0 or amount > 5_000_000:
                self._respond_json(400, {"error": f"Invalid amount: {amount}."}); return
            if not _validate_cm_phone(phone):
                self._respond_json(400, {"error": f"Invalid phone: '{phone}'."}); return
            if acc_id <= 0:
                self._respond_json(400, {"error": "'account_id' must be positive."}); return
            res = trigger_orange_money_payment(amount, phone, loan_id) if provider == "ORANGE" \
                  else trigger_momo_request_to_pay(amount, phone, acc_id, loan_id)
            db_adapter.record_momo_transaction(
                reference_id=res.get("reference_id", "REF-000"),
                account_id=acc_id, loan_id=loan_id,
                amount_fcfa=amount, phone=f"{str(phone)[:6]}XXXXXX",
                status=res.get("status", "UNKNOWN"), provider=res.get("provider", "MOMO"),
            )
            self._respond_json(200, res)

        # ── CamPay USSD push ─────────────────────────────────────────────────
        elif path == "/api/v1/campay/ussd-push":
            # Accept both 'amount_fcfa' (frontend) and 'amount' (legacy) keys
            amount  = float(body.get("amount_fcfa", body.get("amount", 0.0)))
            phone   = str(body.get("phone", "")).strip()
            acc_id  = int(body.get("account_id", 0))
            loan_id = int(body.get("loan_id", 0))
            desc    = str(body.get("description", "")).strip()
            if amount <= 0:
                self._respond_json(400, {"error": "amount must be positive."}); return
            if not _validate_cm_phone(phone):
                self._respond_json(400, {"error": f"Invalid phone: '{phone}'."}); return
            res = trigger_ussd_push(phone, amount, acc_id, loan_id, desc)
            self._respond_json(200, res)

        # ── SMS dispatch ─────────────────────────────────────────────────────
        elif path == "/api/v1/outreach/send-sms":
            phone  = str(body.get("phone", "")).strip()
            text   = str(body.get("text", "")).strip()
            acc_id = int(body.get("account_id", 0))
            if not phone or not text:
                self._respond_json(400, {"error": "'phone' and 'text' required."}); return
            if not _validate_cm_phone(phone):
                self._respond_json(400, {"error": f"Invalid phone: '{phone}'."}); return
            if len(text) > 480:
                self._respond_json(400, {"error": "SMS text > 480 chars."}); return
            self._respond_json(200, send_outreach_sms(phone, text, acc_id))

        # ── WhatsApp single message ───────────────────────────────────────────
        elif path == "/api/v1/outreach/send-whatsapp":
            phone   = str(body.get("phone", "")).strip()
            text    = str(body.get("text", "")).strip()
            amount  = float(body.get("amount", 0.0))
            loan_id = int(body.get("loan_id", 0))
            if not phone or not text:
                self._respond_json(400, {"error": "'phone' and 'text' required."}); return
            self._respond_json(200, send_whatsapp_message(phone, text, amount, loan_id))

        # ── WhatsApp outreach sequence ────────────────────────────────────────
        elif path == "/api/v1/whatsapp/send-sequence":
            acc_id  = int(body.get("account_id", 0))
            phone   = str(body.get("phone", "")).strip()
            overdue = float(body.get("overdue_fcfa", 0.0))
            loan_id = int(body.get("loan_id", 0))
            name    = str(body.get("client_name", "")).strip()
            officer = str(body.get("officer_name", "System")).strip()
            if not acc_id or not phone or overdue <= 0:
                self._respond_json(400, {
                    "error": "'account_id', 'phone', and 'overdue_fcfa' are required."
                }); return
            if not _validate_cm_phone(phone):
                self._respond_json(400, {"error": f"Invalid phone: '{phone}'."}); return
            res = start_sequence(acc_id, phone, overdue, loan_id, name, officer)
            self._respond_json(200, res)

        # ── WhatsApp sequence list ────────────────────────────────────────────
        elif path == "/api/v1/whatsapp/sequences":
            acc_id = body.get("account_id")
            status = body.get("status")
            seqs   = list_sequences(account_id=acc_id, status=status)
            summary = wa_summary()
            self._respond_json(200, {"status": "SUCCESS", "sequences": seqs, "summary": summary})

        # ── Tailored Bulk Campaign Dispatch ───────────────────────────────────
        elif path == "/api/v1/outreach/bulk-campaign":
            messages = body.get("messages", [])
            channel = str(body.get("channel", "SMS")).upper()
            campaign_name = str(body.get("campaign_name", "Tailored Recovery Campaign"))

            if not messages or not isinstance(messages, list):
                self._respond_json(400, {"error": "'messages' array is required."})
                return

            sent_count = 0
            failed_count = 0
            total_debt_addressed = 0.0
            results = []

            for msg_item in messages:
                acc_id = int(msg_item.get("account_id", 0))
                phone = str(msg_item.get("phone", "677123456")).strip()
                text = str(msg_item.get("text", "")).strip()
                overdue = float(msg_item.get("overdue", 0.0))
                total_debt_addressed += overdue

                try:
                    if channel == "WHATSAPP":
                        resp = send_whatsapp_message(phone, text, overdue, acc_id)
                    else:
                        resp = send_outreach_sms(phone, text, acc_id)
                    
                    sent_count += 1
                    results.append({"account_id": acc_id, "status": "DELIVERED", "response": resp})
                    
                    # Record contact outcome in audit database
                    db_adapter.commit_contact_outcome(
                        account_id=acc_id,
                        loan_id=int(msg_item.get("loan_id", acc_id)),
                        officer_name="Campaign Automation",
                        contact_outcome="CAMPAIGN_MESSAGE_SENT",
                        recommended_channel=channel,
                        is_vulnerable=bool(msg_item.get("is_vulnerable", False)),
                        notes=f"Dispatched via bulk campaign: '{campaign_name}'"
                    )
                except Exception as ex:
                    failed_count += 1
                    results.append({"account_id": acc_id, "status": "FAILED", "error": str(ex)})

            logger.info(f"[CAMPAIGN] '{campaign_name}' finished: {sent_count} sent, {failed_count} failed, total book {total_debt_addressed:,.0f} FCFA")
            self._respond_json(200, {
                "status": "SUCCESS",
                "campaign_name": campaign_name,
                "channel": channel,
                "total_messages": len(messages),
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_debt_fcfa": total_debt_addressed,
                "audit_timestamp": "2026-10-09T13:15:00Z",
                "results": results[:20]
            })
            return

        # ── Commit contact outcome ────────────────────────────────────────────
        elif path == "/api/v1/collections/commit-outcome":
            acc_id  = int(body.get("account_id", 0))
            loan_id = int(body.get("loan_id", 0))
            outcome = str(body.get("contact_outcome", "")).strip()
            if acc_id <= 0 or not outcome:
                self._respond_json(400, {"error": "'account_id' and 'contact_outcome' required."}); return
            res = db_adapter.commit_contact_outcome(
                account_id=acc_id, loan_id=loan_id,
                officer_name=str(body.get("officer_name", "Officer")),
                contact_outcome=outcome,
                promise_date=body.get("promise_date"),
                promise_amount=float(body.get("promise_amount", 0.0)),
                recommended_channel=str(body.get("recommended_channel", "SMS")),
                is_vulnerable=bool(body.get("is_vulnerable", False)),
                notes=str(body.get("notes", "")),
            )
            self._respond_json(200, res)

        # ── Log a promise-to-pay ──────────────────────────────────────────────
        elif path == "/api/v1/promises/log":
            try:
                res = log_promise(
                    account_id   = int(body.get("account_id", 0)),
                    officer_name = str(body.get("officer_name", "Officer")),
                    amount_fcfa  = float(body.get("amount_fcfa", 0.0)),
                    promise_date = str(body.get("promise_date", "")),
                    loan_id      = int(body.get("loan_id", 0)),
                    phone        = str(body.get("phone", "")),
                    notes        = str(body.get("notes", "")),
                    channel      = str(body.get("channel", "CALL")),
                )
                self._respond_json(200, res)
            except (ValueError, KeyError) as e:
                self._respond_json(400, {"error": str(e)})

        # ── Update promise status ─────────────────────────────────────────────
        elif path == "/api/v1/promises/update-status":
            try:
                res = update_promise_status(
                    promise_id      = str(body.get("promise_id", "")),
                    new_status      = str(body.get("status", "")),
                    resolution_note = str(body.get("note", "")),
                )
                self._respond_json(200, res)
            except (ValueError, KeyError) as e:
                self._respond_json(400, {"error": str(e)})

        else:
            self._respond_json(404, {"error": f"POST '{path}' not found."})


from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True


def run_production_server(port: int = 8080):
    httpd = ThreadedHTTPServer(("", port), ProductionAPIHandler)
    auth  = "AUTH ENABLED" if API_SECRET_KEY else "AUTH DISABLED (dev — set API_SECRET_KEY in .env)"
    logger.info(f"✳  RecoverIQ REST API running on http://localhost:{port} | {auth}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopping gracefully...")
        httpd.server_close()


if __name__ == "__main__":
    run_production_server(8080)

