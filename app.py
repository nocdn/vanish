import json
import os
import random
import requests
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# --- Initialization ---
load_dotenv()  # Load variables from .env file

app = Flask(__name__)

# --- Configuration ---
# Set up logging to output to console (visible in Docker logs)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = app.logger # Use Flask's logger

# Simple list of words for random generation.
WORDS = [
    "apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew",
    "kiwi", "lemon", "mango", "nectarine", "orange", "papaya", "quince", "raspberry",
    "strawberry", "tangerine", "ugli", "vanilla", "watermelon", "xigua", "yam", "zucchini",
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliett", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey", "xray",
    "yankee", "zulu", "red", "blue", "green", "yellow", "purple", "silver", "gold"
]

# --- Helper Functions (adapted from Lambda) ---

def generate_random_prefix():
    """Generates a random prefix like 'word1_word2'."""
    word1 = random.choice(WORDS)
    word2 = random.choice(WORDS)
    return f"{word1}_{word2}"

def create_cloudflare_route(api_key, zone_id, temp_email, destination_email):
    """Calls the Cloudflare API to create an email routing rule."""
    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    rule_name = f"Temp Alias API: {temp_email}"
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
        response.raise_for_status()

        response_data = response.json()
        logger.info(f"Cloudflare API response: {response_data}")

        if response_data.get("success"):
            logger.info(f"Successfully created routing rule for {temp_email}")
            return True, None # Success, no error message
        else:
            error_detail = response_data.get('errors', 'Unknown Cloudflare API error')
            logger.error(f"Cloudflare API indicated failure: {error_detail}")
            return False, json.dumps(error_detail) # Failure, error details

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

@app.route('/generate-email', methods=['GET'])
def generate_email_route():
    """API endpoint to generate a temporary email address."""
    logger.info(f"Received request on /generate-email from {request.remote_addr}")

    # --- Get Configuration from Environment Variables ---
    api_key = os.getenv('CLOUDFLARE_API_KEY')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    destination_email = os.getenv('DESTINATION_EMAIL')
    domain_name = os.getenv('DOMAIN_NAME')

    missing_vars = []
    if not api_key: missing_vars.append('CLOUDFLARE_API_KEY')
    if not zone_id: missing_vars.append('CLOUDFLARE_ZONE_ID')
    if not destination_email: missing_vars.append('DESTINATION_EMAIL')
    if not domain_name: missing_vars.append('DOMAIN_NAME')

    if missing_vars:
        error_message = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        return jsonify({'error': error_message}), 500

    # --- Generate Email ---
    try:
        random_prefix = generate_random_prefix()
        temp_email = f"{random_prefix}@{domain_name}"
        logger.info(f"Generated temporary email: {temp_email}")
    except Exception as e:
        logger.exception("Error during email generation")
        return jsonify({'error': f"Failed to generate email prefix: {e}"}), 500


    # --- Create Cloudflare Route ---
    success, error_details = create_cloudflare_route(api_key, zone_id, temp_email, destination_email)

    # --- Format and Return Response ---
    if success:
        return jsonify({'email': temp_email}), 200
    else:
        # Try to parse Cloudflare error if it's JSON, otherwise return the string
        try:
            error_payload = json.loads(error_details)
        except (json.JSONDecodeError, TypeError):
             error_payload = {'message': error_details or 'Failed to create Cloudflare routing rule'}

        return jsonify({'error': 'Failed to create Cloudflare routing rule', 'details': error_payload}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

# --- Main Execution ---
if __name__ == '__main__':
    # Use environment variables for port and debug
    port = int(os.getenv('FLASK_RUN_PORT', 6020))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    # Use 0.0.0.0 to be accessible from outside the container
    app.run(host='0.0.0.0', port=port, debug=debug_mode)