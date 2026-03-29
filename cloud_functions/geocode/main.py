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


def _geocode_location(location: str) -> dict | None:
    """Try full location, then district-level via Google Maps API."""
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

    return None


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

    result = _geocode_location(location)

    if not result:
        return json.dumps({
            "error": f"Could not geocode '{location}'. Google Maps API key required.",
            "location_query": location,
        }), 503, {"Content-Type": "application/json"}

    return json.dumps({
        "location_query": location,
        **result,
    }), 200, {"Content-Type": "application/json"}
