"""
Calculate Profit Cloud Function
================================
Ranks mandis by net profit after accounting for transport cost, commission,
and spoilage risk.
"""

import json
import math
import os

import functions_framework

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TRANSPORT_COST_PER_KM_PER_QTL = 3.5  # INR per km per quintal
DEFAULT_COMMISSION_RATE = 0.04        # 4% mandi commission
SPOILAGE_RATES = {
    "tomato": 0.05,      # 5% spoilage for perishables
    "apple": 0.03,
    "banana": 0.06,
    "mango": 0.04,
    "potato": 0.02,
    "onion": 0.02,
    "wheat": 0.005,
    "rice": 0.005,
    "coffee": 0.005,
    "default": 0.02,
}

# Mandi coordinates for distance calculation
MANDI_LOCATIONS = {
    "solan": (30.9045, 77.0967),
    "shimla": (31.1048, 77.1734),
    "kullu": (31.9579, 77.1090),
    "mandi": (31.7084, 76.9318),
    "ludhiana": (30.9010, 75.8573),
    "amritsar": (31.6340, 74.8723),
    "jalandhar": (31.3260, 75.5762),
    "patiala": (30.3398, 76.3869),
    "bathinda": (30.2110, 74.9455),
    "chandigarh": (30.7333, 76.7794),
    "bangalore": (12.9716, 77.5946),
    "mysore": (12.2958, 76.6394),
    "hubli": (15.3647, 75.1240),
    "chikmagalur": (13.3161, 75.7720),
    "hassan": (13.0068, 76.1003),
    "kodagu": (12.3375, 75.8069),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometres using Haversine formula."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Estimate road distance as 1.4x straight-line distance (India terrain factor)."""
    return _haversine_km(lat1, lon1, lat2, lon2) * 1.4


def calculate_mandi_profits(prices: list[dict], farmer_lat: float,
                            farmer_lon: float, crop: str,
                            quantity_qtl: float) -> list[dict]:
    """
    Calculate net profit for each mandi and return ranked list.

    Args:
        prices: List of {mandi, min_price, max_price, modal_price, date}
        farmer_lat, farmer_lon: Farmer's location
        crop: Crop name (for spoilage rate lookup)
        quantity_qtl: Quantity in quintals

    Returns:
        List of mandis ranked by net_profit (descending).
    """
    spoilage_rate = SPOILAGE_RATES.get(crop.lower(), SPOILAGE_RATES["default"])
    results = []

    for p in prices:
        mandi_name = p.get("mandi", "Unknown")
        modal_price = p.get("modal_price", 0)
        mandi_key = mandi_name.lower().strip()

        # Get mandi coordinates
        mandi_coords = MANDI_LOCATIONS.get(mandi_key)
        if mandi_coords:
            distance_km = _road_distance_km(farmer_lat, farmer_lon,
                                            mandi_coords[0], mandi_coords[1])
        else:
            distance_km = 50.0  # default assumption

        # Calculate costs
        gross_revenue = modal_price * quantity_qtl
        transport_cost = TRANSPORT_COST_PER_KM_PER_QTL * distance_km * quantity_qtl
        commission_rate = p.get("commission_rate", DEFAULT_COMMISSION_RATE)
        commission = gross_revenue * commission_rate
        spoilage_loss = gross_revenue * spoilage_rate * (distance_km / 100)  # increases with distance
        spoilage_loss = min(spoilage_loss, gross_revenue * 0.15)  # cap at 15%

        net_profit = gross_revenue - transport_cost - commission - spoilage_loss

        results.append({
            "mandi": mandi_name,
            "distance_km": round(distance_km, 1),
            "modal_price_per_qtl": modal_price,
            "gross_revenue": round(gross_revenue, 2),
            "transport_cost": round(transport_cost, 2),
            "commission": round(commission, 2),
            "commission_rate": commission_rate,
            "spoilage_loss": round(spoilage_loss, 2),
            "spoilage_rate": spoilage_rate,
            "net_profit": round(net_profit, 2),
            "net_price_per_qtl": round(net_profit / quantity_qtl, 2) if quantity_qtl > 0 else 0,
            "date": p.get("date", ""),
        })

    results.sort(key=lambda x: x["net_profit"], reverse=True)
    return results


@functions_framework.http
def calculate_profit(request):
    """
    HTTP Cloud Function entry point.

    JSON body:
        prices (list): Array of {mandi, min_price, max_price, modal_price, date}.
        lat (float): Farmer latitude.
        lon (float): Farmer longitude.
        crop (str): Crop name.
        quantity_qtl (float): Quantity in quintals.

    Returns:
        JSON with mandis ranked by net profit.
    """
    if not request.is_json:
        return json.dumps({"error": "Request must be JSON"}), 400, {"Content-Type": "application/json"}

    body = request.get_json(silent=True) or {}
    prices = body.get("prices", [])
    lat = float(body.get("lat", 0))
    lon = float(body.get("lon", 0))
    crop = body.get("crop", "tomato")
    quantity_qtl = float(body.get("quantity_qtl", 10))

    if not prices:
        return json.dumps({"error": "Missing 'prices' array"}), 400, {"Content-Type": "application/json"}
    if lat == 0 and lon == 0:
        return json.dumps({"error": "Missing 'lat' and 'lon'"}), 400, {"Content-Type": "application/json"}

    ranked = calculate_mandi_profits(prices, lat, lon, crop, quantity_qtl)

    return json.dumps({
        "crop": crop,
        "quantity_qtl": quantity_qtl,
        "farmer_location": {"lat": lat, "lon": lon},
        "ranked_mandis": ranked,
        "best_mandi": ranked[0] if ranked else None,
    }), 200, {"Content-Type": "application/json"}
