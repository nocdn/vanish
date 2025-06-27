import os
import random
import re
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from database import add_email, remove_email, get_comment
from cloudflare_utils import create_cloudflare_route, get_all_cloudflare_rules, delete_cloudflare_rule, RULE_NAME_PREFIX
from extensions import limiter, DEFAULT_RATE_LIMIT

logger = logging.getLogger(__name__)

routes_bp = Blueprint('routes', __name__)

WORDS = [
    "apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew",
    "kiwi", "lemon", "mango", "nectarine", "orange", "papaya", "quince", "raspberry",
    "strawberry", "tangerine", "ugli", "vanilla", "watermelon", "xigua", "yam", "zucchini",
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliett", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey", "xray",
    "yankee", "zulu", "red", "blue", "green", "yellow", "purple", "silver", "gold"
]

class InvalidExpiryError(ValueError):
    pass


def parse_expiry(expiry_str):
    """Parse strings like '10m', '1h', '2d' into future datetime."""
    MINIMUM_EXPIRY_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "5"))
    if not expiry_str:
        return None
    match = re.match(r"^(\d+)([hdm])$", expiry_str.lower())
    if not match:
        raise InvalidExpiryError(
            f"Invalid expiry format: '{expiry_str}'. Use format like '10m', '1h', '2d'."
        )
    value, unit = match.groups()
    value = int(value)
    now = datetime.now(timezone.utc)
    if unit == 'h':
        delta = timedelta(hours=value)
    elif unit == 'd':
        delta = timedelta(days=value)
    else:
        delta = timedelta(minutes=value)

    if delta < timedelta(minutes=MINIMUM_EXPIRY_MINUTES):
        raise InvalidExpiryError(
            f"Minimum expiry duration is {MINIMUM_EXPIRY_MINUTES} minutes. Requested: '{expiry_str}'"
        )
    return now + delta


def generate_random_prefix():
    word1 = random.choice(WORDS)
    word2 = random.choice(WORDS)
    return f"{word1}_{word2}{random.randint(100, 999)}"

GENERATE_RATE_LIMIT = os.getenv("RATE_LIMIT_GENERATE", "20 per day")


@routes_bp.route('/generate', methods=['GET'])
@limiter.limit(GENERATE_RATE_LIMIT)
def generate_email_route():
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    destination_email = os.getenv('DESTINATION_EMAIL')
    domain_name = os.getenv('DOMAIN_NAME')
    expiry_str = request.args.get('expiry')
    comment = request.args.get('comment', 'none')

    missing = [name for name, val in [
        ('CLOUDFLARE_API_TOKEN', api_token),
        ('CLOUDFLARE_ZONE_ID', zone_id),
        ('DESTINATION_EMAIL', destination_email),
        ('DOMAIN_NAME', domain_name),
    ] if not val]
    if missing:
        return jsonify({'error': f"Missing env vars: {', '.join(missing)}"}), 500

    try:
        expires_at = parse_expiry(expiry_str)
    except InvalidExpiryError as e:
        return jsonify({'error': str(e)}), 400

    temp_email = f"{generate_random_prefix()}@{domain_name}"
    success, rule_id, err = create_cloudflare_route(api_token, zone_id, temp_email, destination_email)
    if not success:
        return jsonify({'error': 'Failed to create Cloudflare routing rule', 'details': err}), 500

    add_email(temp_email, rule_id, expires_at, comment)
    return jsonify({
        'email': temp_email,
        'rule_id': rule_id,
        'expires_at': expires_at.isoformat() if expires_at else None,
        'comment': comment,
    }), 200


@routes_bp.route('/list', methods=['GET'])
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_email_routes():
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    if not api_token or not zone_id:
        return jsonify({'error': 'Missing Cloudflare credentials'}), 500

    all_rules, error = get_all_cloudflare_rules(api_token, zone_id)
    if error:
        return jsonify({'error': error}), 500

    emails = []
    for rule in all_rules:
        name = rule.get('name', '')
        if name.startswith(RULE_NAME_PREFIX):
            for m in rule.get('matchers', []):
                if m.get('field') == 'to' and m.get('type') == 'literal':
                    email = m.get('value')
                    emails.append({
                        'email': email,
                        'comment': get_comment(email),
                        'rule_id': rule.get('id')
                    })
                    break
    return jsonify({'generated_emails': emails}), 200


@routes_bp.route('/remove/<path:email_to_remove>', methods=['DELETE'])
@limiter.limit(DEFAULT_RATE_LIMIT)
def remove_email_route(email_to_remove):
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    if not api_token or not zone_id:
        return jsonify({'error': 'Missing Cloudflare credentials'}), 500

    # Try to get rule_id via list rules (could also store in DB) for safety
    all_rules, err = get_all_cloudflare_rules(api_token, zone_id)
    if err:
        return jsonify({'error': err}), 500
    rule_id = None
    for rule in all_rules:
        for m in rule.get('matchers', []):
            if m.get('field') == 'to' and m.get('value') == email_to_remove:
                rule_id = rule.get('id'); break
        if rule_id:
            break

    if not rule_id:
        remove_email(email_to_remove)
        return jsonify({'error': f'Rule for {email_to_remove} not found'}), 404

    success, del_err = delete_cloudflare_rule(api_token, zone_id, rule_id)
    if success:
        remove_email(email_to_remove)
        return jsonify({'message': 'Removed'}), 200
    return jsonify({'error': del_err}), 500


@routes_bp.route('/health', methods=['GET'])
@limiter.limit(DEFAULT_RATE_LIMIT)
def health_check():
    from flask import current_app
    response = {
        'status': 'healthy',
        'checks': {
            'scheduler': 'running' if getattr(current_app, 'scheduler', None) and current_app.scheduler.running else 'not running'
        }
    }
    status_code = 200 if response['checks']['scheduler'] == 'running' else 503
    return jsonify(response), status_code


@routes_bp.route('/help', methods=['GET'])
@limiter.limit(DEFAULT_RATE_LIMIT)
def help_endpoint():
    info = {
        'service': 'Cloudflare Temp-Mail API',
        'routes': ['/generate', '/list', '/remove/<email>', '/health', '/help'],
    }
    return jsonify(info), 200 