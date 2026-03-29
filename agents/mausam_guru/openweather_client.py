"""
Weather API client for MausamGuru.

Primary:  Google Maps Weather API (Forecast hours:lookup)

The Google Weather API endpoint:
  POST https://weather.googleapis.com/v1/forecast/hours:lookup
  with GOOGLE_MAPS_API_KEY

If the API call fails (missing key, quota, network), returns an empty
forecast with source="error".
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .crop_weather_rules import HourlyForecast

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GOOGLE_WEATHER_BASE = "https://weather.googleapis.com/v1/forecast/hours:lookup"
FORECAST_HOURS = 120  # 5 days * 24 hours


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------

class ForecastResponse(BaseModel):
    """Structured forecast returned by the client."""
    location_name: str
    lat: float
    lon: float
    source: str = Field(
        ...,
        description="'google_weather_api' or 'error'"
    )
    fetched_at: str
    hourly: List[HourlyForecast]


# ---------------------------------------------------------------------------
# Google Weather API
# ---------------------------------------------------------------------------

def _fetch_google_weather(lat: float, lon: float, api_key: str) -> Optional[List[HourlyForecast]]:
    """
    Fetch hourly forecast from Google Maps Weather API.

    Endpoint: POST https://weather.googleapis.com/v1/forecast/hours:lookup
    Docs: https://developers.google.com/maps/documentation/weather/overview
    """
    url = GOOGLE_WEATHER_BASE
    params = {"key": api_key}
    payload = {
        "location": {
            "latitude": lat,
            "longitude": lon,
        },
        "hours": FORECAST_HOURS,
        "unitsSystem": "METRIC",
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, params=params, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Google Weather API request failed: %s", exc)
        return None

    # Parse the response into our HourlyForecast list
    hourly_list: List[HourlyForecast] = []
    forecast_hours = data.get("forecastHours", data.get("hours", []))

    for entry in forecast_hours:
        try:
            # Google Weather API returns nested structures
            dt_str = entry.get("interval", {}).get("startTime", "") or entry.get("dateTime", "")
            temp_info = entry.get("temperature", {})
            temp_c = temp_info.get("degrees", temp_info.get("value", 25.0))

            humidity_info = entry.get("humidity", {})
            humidity_pct = humidity_info.get("percent", humidity_info.get("value", 60.0))

            precip_info = entry.get("precipitation", {})
            rain_mm = precip_info.get("quantity", {}).get("millimeters", 0.0)
            if rain_mm == 0.0:
                rain_mm = precip_info.get("amount", {}).get("value", 0.0)

            wind_info = entry.get("wind", {})
            wind_speed = wind_info.get("speed", {})
            wind_kmh = wind_speed.get("kilometersPerHour", wind_speed.get("value", 0.0))

            desc = entry.get("weatherCondition", {}).get("description", {}).get("text", "")
            if not desc:
                desc = entry.get("weatherCondition", {}).get("type", "")

            hourly_list.append(HourlyForecast(
                datetime_iso=dt_str,
                temp_c=float(temp_c),
                humidity_pct=float(humidity_pct),
                rain_mm=float(rain_mm),
                wind_kmh=float(wind_kmh),
                description=str(desc),
            ))
        except (KeyError, TypeError, ValueError) as parse_err:
            logger.debug("Skipping unparseable forecast hour: %s", parse_err)
            continue

    if not hourly_list:
        logger.warning("Google Weather API returned no parseable hours")
        return None

    return hourly_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_forecast(lat: float, lon: float) -> ForecastResponse:
    """
    Fetch a 5-day hourly weather forecast for the given coordinates.

    Tries Google Weather API first. Returns empty forecast with
    source="error" if the API call fails or no key is configured.

    Returns:
        ForecastResponse with source attribution.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Attempt live API ---
    if api_key:
        hourly = _fetch_google_weather(lat, lon, api_key)
        if hourly:
            return ForecastResponse(
                location_name=f"Location ({lat:.4f}, {lon:.4f})",
                lat=lat,
                lon=lon,
                source="google_weather_api",
                fetched_at=now_iso,
                hourly=hourly,
            )
        logger.warning(
            "Google Weather API failed for (%.4f, %.4f); returning empty forecast.",
            lat, lon,
        )
    else:
        logger.info(
            "GOOGLE_MAPS_API_KEY not set — returning empty forecast for (%.4f, %.4f).",
            lat, lon,
        )

    # No fallback — return empty forecast with error indication
    return ForecastResponse(
        location_name=f"Location ({lat:.4f}, {lon:.4f})",
        lat=lat,
        lon=lon,
        source="error",
        fetched_at=now_iso,
        hourly=[],
    )
