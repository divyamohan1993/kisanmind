"""
Geocode Cloud Function
======================
Converts a location string (village/city name) to lat, lon, formatted address.
Uses Google Maps Geocoding API with progressive fallback.
"""

import json
import os

import functions_framework
import requests

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Demo coordinates for common locations (work without API key)
DEMO_COORDINATES = {
    "solan": {"lat": 30.9045, "lon": 77.0967, "formatted_address": "Solan, Himachal Pradesh 173212, India"},
    "coorg": {"lat": 12.3375, "lon": 75.8069, "formatted_address": "Kodagu (Coorg), Karnataka 571201, India"},
    "kodagu": {"lat": 12.3375, "lon": 75.8069, "formatted_address": "Kodagu (Coorg), Karnataka 571201, India"},
    "ludhiana": {"lat": 30.9010, "lon": 75.8573, "formatted_address": "Ludhiana, Punjab 141001, India"},
    "shimla": {"lat": 31.1048, "lon": 77.1734, "formatted_address": "Shimla, Himachal Pradesh 171001, India"},
    "chandigarh": {"lat": 30.7333, "lon": 76.7794, "formatted_address": "Chandigarh 160001, India"},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946, "formatted_address": "Bengaluru, Karnataka 560001, India"},
    "bangalore": {"lat": 12.9716, "lon": 77.5946, "formatted_address": "Bengaluru, Karnataka 560001, India"},
    "amritsar": {"lat": 31.6340, "lon": 74.8723, "formatted_address": "Amritsar, Punjab 143001, India"},
    "mysore": {"lat": 12.2958, "lon": 76.6394, "formatted_address": "Mysuru, Karnataka 570001, India"},
    "mysuru": {"lat": 12.2958, "lon": 76.6394, "formatted_address": "Mysuru, Karnataka 570001, India"},
}

# State centroids as last-resort fallback
STATE_CENTROIDS = {
    "himachal pradesh": {"lat": 31.1048, "lon": 77.1734},
    "karnataka": {"lat": 15.3173, "lon": 75.7139},
    "punjab": {"lat": 31.1471, "lon": 75.3412},
    "haryana": {"lat": 29.0588, "lon": 76.0856},
    "uttar pradesh": {"lat": 26.8467, "lon": 80.9462},
    "maharashtra": {"lat": 19.7515, "lon": 75.7139},
    "tamil nadu": {"lat": 11.1271, "lon": 78.6569},
    "kerala": {"lat": 10.8505, "lon": 76.2711},
    "rajasthan": {"lat": 27.0238, "lon": 74.2179},
    "madhya pradesh": {"lat": 22.9734, "lon": 78.6569},
}


def _geocode_via_google(location: str) -> dict | None:
    """Call Google Maps Geocoding API. Returns dict or None on failure."""
    if not GOOGLE_MAPS_API_KEY:
        return None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": GOOGLE_MAPS_API_KEY, "region": "in"}
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            geo = result["geometry"]["location"]
            return {
                "lat": geo["lat"],
                "lon": geo["lng"],
                "formatted_address": result.get("formatted_address", location),
            }
    except Exception:
        pass
    return None


def _progressive_fallback(location: str) -> dict:
    """Try full location, then district-level, then state centroid."""
    lower = location.lower().strip()

    # Check demo coordinates first
    for key, coords in DEMO_COORDINATES.items():
        if key in lower:
            return coords

    # Try Google Maps API with full address
    result = _geocode_via_google(f"{location}, India")
    if result:
        return result

    # Try district-level (strip village/tehsil prefixes)
    parts = [p.strip() for p in location.split(",")]
    if len(parts) > 1:
        district_query = ", ".join(parts[1:])
        result = _geocode_via_google(f"{district_query}, India")
        if result:
            return result

    # Try state centroid
    for state, centroid in STATE_CENTROIDS.items():
        if state in lower:
            return {
                "lat": centroid["lat"],
                "lon": centroid["lon"],
                "formatted_address": f"{state.title()} (state centroid), India",
            }

    # Ultimate fallback: centre of India
    return {
        "lat": 22.9734,
        "lon": 78.6569,
        "formatted_address": "India (centre fallback)",
    }


@functions_framework.http
def geocode(request):
    """
    HTTP Cloud Function entry point.

    Query params or JSON body:
        location (str): Village, city, or district name.

    Returns:
        JSON with lat, lon, formatted_address.
    """
    # Parse input
    if request.is_json:
        body = request.get_json(silent=True) or {}
        location = body.get("location", "")
    else:
        location = request.args.get("location", "")

    if not location:
        return json.dumps({"error": "Missing 'location' parameter"}), 400, {"Content-Type": "application/json"}

    result = _progressive_fallback(location)

    return json.dumps({
        "location_query": location,
        **result,
    }), 200, {"Content-Type": "application/json"}
