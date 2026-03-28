"""
Fetch Mandi Prices Cloud Function
==================================
Retrieves commodity prices from data.gov.in (AgMarkNet) API.
Falls back to hardcoded demo data when API key is unavailable.
"""

import json
import os
from datetime import datetime

import functions_framework
import requests

DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY", "")
AGMARKNET_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"

# ---------------------------------------------------------------------------
# Demo data (realistic prices in INR per quintal)
# ---------------------------------------------------------------------------
DEMO_PRICES = {
    "tomato": {
        "himachal pradesh": [
            {"mandi": "Solan", "min_price": 1800, "max_price": 3200, "modal_price": 2600, "date": "2025-03-20"},
            {"mandi": "Shimla", "min_price": 2000, "max_price": 3500, "modal_price": 2850, "date": "2025-03-20"},
            {"mandi": "Kullu", "min_price": 1600, "max_price": 2800, "modal_price": 2200, "date": "2025-03-19"},
            {"mandi": "Mandi", "min_price": 1700, "max_price": 3000, "modal_price": 2400, "date": "2025-03-19"},
        ],
        "punjab": [
            {"mandi": "Ludhiana", "min_price": 1500, "max_price": 2800, "modal_price": 2200, "date": "2025-03-20"},
            {"mandi": "Amritsar", "min_price": 1400, "max_price": 2600, "modal_price": 2000, "date": "2025-03-20"},
            {"mandi": "Jalandhar", "min_price": 1550, "max_price": 2700, "modal_price": 2150, "date": "2025-03-19"},
        ],
        "karnataka": [
            {"mandi": "Bangalore", "min_price": 1200, "max_price": 2500, "modal_price": 1800, "date": "2025-03-20"},
            {"mandi": "Mysore", "min_price": 1100, "max_price": 2400, "modal_price": 1700, "date": "2025-03-20"},
            {"mandi": "Hubli", "min_price": 1000, "max_price": 2200, "modal_price": 1600, "date": "2025-03-19"},
        ],
    },
    "wheat": {
        "punjab": [
            {"mandi": "Ludhiana", "min_price": 2100, "max_price": 2275, "modal_price": 2200, "date": "2025-03-20"},
            {"mandi": "Amritsar", "min_price": 2050, "max_price": 2250, "modal_price": 2150, "date": "2025-03-20"},
            {"mandi": "Patiala", "min_price": 2080, "max_price": 2260, "modal_price": 2180, "date": "2025-03-19"},
            {"mandi": "Bathinda", "min_price": 2000, "max_price": 2240, "modal_price": 2125, "date": "2025-03-19"},
        ],
        "himachal pradesh": [
            {"mandi": "Solan", "min_price": 2150, "max_price": 2350, "modal_price": 2250, "date": "2025-03-20"},
            {"mandi": "Mandi", "min_price": 2100, "max_price": 2300, "modal_price": 2200, "date": "2025-03-19"},
        ],
    },
    "rice": {
        "punjab": [
            {"mandi": "Ludhiana", "min_price": 2100, "max_price": 2400, "modal_price": 2250, "date": "2025-03-20"},
            {"mandi": "Amritsar", "min_price": 2050, "max_price": 2350, "modal_price": 2200, "date": "2025-03-20"},
        ],
        "karnataka": [
            {"mandi": "Bangalore", "min_price": 2800, "max_price": 3400, "modal_price": 3100, "date": "2025-03-20"},
            {"mandi": "Mysore", "min_price": 2700, "max_price": 3300, "modal_price": 3000, "date": "2025-03-19"},
        ],
    },
    "apple": {
        "himachal pradesh": [
            {"mandi": "Shimla", "min_price": 4000, "max_price": 8000, "modal_price": 6000, "date": "2025-03-20"},
            {"mandi": "Kullu", "min_price": 3800, "max_price": 7500, "modal_price": 5500, "date": "2025-03-19"},
            {"mandi": "Solan", "min_price": 3500, "max_price": 7000, "modal_price": 5200, "date": "2025-03-19"},
        ],
    },
    "coffee": {
        "karnataka": [
            {"mandi": "Chikmagalur", "min_price": 18000, "max_price": 24000, "modal_price": 21000, "date": "2025-03-20"},
            {"mandi": "Hassan", "min_price": 17500, "max_price": 23000, "modal_price": 20000, "date": "2025-03-19"},
            {"mandi": "Kodagu", "min_price": 18500, "max_price": 24500, "modal_price": 21500, "date": "2025-03-20"},
        ],
    },
}


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


def _get_demo_prices(commodity: str, state: str) -> list[dict]:
    """Return hardcoded demo prices for the commodity and state."""
    commodity_lower = commodity.lower().strip()
    state_lower = state.lower().strip()
    commodity_data = DEMO_PRICES.get(commodity_lower, {})
    return commodity_data.get(state_lower, [])


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

    # Try live API first, fall back to demo
    prices = _fetch_from_api(commodity, state)
    if prices is None:
        prices = _get_demo_prices(commodity, state)
        source = "demo_data"
    else:
        source = "data.gov.in"

    return json.dumps({
        "commodity": commodity,
        "state": state,
        "source": source,
        "count": len(prices),
        "prices": prices,
    }), 200, {"Content-Type": "application/json"}
