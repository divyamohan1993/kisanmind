"""
Fetch Mandi Prices Cloud Function
==================================
Retrieves commodity prices from data.gov.in (AgMarkNet) API.
Returns an error when API key is unavailable.
"""

import json
import os
from datetime import datetime

import functions_framework
import requests

DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY", "")
AGMARKNET_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"



def _fetch_from_api(commodity: str, state: str) -> list[dict] | None:
    """Fetch live prices from data.gov.in AgMarkNet API."""
    if not DATA_GOV_API_KEY:
        return None
    url = "https://api.data.gov.in/resource/" + AGMARKNET_RESOURCE_ID
    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": 50,
        "filters[commodity]": commodity.title(),
        "filters[state]": state.title(),
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        records = data.get("records", [])
        return [
            {
                "mandi": r.get("market", "Unknown"),
                "min_price": int(r.get("min_price", 0)),
                "max_price": int(r.get("max_price", 0)),
                "modal_price": int(r.get("modal_price", 0)),
                "date": r.get("arrival_date", ""),
            }
            for r in records
        ]
    except Exception:
        return None


@functions_framework.http
def fetch_mandi_prices(request):
    """
    HTTP Cloud Function entry point.

    Query params or JSON body:
        commodity (str): Crop name (e.g. tomato, wheat).
        state (str): Indian state name.

    Returns:
        JSON array of {mandi, min_price, max_price, modal_price, date}.
    """
    if request.is_json:
        body = request.get_json(silent=True) or {}
        commodity = body.get("commodity", "")
        state = body.get("state", "")
    else:
        commodity = request.args.get("commodity", "")
        state = request.args.get("state", "")

    if not commodity:
        return json.dumps({"error": "Missing 'commodity' parameter"}), 400, {"Content-Type": "application/json"}

    # Fetch live prices from API
    prices = _fetch_from_api(commodity, state)
    if prices is None:
        return json.dumps({
            "error": "Unable to fetch mandi prices. AgMarkNet API unavailable or API key not configured.",
            "commodity": commodity,
            "state": state,
        }), 503, {"Content-Type": "application/json"}

    return json.dumps({
        "commodity": commodity,
        "state": state,
        "source": "data.gov.in",
        "count": len(prices),
        "prices": prices,
    }), 200, {"Content-Type": "application/json"}
