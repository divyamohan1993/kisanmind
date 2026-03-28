"""
Fetch Weather Cloud Function
=============================
Returns a 5-day forecast with hourly breakdown.
Uses Google Weather API when available, otherwise serves demo data.
"""

import json
import os
from datetime import datetime, timedelta

import functions_framework
import requests

GOOGLE_WEATHER_API_KEY = os.environ.get("GOOGLE_WEATHER_API_KEY", "")

# ---------------------------------------------------------------------------
# Demo forecast data for supported locations
# ---------------------------------------------------------------------------

def _generate_hourly(base_temp: float, humidity: int, wind: float,
                     condition: str, rain_mm: float = 0.0) -> list[dict]:
    """Generate 24-hour breakdown with realistic diurnal variation."""
    hours = []
    for h in range(0, 24, 3):
        temp_offset = -4 + (6 * (1 - abs(h - 14) / 14))  # peaks at 2 PM
        hours.append({
            "hour": f"{h:02d}:00",
            "temp_c": round(base_temp + temp_offset, 1),
            "humidity_pct": humidity + (10 if h < 6 or h > 20 else 0),
            "wind_kmh": round(wind + (2 if 10 <= h <= 16 else -1), 1),
            "condition": condition,
            "rain_mm": round(rain_mm * (0.3 if 6 <= h <= 10 else 0.1), 1),
        })
    return hours


def _make_demo_forecast(location_key: str) -> dict:
    """Build a 5-day demo forecast for known locations."""
    profiles = {
        "solan": {
            "location": "Solan, Himachal Pradesh",
            "lat": 30.9045, "lon": 77.0967,
            "days": [
                {"date_offset": 0, "high": 18, "low": 7, "condition": "partly_cloudy", "rain_mm": 0, "humidity": 55, "wind": 8},
                {"date_offset": 1, "high": 16, "low": 6, "condition": "cloudy", "rain_mm": 2.5, "humidity": 70, "wind": 12},
                {"date_offset": 2, "high": 14, "low": 5, "condition": "rain", "rain_mm": 12.0, "humidity": 85, "wind": 15},
                {"date_offset": 3, "high": 15, "low": 4, "condition": "partly_cloudy", "rain_mm": 1.0, "humidity": 65, "wind": 10},
                {"date_offset": 4, "high": 19, "low": 6, "condition": "sunny", "rain_mm": 0, "humidity": 50, "wind": 6},
            ],
        },
        "coorg": {
            "location": "Kodagu (Coorg), Karnataka",
            "lat": 12.3375, "lon": 75.8069,
            "days": [
                {"date_offset": 0, "high": 28, "low": 18, "condition": "partly_cloudy", "rain_mm": 0, "humidity": 65, "wind": 6},
                {"date_offset": 1, "high": 29, "low": 19, "condition": "sunny", "rain_mm": 0, "humidity": 60, "wind": 5},
                {"date_offset": 2, "high": 27, "low": 18, "condition": "thunderstorm", "rain_mm": 25.0, "humidity": 85, "wind": 20},
                {"date_offset": 3, "high": 26, "low": 17, "condition": "rain", "rain_mm": 15.0, "humidity": 90, "wind": 14},
                {"date_offset": 4, "high": 28, "low": 18, "condition": "partly_cloudy", "rain_mm": 3.0, "humidity": 70, "wind": 8},
            ],
        },
        "ludhiana": {
            "location": "Ludhiana, Punjab",
            "lat": 30.9010, "lon": 75.8573,
            "days": [
                {"date_offset": 0, "high": 32, "low": 18, "condition": "sunny", "rain_mm": 0, "humidity": 40, "wind": 10},
                {"date_offset": 1, "high": 33, "low": 19, "condition": "sunny", "rain_mm": 0, "humidity": 38, "wind": 12},
                {"date_offset": 2, "high": 30, "low": 17, "condition": "partly_cloudy", "rain_mm": 0, "humidity": 45, "wind": 14},
                {"date_offset": 3, "high": 28, "low": 16, "condition": "cloudy", "rain_mm": 5.0, "humidity": 60, "wind": 18},
                {"date_offset": 4, "high": 31, "low": 17, "condition": "sunny", "rain_mm": 0, "humidity": 42, "wind": 10},
            ],
        },
    }

    profile = profiles.get(location_key)
    if not profile:
        return {}

    today = datetime.utcnow().date()
    forecast_days = []
    for d in profile["days"]:
        date = today + timedelta(days=d["date_offset"])
        base_temp = (d["high"] + d["low"]) / 2
        forecast_days.append({
            "date": date.isoformat(),
            "high_c": d["high"],
            "low_c": d["low"],
            "condition": d["condition"],
            "rain_mm": d["rain_mm"],
            "humidity_pct": d["humidity"],
            "wind_kmh": d["wind"],
            "hourly": _generate_hourly(base_temp, d["humidity"], d["wind"],
                                       d["condition"], d["rain_mm"]),
        })

    return {
        "location": profile["location"],
        "lat": profile["lat"],
        "lon": profile["lon"],
        "source": "demo_data",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "forecast": forecast_days,
    }


def _resolve_location_key(lat: float, lon: float) -> str:
    """Map lat/lon to the nearest demo location key."""
    locations = {
        "solan": (30.9045, 77.0967),
        "coorg": (12.3375, 75.8069),
        "ludhiana": (30.9010, 75.8573),
    }
    best_key = "solan"
    best_dist = float("inf")
    for key, (rlat, rlon) in locations.items():
        dist = (lat - rlat) ** 2 + (lon - rlon) ** 2
        if dist < best_dist:
            best_dist = dist
            best_key = key
    return best_key


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

    # Try live API
    live = _fetch_from_google_weather(lat, lon)
    if live:
        return json.dumps(live), 200, {"Content-Type": "application/json"}

    # Fall back to demo data
    location_key = _resolve_location_key(lat, lon)
    forecast = _make_demo_forecast(location_key)
    if not forecast:
        return json.dumps({"error": "No forecast data available for this location"}), 404, {"Content-Type": "application/json"}

    return json.dumps(forecast), 200, {"Content-Type": "application/json"}
