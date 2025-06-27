import os
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import g, current_app

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/emails.db')

def get_db():
    """Return a connection for the current request context, creating it if needed."""
    db = g.get('db')
    if db is None:
        db = g.db = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db

def close_db(exception=None):
    """Close the connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Ensure database exists and has the expected schema."""
    try:
        path_obj = Path(DATABASE_PATH)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(DATABASE_PATH)
        cursor = db.cursor()
        # Added rule_id column (critique 4.1)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS temporary_emails (
                email TEXT PRIMARY KEY,
                rule_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                comment TEXT DEFAULT 'none'
            )
            """
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_expires_at ON temporary_emails (expires_at)"""
        )
        db.commit()
        # Ensure legacy DBs have rule_id column
        migrate_add_rule_id()
        logger.info("Database initialised or already present at %s", DATABASE_PATH)
    except Exception:
        logger.exception("Failed to initialise database")
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass

def add_email(email: str, rule_id: str, expires_at, comment: str = "none") -> bool:
    """Insert or replace an email entry."""
    try:
        db = get_db()
        created_at = datetime.now(timezone.utc).isoformat()
        expires_at_iso = expires_at.isoformat() if expires_at else 'never'
        db.execute(
            """INSERT OR REPLACE INTO temporary_emails (email, rule_id, created_at, expires_at, comment)
               VALUES (?, ?, ?, ?, ?)""",
            (email, rule_id, created_at, expires_at_iso, comment),
        )
        db.commit()
        logger.debug("Added/updated %s in DB with rule_id=%s", email, rule_id)
        return True
    except Exception:
        logger.exception("Failed to add/update %s", email)
        return False


def remove_email(email: str) -> bool:
    try:
        db = get_db()
        db.execute("DELETE FROM temporary_emails WHERE email = ?", (email,))
        db.commit()
        logger.debug("Removed %s from DB", email)
        return True
    except Exception:
        logger.exception("Failed to remove %s", email)
        return False


def get_comment(email: str) -> str:
    try:
        db = get_db()
        row = db.execute("SELECT comment FROM temporary_emails WHERE email = ?", (email,)).fetchone()
        return row[0] if row else "none"
    except Exception:
        logger.exception("Failed to fetch comment for %s", email)
        return "none"


def get_expired_emails(now_iso):
    """Return list of rows for expired emails."""
    db = get_db()
    return db.execute(
        "SELECT email, rule_id, expires_at FROM temporary_emails WHERE expires_at != 'never' AND expires_at < ?",
        (now_iso,),
    ).fetchall()


def migrate_add_rule_id():
    """Ensure rule_id column exists (simple runtime migration)."""
    db = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(temporary_emails)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'rule_id' not in columns:
            cursor.execute("ALTER TABLE temporary_emails ADD COLUMN rule_id TEXT")
            db.commit()
            logger.info("Added missing rule_id column to temporary_emails table")
    except Exception:
        logger.exception("Failed to run rule_id migration")
    finally:
        db.close() 