import os
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from typing import Optional

from database import get_expired_emails, remove_email
from cloudflare_utils import delete_cloudflare_rule

logger = logging.getLogger(__name__)

scheduler_instance: Optional[BackgroundScheduler] = None


def _cleanup_expired_emails():
    """Job that purges expired emails; designed to be resilient (critique 4.1)."""
    with current_app.app_context():
        api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
        clear_after_expiry = os.getenv("CLEAR_AFTER_EXPIRY", "false").lower() == "true"

        if not api_token or not zone_id:
            logger.warning("Cleanup job skipped: missing Cloudflare credentials")
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        expired_rows = get_expired_emails(now_iso)
        if not expired_rows:
            logger.debug("Cleanup job: no expired emails")
            return

        logger.info("Cleanup job: found %d expired emails", len(expired_rows))
        for row in expired_rows:
            email = row["email"]
            rule_id = row["rule_id"]
            logger.debug("Processing expired %s (rule_id=%s)", email, rule_id)
            success = True
            if rule_id:
                success, err = delete_cloudflare_rule(api_token, zone_id, rule_id)
                if not success:
                    logger.error("Failed to delete rule %s for %s: %s", rule_id, email, err)
            # If deletion succeeded or rule_id missing, optionally remove from DB
            if success and clear_after_expiry:
                remove_email(email)


def start_scheduler(app):
    """Attach and start BackgroundScheduler if not already started."""
    global scheduler_instance
    if scheduler_instance and scheduler_instance.running:
        return scheduler_instance

    interval_minutes = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "5"))
    scheduler_instance = BackgroundScheduler(daemon=True)
    scheduler_instance.add_job(_cleanup_expired_emails, "interval", minutes=interval_minutes)
    scheduler_instance.start()

    # Add a flag onto app for health check (critique 4.2)
    app.scheduler = scheduler_instance
    logger.info("Background scheduler started (interval=%d min)", interval_minutes)
    return scheduler_instance 