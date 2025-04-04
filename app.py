import json
import os
import random
import requests
import logging
import csv # Added for CSV writing
from datetime import datetime # Added for timestamp
from pathlib import Path # Added for handling file paths

from flask import Flask, jsonify, request
from dotenv import load_dotenv

# --- Initialization ---
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

CSV_HEADER = ['timestamp', 'email']
# --- Helper Functions ---

def generate_random_prefix():
    """Generates a random prefix like 'word1_word2'."""
    word1 = random.choice(WORDS)
    word2 = random.choice(WORDS)
    return f"{word1}_{word2}"

def log_to_csv(temp_email):
    """Appends the generated email and timestamp to the CSV log file."""
    csv_path_str = os.getenv('CSV_LOG_PATH')
    if not csv_path_str:
        logger.warning("CSV_LOG_PATH environment variable not set. Skipping CSV logging.")
        return

    try:
        csv_path = Path(csv_path_str)
        # Ensure the directory exists (create if it doesn't)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = csv_path.is_file()

        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists or csv_path.stat().st_size == 0:
                writer.writerow(CSV_HEADER) # Write header if file is new or empty
            timestamp = datetime.now().isoformat()
            writer.writerow([timestamp, temp_email])
            logger.info(f"Successfully logged {temp_email} to {csv_path_str}")

    except IOError as e:
        logger.error(f"IOError writing to CSV file {csv_path_str}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error writing to CSV file {csv_path_str}")


def create_cloudflare_route(api_key, zone_id, temp_email, destination_email):
    """Calls the Cloudflare API to create an email routing rule."""
    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {
        "Authorization": f"Bearer {api_key}", # Use the API Token
        "Content-Type": "application/json"
    }
    # Use a distinct name prefix to help identify rules created by this API in the /list route
    rule_name_prefix = "Temp Email API:"
    rule_name = f"{rule_name_prefix} {temp_email}"

    payload = {
        "actions": [{"type": "forward", "value": [destination_email]}],
        "matchers": [{"field": "to", "type": "literal", "value": temp_email}],
        "enabled": True,
        "name": rule_name,
        "priority": 50 # Adjust priority as needed
    }

    try:
        logger.info(f"Attempting to create Cloudflare route for {temp_email}")
        response = requests.post(api_endpoint, headers=headers, json=payload)
        # Check specifically for common errors like authentication or duplicate rule name
        if response.status_code == 403:
             logger.error(f"Cloudflare API Error 403 (Forbidden): Check API token permissions. Response: {response.text}")
             return False, f"Permission denied. Check API Token. Details: {response.text}"
        if response.status_code == 400 and "rule with the same name already exists" in response.text:
             logger.error(f"Cloudflare API Error 400: Duplicate rule name '{rule_name}'. Response: {response.text}")
             # Potentially retry generation or just report the specific error
             return False, f"A rule with the name '{rule_name}' already exists. Try again."

        response.raise_for_status() # Raise errors for other 4xx/5xx codes

        response_data = response.json()
        logger.info(f"Cloudflare API response: {response_data}")

        if response_data.get("success"):
            logger.info(f"Successfully created routing rule for {temp_email}")
            return True, None # Success, no error message
        else:
            # Log and return specific Cloudflare errors if available
            error_detail = response_data.get('errors', [{'message': 'Unknown Cloudflare API error'}])
            logger.error(f"Cloudflare API indicated failure: {error_detail}")
            # Return the list of error objects directly
            return False, error_detail

    except requests.exceptions.RequestException as e:
        error_body = "Could not decode error response."
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.text
            except Exception:
                pass # Keep default error_body
        logger.error(f"Error calling Cloudflare API: {e}. Response: {error_body}")
        return False, f"Network or API error: {e}" # Failure, error message
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Cloudflare API call for {temp_email}")
        return False, f"Unexpected server error: {e}" # Failure, error message

# --- Flask Routes ---

@app.route('/generate', methods=['GET'])
def generate_email_route():
    """API endpoint to generate a temporary email address."""
    logger.info(f"Received request on /generate from {request.remote_addr}")

    api_key = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    destination_email = os.getenv('DESTINATION_EMAIL')
    domain_name = os.getenv('DOMAIN_NAME')

    missing_vars = []
    if not api_key: missing_vars.append('CLOUDFLARE_API_TOKEN')
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

    success, error_details = create_cloudflare_route(api_key, zone_id, temp_email, destination_email)

    if success:
        # Log to CSV only *after* successful Cloudflare rule creation
        log_to_csv(temp_email)
        return jsonify({'email': temp_email}), 200
    else:
        # Error details should now be the Cloudflare error list or a string
        return jsonify({'error': 'Failed to create Cloudflare routing rule', 'details': error_details}), 500

@app.route('/list', methods=['GET'])
def list_email_routes():
    """Lists email routing rules created by this API from Cloudflare."""
    logger.info(f"Received request on /list from {request.remote_addr}")

    api_key = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')

    if not api_key or not zone_id:
        return jsonify({'error': 'Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID environment variables'}), 500

    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {"Authorization": f"Bearer {api_key}"}
    # Define the prefix used when creating rules to filter by it
    rule_name_prefix = "Temp Email API:"

    generated_emails = []
    page = 1
    # Basic pagination handling - loop until no more results are expected
    # Note: Cloudflare might change API limits, adjust per_page if needed/possible
    while True:
        params = {'page': page, 'per_page': 50} # Request up to 50 per page
        try:
            logger.info(f"Fetching page {page} of Cloudflare email rules")
            response = requests.get(api_endpoint, headers=headers, params=params)
            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("success"):
                error_detail = response_data.get('errors', 'Unknown Cloudflare API error')
                logger.error(f"Cloudflare API failed on list: {error_detail}")
                return jsonify({'error': 'Failed to list Cloudflare rules', 'details': error_detail}), 500

            rules = response_data.get("result", [])
            if not rules: # No more rules found on this page
                break

            for rule in rules:
                rule_name = rule.get("name", "")
                # Filter rules created by this specific API based on name prefix
                if rule_name.startswith(rule_name_prefix):
                    # Extract email from the first literal 'to' matcher
                    matchers = rule.get("matchers", [])
                    for matcher in matchers:
                        if matcher.get("field") == "to" and matcher.get("type") == "literal":
                            generated_emails.append(matcher.get("value"))
                            break # Found the email for this rule

            # Check pagination info to see if we need to fetch more
            result_info = response_data.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            current_page = result_info.get("page", 1)

            if current_page >= total_pages:
                break # Last page reached

            page += 1 # Go to the next page

        except requests.exceptions.RequestException as e:
            error_body = "Could not decode error response."
            if hasattr(e, 'response') and e.response is not None:
                try: error_body = e.response.text
                except Exception: pass
            logger.error(f"Error listing Cloudflare rules: {e}. Response: {error_body}")
            return jsonify({'error': f"Network or API error during list: {e}"}), 500
        except Exception as e:
            logger.exception("Unexpected error listing Cloudflare rules")
            return jsonify({'error': f"Unexpected server error during list: {e}"}), 500

    logger.info(f"Found {len(generated_emails)} email rules matching prefix '{rule_name_prefix}'")
    return jsonify({'generated_emails': generated_emails}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.getenv('FLASK_RUN_PORT', 6020))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)