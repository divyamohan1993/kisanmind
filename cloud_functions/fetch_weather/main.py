"""
Fetch Weather Cloud Function
=============================
Returns a 5-day forecast with hourly breakdown.
Uses Google Weather API. Returns an error when API is unavailable.
"""

import json
import os

import functions_framework
import requests

GOOGLE_WEATHER_API_KEY = os.environ.get("GOOGLE_WEATHER_API_KEY", "")

# ---------------------------------------------------------------------------
# Demo forecast data for supported locations
# ---------------------------------------------------------------------------

def _fetch_from_google_weather(lat: float, lon: float) -> dict | None:
    """Call Google Weather API. Returns dict or None."""
    if not GOOGLE_WEATHER_API_KEY:
        return None
    try:
        url = "https://weather.googleapis.com/v1/forecast/days:lookup"
        params = {
            "key": GOOGLE_WEATHER_API_KEY,
            "location.latitude": lat,
            "location.longitude": lon,
            "days": 5,
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


@functions_framework.http
def fetch_weather(request):
    """
    HTTP Cloud Function entry point.

    Query params or JSON body:
        lat (float): Latitude.
        lon (float): Longitude.

    Returns:
        JSON with 5-day forecast including hourly breakdown.
    """
    if request.is_json:
        body = request.get_json(silent=True) or {}
        lat = float(body.get("lat", 0))
        lon = float(body.get("lon", 0))
    else:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))

    if lat == 0 and lon == 0:
        return json.dumps({"error": "Missing 'lat' and 'lon' parameters"}), 400, {"Content-Type": "application/json"}

    # Fetch live weather data
    live = _fetch_from_google_weather(lat, lon)
    if live:
        return json.dumps(live), 200, {"Content-Type": "application/json"}

    return json.dumps({
        "error": "Unable to fetch weather data. Google Weather API unavailable or API key not configured.",
        "lat": lat,
        "lon": lon,
    }), 503, {"Content-Type": "application/json"}
