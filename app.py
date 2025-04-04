import json
import os
import random
import requests
import logging

from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file

app = Flask(__name__)

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = app.logger

WORDS = [
    "apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew",
    "kiwi", "lemon", "mango", "nectarine", "orange", "papaya", "quince", "raspberry",
    "strawberry", "tangerine", "ugli", "vanilla", "watermelon", "xigua", "yam", "zucchini",
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliett", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey", "xray",
    "yankee", "zulu", "red", "blue", "green", "yellow", "purple", "silver", "gold"
]

# Prefix used to identify rules created by this API
RULE_NAME_PREFIX = "temp_email_api:"


def generate_random_prefix():
    """Generates a random prefix like 'word1_word2123'."""
    word1 = random.choice(WORDS)
    word2 = random.choice(WORDS)
    random_digits = random.randint(100, 999)  # Generate random 3-digit number
    return f"{word1}_{word2}{random_digits}"


def create_cloudflare_route(api_token, zone_id, temp_email, destination_email):
    """Calls the Cloudflare API to create an email routing rule."""
    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {
        "Authorization": f"Bearer {api_token}", # Use the API Token
        "Content-Type": "application/json"
    }
    rule_name = f"{RULE_NAME_PREFIX} {temp_email}" # Use the defined prefix

    payload = {
        "actions": [{"type": "forward", "value": [destination_email]}],
        "matchers": [{"field": "to", "type": "literal", "value": temp_email}],
        "enabled": True,
        "name": rule_name,
        "priority": 50
    }

    try:
        logger.info(f"Attempting to create Cloudflare route for {temp_email} with name '{rule_name}'")
        response = requests.post(api_endpoint, headers=headers, json=payload)

        # Specific error checks
        if response.status_code == 403:
             logger.error(f"Cloudflare API Error 403 (Forbidden): Check API token permissions. Response: {response.text}")
             return False, f"Permission denied. Check API Token. Details: {response.text}"
        if response.status_code == 400 and "rule with the same name already exists" in response.text.lower():
             logger.warning(f"Cloudflare API Error 400: Duplicate rule name '{rule_name}'. Response: {response.text}")
             return False, f"A rule with the name '{rule_name}' may already exist."
        if response.status_code == 400 and "rule with the same matcher already exists" in response.text.lower():
             logger.warning(f"Cloudflare API Error 400: Duplicate matcher for email '{temp_email}'. Response: {response.text}")
             return False, f"A rule matching email '{temp_email}' may already exist."

        response.raise_for_status() # Raise errors for other 4xx/5xx codes

        response_data = response.json()
        logger.info(f"Cloudflare API response: {response_data}")

        if response_data.get("success"):
            logger.info(f"Successfully created routing rule for {temp_email}")
            return True, None # Success, no error message
        else:
            error_detail = response_data.get('errors', [{'message': 'Unknown Cloudflare API error'}])
            logger.error(f"Cloudflare API indicated failure: {error_detail}")
            return False, error_detail # Return list of error objects

    except requests.exceptions.RequestException as e:
        error_body = "Could not decode error response."
        if hasattr(e, 'response') and e.response is not None:
            try: error_body = e.response.text
            except Exception: pass
        logger.error(f"Error calling Cloudflare API: {e}. Response: {error_body}")
        return False, f"Network or API error: {e}"
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Cloudflare API call for {temp_email}")
        return False, f"Unexpected server error: {e}"


def get_all_cloudflare_rules(api_token, zone_id):
    """Fetches all email routing rules from Cloudflare using pagination."""
    all_rules = []
    page = 1
    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {"Authorization": f"Bearer {api_token}"}

    while True:
        params = {'page': page, 'per_page': 50}
        try:
            logger.info(f"Fetching page {page} of Cloudflare email rules")
            response = requests.get(api_endpoint, headers=headers, params=params)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("success"):
                error_detail = response_data.get('errors', 'Unknown Cloudflare API error listing rules')
                logger.error(f"Cloudflare API failed on list (page {page}): {error_detail}")
                # Return None and the error details
                return None, error_detail

            rules_on_page = response_data.get("result", [])
            if not rules_on_page:
                break # No more rules on this page

            all_rules.extend(rules_on_page)

            result_info = response_data.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            if page >= total_pages:
                break # Last page reached

            page += 1

        except requests.exceptions.RequestException as e:
            error_body = "Could not decode list response."
            if hasattr(e, 'response') and e.response is not None:
                try: error_body = e.response.text
                except Exception: pass
            logger.error(f"Error listing Cloudflare rules (page {page}): {e}. Response: {error_body}")
            return None, f"Network or API error during list: {e}"
        except Exception as e:
            logger.exception(f"Unexpected error listing Cloudflare rules (page {page})")
            return None, f"Unexpected server error during list: {e}"

    logger.info(f"Successfully fetched {len(all_rules)} total rules from Cloudflare.")
    return all_rules, None # Return rules, no error


@app.route('/generate', methods=['GET'])
def generate_email_route():
    """API endpoint to generate a temporary email address."""
    logger.info(f"Received request on /generate from {request.remote_addr}")

    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    destination_email = os.getenv('DESTINATION_EMAIL')
    domain_name = os.getenv('DOMAIN_NAME')

    missing_vars = []
    if not api_token: missing_vars.append('CLOUDFLARE_API_TOKEN')
    if not zone_id: missing_vars.append('CLOUDFLARE_ZONE_ID')
    if not destination_email: missing_vars.append('DESTINATION_EMAIL')
    if not domain_name: missing_vars.append('DOMAIN_NAME')

    if missing_vars:
        error_message = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        return jsonify({'error': error_message}), 500

    try:
        random_prefix = generate_random_prefix()
        temp_email = f"{random_prefix}@{domain_name}"
        logger.info(f"Generated temporary email: {temp_email}")
    except Exception as e:
        logger.exception("Error during email generation")
        return jsonify({'error': f"Failed to generate email prefix: {e}"}), 500

    success, error_details = create_cloudflare_route(api_token, zone_id, temp_email, destination_email)

    if success:
        return jsonify({'email': temp_email}), 200
    else:
        return jsonify({'error': 'Failed to create Cloudflare routing rule', 'details': error_details}), 500


@app.route('/list', methods=['GET'])
def list_email_routes():
    """Lists email routing rules created by this API from Cloudflare."""
    logger.info(f"Received request on /list from {request.remote_addr}")

    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')

    if not api_token or not zone_id:
        return jsonify({'error': 'Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID environment variables'}), 500

    all_rules, error = get_all_cloudflare_rules(api_token, zone_id)

    if error:
        # Error already logged in helper function
        return jsonify({'error': 'Failed to retrieve rules from Cloudflare', 'details': error}), 500

    generated_emails = []
    for rule in all_rules:
        rule_name = rule.get("name", "")
        # Filter rules created by this specific API based on name prefix
        if rule_name.startswith(RULE_NAME_PREFIX):
            # Extract email from the first literal 'to' matcher
            matchers = rule.get("matchers", [])
            for matcher in matchers:
                if matcher.get("field") == "to" and matcher.get("type") == "literal":
                    email = matcher.get("value")
                    if email:
                       generated_emails.append(email)
                    break # Found the email for this rule

    logger.info(f"Found {len(generated_emails)} email rules matching prefix '{RULE_NAME_PREFIX}'")
    return jsonify({'generated_emails': generated_emails}), 200


@app.route('/remove/<path:email_to_remove>', methods=['DELETE'])
def remove_email_route(email_to_remove):
    """Removes a specific email routing rule created by this API."""
    logger.info(f"Received request on /remove for {email_to_remove} from {request.remote_addr}")

    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')

    if not api_token or not zone_id:
        return jsonify({'error': 'Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID environment variables'}), 500

    # 1. Find the rule ID for the given email
    all_rules, list_error = get_all_cloudflare_rules(api_token, zone_id)
    if list_error:
        return jsonify({'error': 'Failed to retrieve rules to find rule ID', 'details': list_error}), 500

    rule_id_to_remove = None
    for rule in all_rules:
        matchers = rule.get("matchers", [])
        for matcher in matchers:
            if (matcher.get("field") == "to" and
                matcher.get("type") == "literal" and
                matcher.get("value") == email_to_remove):
                rule_id_to_remove = rule.get("id")
                logger.info(f"Found rule ID {rule_id_to_remove} for email {email_to_remove}")
                break # Found the matcher
        if rule_id_to_remove:
            break # Found the rule

    if not rule_id_to_remove:
        logger.warning(f"Rule for email {email_to_remove} not found in Cloudflare.")
        return jsonify({'error': f'Rule for email {email_to_remove} not found'}), 404

    # 2. Call the DELETE API endpoint
    delete_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules/{rule_id_to_remove}"
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        logger.info(f"Attempting to delete Cloudflare rule ID {rule_id_to_remove} for email {email_to_remove}")
        response = requests.delete(delete_endpoint, headers=headers)
        response.raise_for_status() # Check for 4xx/5xx errors

        response_data = response.json()
        logger.info(f"Cloudflare DELETE API response: {response_data}")

        if response_data.get("success"):
            logger.info(f"Successfully deleted rule for {email_to_remove}")
            return jsonify({'message': f'Successfully removed rule for {email_to_remove}'}), 200
        else:
            error_detail = response_data.get('errors', [{'message': 'Unknown error during deletion'}])
            logger.error(f"Cloudflare API indicated failure during delete: {error_detail}")
            return jsonify({'error': 'Cloudflare failed to delete the rule', 'details': error_detail}), 500

    except requests.exceptions.RequestException as e:
        error_body = "Could not decode delete response."
        if hasattr(e, 'response') and e.response is not None:
            try: error_body = e.response.text
            except Exception: pass
        logger.error(f"Error deleting Cloudflare rule {rule_id_to_remove}: {e}. Response: {error_body}")
        return jsonify({'error': f"Network or API error during delete: {e}"}), 500
    except Exception as e:
        logger.exception(f"Unexpected error deleting Cloudflare rule {rule_id_to_remove}")
        return jsonify({'error': f"Unexpected server error during delete: {e}"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.getenv('FLASK_RUN_PORT', 6020))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)