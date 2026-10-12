"""Production Credit Union Core Banking System (CBS) Database Adapter.

Provides database synchronization for pulling live loan arrears books and committing
officer contact outcomes (P2P dates, payment commitments, hardship flags) to PostgreSQL, MySQL, or SQLite.
"""
import sqlite3
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from src.config import Config

logger = logging.getLogger("CBSDatabaseAdapter")


class CollectionsDatabaseAdapter:
    """Core Banking Database Interface."""

    def __init__(self):
        self.db_type = Config.DB_TYPE
        self.db_path = Config.DB_SQLITE_PATH
        self._init_db_schema()

    def _get_connection(self):
        """Establish connection based on configured DB_TYPE."""
        if self.db_type == "postgres":
            try:
                import psycopg2
                return psycopg2.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    dbname=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
            except ImportError:
                logger.warning("psycopg2 not installed. Falling back to SQLite.")
                return sqlite3.connect(self.db_path)
        elif self.db_type == "mysql":
            try:
                import pymysql
                return pymysql.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    database=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
            except ImportError:
                logger.warning("pymysql not installed. Falling back to SQLite.")
                return sqlite3.connect(self.db_path)
        else:
            # SQLite default
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(self.db_path)

    def _init_db_schema(self):
        """Ensure collections outcomes and audit logs tables exist in DB."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS officer_contact_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    loan_id INTEGER NOT NULL,
                    officer_name TEXT NOT NULL,
                    contact_outcome TEXT NOT NULL,
                    promise_date TEXT,
                    promise_amount REAL,
                    recommended_channel TEXT,
                    is_vulnerable INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS momo_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_id TEXT NOT NULL,
                    account_id INTEGER NOT NULL,
                    loan_id INTEGER NOT NULL,
                    amount_fcfa REAL NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Indexes for fast lookups as data grows
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_account ON officer_contact_outcomes(account_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_created ON officer_contact_outcomes(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_momo_account ON momo_transactions(account_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_momo_ref ON momo_transactions(reference_id);")
            conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
        finally:
            conn.close()

    def commit_contact_outcome(
        self,
        account_id: int,
        loan_id: int,
        officer_name: str,
        contact_outcome: str,
        promise_date: str = None,
        promise_amount: float = 0.0,
        recommended_channel: str = "SMS",
        is_vulnerable: bool = False,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Commit an officer contact outcome to the Credit Union database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO officer_contact_outcomes (
                    account_id, loan_id, officer_name, contact_outcome,
                    promise_date, promise_amount, recommended_channel,
                    is_vulnerable, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                account_id, loan_id, officer_name, contact_outcome,
                promise_date, promise_amount, recommended_channel,
                1 if is_vulnerable else 0, notes, now_str
            ))
            conn.commit()
            return {
                "status": "SUCCESS",
                "message": f"Outcome '{contact_outcome}' committed to database for Client #{account_id}.",
                "timestamp": now_str
            }
        except Exception as e:
            logger.error(f"Error committing outcome to DB: {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            conn.close()

    def record_momo_transaction(
        self,
        reference_id: str,
        account_id: int,
        loan_id: int,
        amount_fcfa: float,
        phone: str,
        status: str,
        provider: str
    ) -> bool:
        """Record MoMo collection transaction audit entry."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO momo_transactions (
                    reference_id, account_id, loan_id, amount_fcfa, phone, status, provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (reference_id, account_id, loan_id, amount_fcfa, phone, status, provider))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error recording MoMo transaction: {e}")
            return False
        finally:
            conn.close()

    def get_recent_outcomes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent officer logged outcomes from DB."""
        conn = self._get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM officer_contact_outcomes ORDER BY created_at DESC LIMIT ?",
                conn,
                params=(limit,)
            )
            return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Error fetching outcomes: {e}")
            return []
        finally:
            conn.close()
