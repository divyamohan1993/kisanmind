"""
Weather API client for MausamGuru.

Primary:  Google Maps Weather API (Forecast hours:lookup)
Fallback: Simulated realistic forecast data for demo locations.

The Google Weather API endpoint:
  POST https://weather.googleapis.com/v1/forecast/hours:lookup
  with GOOGLE_MAPS_API_KEY

If the API call fails (missing key, quota, network), we fall back to
pre-built demo forecasts for Solan, Coorg, and Punjab so the agent
always returns a result.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

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
        description="'google_weather_api' or 'simulated_demo_data'"
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
# Demo / simulated data
# ---------------------------------------------------------------------------

def _make_hourly(
    base_date: datetime,
    hour: int,
    temp_c: float,
    humidity_pct: float,
    rain_mm: float,
    wind_kmh: float,
    description: str,
) -> HourlyForecast:
    dt = base_date + timedelta(hours=hour)
    return HourlyForecast(
        datetime_iso=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        temp_c=temp_c,
        humidity_pct=humidity_pct,
        rain_mm=rain_mm,
        wind_kmh=wind_kmh,
        description=description,
    )


def _generate_day_hours(
    base_date: datetime,
    day_offset: int,
    temp_min: float,
    temp_max: float,
    humidity_base: float,
    rain_hours: Dict[int, float],
    wind_base: float,
    description: str,
) -> List[HourlyForecast]:
    """Generate 24 hourly entries for a single day with realistic diurnal variation."""
    day_start = base_date + timedelta(days=day_offset)
    hours: List[HourlyForecast] = []

    for h in range(24):
        # Diurnal temperature curve: coldest at 5 AM, hottest at 14:00
        if h <= 5:
            t_frac = 0.0
        elif h <= 14:
            t_frac = (h - 5) / 9.0
        else:
            t_frac = 1.0 - (h - 14) / 10.0
        temp = temp_min + (temp_max - temp_min) * max(0, min(1, t_frac))

        # Humidity inversely correlated with temperature
        humidity = humidity_base + (1.0 - t_frac) * 10
        humidity = min(100, max(20, humidity))

        rain = rain_hours.get(h, 0.0)
        wind = wind_base + (5 if 10 <= h <= 16 else 0)

        hours.append(_make_hourly(
            day_start, h, round(temp, 1), round(humidity, 1),
            round(rain, 1), round(wind, 1), description,
        ))

    return hours


# --- Solan, Himachal Pradesh (30.9045, 77.0967) — Tomato region ---

def _demo_solan() -> List[HourlyForecast]:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    all_hours: List[HourlyForecast] = []

    day_configs = [
        # (day_offset, temp_min, temp_max, humidity, rain_hours, wind, desc)
        (0, 12.0, 28.0, 65.0, {}, 8.0, "Clear sky"),
        (1, 14.0, 26.0, 72.0, {}, 10.0, "Partly cloudy"),
        (2, 11.0, 22.0, 82.0, {10: 3.0, 11: 5.0, 12: 4.0, 13: 3.0}, 15.0, "Light rain"),
        (3, 10.0, 20.0, 88.0, {8: 4.0, 9: 6.0, 10: 5.0, 11: 3.0, 14: 2.0}, 18.0, "Moderate rain"),
        (4, 13.0, 25.0, 68.0, {}, 10.0, "Clear sky"),
    ]

    for cfg in day_configs:
        all_hours.extend(_generate_day_hours(base, *cfg))

    return all_hours


# --- Coorg (Kodagu), Karnataka (12.4244, 75.7382) — Coffee region ---

def _demo_coorg() -> List[HourlyForecast]:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    all_hours: List[HourlyForecast] = []

    day_configs = [
        (0, 18.0, 30.0, 75.0, {15: 2.0, 16: 3.0}, 12.0, "Partly cloudy"),
        (1, 19.0, 31.0, 78.0, {14: 5.0, 15: 8.0, 16: 6.0, 17: 3.0}, 14.0, "Thunderstorm"),
        (2, 17.0, 28.0, 85.0, {9: 4.0, 10: 6.0, 11: 8.0, 12: 10.0, 13: 8.0, 14: 6.0, 15: 5.0, 16: 4.0}, 20.0, "Heavy rain"),
        (3, 18.0, 27.0, 82.0, {10: 3.0, 11: 4.0, 12: 3.0}, 16.0, "Light rain"),
        (4, 19.0, 32.0, 70.0, {}, 10.0, "Sunny"),
    ]

    for cfg in day_configs:
        all_hours.extend(_generate_day_hours(base, *cfg))

    return all_hours


# --- Punjab (Ludhiana) (30.9010, 75.8573) — Wheat region ---

def _demo_punjab() -> List[HourlyForecast]:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    all_hours: List[HourlyForecast] = []

    day_configs = [
        (0, 8.0, 24.0, 55.0, {}, 12.0, "Clear sky"),
        (1, 6.0, 22.0, 60.0, {}, 15.0, "Haze"),
        (2, 4.0, 18.0, 70.0, {12: 2.0, 13: 3.0}, 20.0, "Overcast"),
        (3, 5.0, 16.0, 92.0, {8: 5.0, 9: 8.0, 10: 10.0, 11: 8.0, 12: 5.0, 13: 3.0}, 25.0, "Heavy rain"),
        (4, 7.0, 20.0, 65.0, {}, 18.0, "Partly cloudy"),
    ]

    for cfg in day_configs:
        all_hours.extend(_generate_day_hours(base, *cfg))

    return all_hours


# Registry: (lat, lon) approximate bounding → demo data generator
DEMO_LOCATIONS: List[Tuple[str, float, float, float, callable]] = [
    # (name, lat_center, lon_center, radius_deg, generator)
    ("Solan, Himachal Pradesh", 30.9045, 77.0967, 1.0, _demo_solan),
    ("Coorg (Kodagu), Karnataka", 12.4244, 75.7382, 1.0, _demo_coorg),
    ("Ludhiana, Punjab", 30.9010, 75.8573, 1.0, _demo_punjab),
]


def _find_demo(lat: float, lon: float) -> Optional[Tuple[str, List[HourlyForecast]]]:
    """Return demo data if the coordinates are near a known demo location."""
    for name, lat_c, lon_c, radius, gen_fn in DEMO_LOCATIONS:
        if abs(lat - lat_c) <= radius and abs(lon - lon_c) <= radius:
            return name, gen_fn()
    return None


def _generic_demo(lat: float, lon: float) -> Tuple[str, List[HourlyForecast]]:
    """Generate a generic mild-weather demo for any unknown location."""
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    all_hours: List[HourlyForecast] = []

    day_configs = [
        (0, 18.0, 32.0, 60.0, {}, 10.0, "Clear sky"),
        (1, 19.0, 33.0, 58.0, {}, 12.0, "Sunny"),
        (2, 17.0, 30.0, 68.0, {14: 3.0, 15: 4.0}, 14.0, "Partly cloudy"),
        (3, 16.0, 28.0, 75.0, {10: 2.0, 11: 3.0, 12: 2.0}, 10.0, "Light rain"),
        (4, 18.0, 31.0, 62.0, {}, 8.0, "Clear sky"),
    ]

    for cfg in day_configs:
        all_hours.extend(_generate_day_hours(base, *cfg))

    return f"Location ({lat:.2f}, {lon:.2f})", all_hours


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_forecast(lat: float, lon: float) -> ForecastResponse:
    """
    Fetch a 5-day hourly weather forecast for the given coordinates.

    Tries Google Weather API first.  Falls back to simulated demo data
    if the API call fails or no key is configured.

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
            "Google Weather API failed for (%.4f, %.4f); falling back to demo data.",
            lat, lon,
        )
    else:
        logger.info(
            "GOOGLE_MAPS_API_KEY not set — using simulated demo data for (%.4f, %.4f).",
            lat, lon,
        )

    # --- Fallback: demo / simulated data ---
    demo_result = _find_demo(lat, lon)
    if demo_result:
        name, hourly = demo_result
    else:
        name, hourly = _generic_demo(lat, lon)

    return ForecastResponse(
        location_name=name,
        lat=lat,
        lon=lon,
        source="simulated_demo_data",
        fetched_at=now_iso,
        hourly=hourly,
    )
