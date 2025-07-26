import os
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import g, current_app

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/emails.db')
TABLE_NAME = 'emails'

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
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                email TEXT PRIMARY KEY,
                rule_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                comment TEXT DEFAULT 'none'
            )
            """
        )
        cursor.execute(
            f"""CREATE INDEX IF NOT EXISTS idx_expires_at ON {TABLE_NAME} (expires_at)"""
        )
        db.commit()
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
            f"""INSERT OR REPLACE INTO {TABLE_NAME} (email, rule_id, created_at, expires_at, comment)
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
        db.execute(f"DELETE FROM {TABLE_NAME} WHERE email = ?", (email,))
        db.commit()
        logger.debug("Removed %s from DB", email)
        return True
    except Exception:
        logger.exception("Failed to remove %s", email)
        return False


def get_comment(email: str) -> str:
    try:
        db = get_db()
        row = db.execute(f"SELECT comment FROM {TABLE_NAME} WHERE email = ?", (email,)).fetchone()
        return row[0] if row else "none"
    except Exception:
        logger.exception("Failed to fetch comment for %s", email)
        return "none"


def get_expired_emails(now_iso):
    """Return list of rows for expired emails."""
    db = get_db()
    return db.execute(
        f"SELECT email, rule_id, expires_at FROM {TABLE_NAME} WHERE expires_at != 'never' AND expires_at < ?",
        (now_iso,),
    ).fetchall()


def migrate_add_rule_id():
    """Ensure rule_id column exists (simple runtime migration)."""
    db = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = db.cursor()
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = [row[1] for row in cursor.fetchall()]
        if 'rule_id' not in columns:
            cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN rule_id TEXT")
            db.commit()
            logger.info("Added missing rule_id column to %s table", TABLE_NAME)
    except Exception:
        logger.exception("Failed to run rule_id migration")
    finally:
        db.close() 