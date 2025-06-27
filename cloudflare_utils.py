import requests
import logging
import os

logger = logging.getLogger(__name__)

RULE_NAME_PREFIX = "temp_email_api:"


def create_cloudflare_route(api_token: str, zone_id: str, temp_email: str, destination_email: str):
    """Create a routing rule and return (success, rule_id, error)."""
    api_endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    rule_name = f"{RULE_NAME_PREFIX} {temp_email}"
    payload = {
        "actions": [{"type": "forward", "value": [destination_email]}],
        "matchers": [{"field": "to", "type": "literal", "value": temp_email}],
        "enabled": True,
        "name": rule_name,
        "priority": 50,
    }
    try:
        response = requests.post(api_endpoint, headers=headers, json=payload)
        if response.status_code in (400, 403):
            logger.warning("Cloudflare returned %s: %s", response.status_code, response.text)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            rule_id = data["result"]["id"]
            return True, rule_id, None
        return False, None, data.get("errors", "Unknown error")
    except requests.exceptions.RequestException as e:
        return False, None, str(e)


def delete_cloudflare_rule(api_token: str, zone_id: str, rule_id: str):
    """Delete a rule by ID. Returns (success, error)"""
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules/{rule_id}"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        resp = requests.delete(endpoint, headers=headers)
        if resp.status_code == 404:
            return True, None  # Already gone
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False), None if data.get("success") else data.get("errors")
    except requests.exceptions.RequestException as e:
        return False, str(e)


def get_all_cloudflare_rules(api_token: str, zone_id: str):
    """Paginate through rules list. Returns (list, error)"""
    all_rules, page = [], 1
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    headers = {"Authorization": f"Bearer {api_token}"}
    while True:
        params = {"page": page, "per_page": 50}
        try:
            resp = requests.get(endpoint, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return None, data.get("errors", "Unknown error")
            page_rules = data.get("result", [])
            if not page_rules:
                break
            all_rules.extend(page_rules)
            pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= pages:
                break
            page += 1
        except requests.exceptions.RequestException as e:
            return None, str(e)
    return all_rules, None 