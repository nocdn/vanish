import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure default rate limits from environment
DEFAULT_RATE_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "60 per minute")

# Global limiter instance (to be initialised with the Flask app in app.py)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri="memory://",
    strategy="fixed-window",
) 