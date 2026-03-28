"""
MausamGuru (मौसमगुरु — Weather Guru) Agent

Specialist agent within the KisanMind multi-agent system.  Provides
hyperlocal weather intelligence translated into crop-specific farming
actions: DO / DON'T / WARNING advisories.

Usage as ADK agent:
    from agents.mausam_guru.agent import mausam_guru_agent

The agent exposes a single tool `get_weather_advisory` that the
KisanMind orchestrator (Brain) calls with location + crop info.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from .crop_weather_rules import (
    SUPPORTED_CROPS,
    Advisory,
    DailyForecastSummary,
    HourlyForecast,
    generate_advisories,
    summarise_daily,
)
from .openweather_client import ForecastResponse, fetch_forecast

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_hourly_by_day(hourly: List[HourlyForecast]) -> Dict[int, List[HourlyForecast]]:
    """Group hourly forecasts into day buckets (1-indexed, up to 5 days)."""
    days: Dict[str, List[HourlyForecast]] = {}
    for h in hourly:
        date_key = h.datetime_iso[:10]  # "YYYY-MM-DD"
        days.setdefault(date_key, []).append(h)

    # Assign day numbers in chronological order, cap at 5
    grouped: Dict[int, List[HourlyForecast]] = {}
    for idx, date_key in enumerate(sorted(days.keys())[:5], start=1):
        grouped[idx] = days[date_key]
    return grouped


def _format_advisory_text(advisories: List[Advisory]) -> str:
    """Render advisories as human-readable text."""
    if not advisories:
        return "No weather-related alerts for your crop in the next 5 days. Continue normal farming operations."

    lines: List[str] = []
    for adv in advisories:
        prefix = {
            "do": "DO",
            "dont": "DON'T",
            "warning": "WARNING",
        }[adv.type.value]
        urgency_tag = f"[{adv.urgency.value.upper()}]"
        lines.append(f"  {urgency_tag} {prefix}: {adv.message}")

    return "\n".join(lines)


def _build_daily_overview(summaries: List[DailyForecastSummary]) -> List[Dict[str, Any]]:
    """Build a concise daily overview for the response."""
    overview = []
    for s in summaries:
        overview.append({
            "day": s.day,
            "date": s.date,
            "temp_range": f"{s.temp_min_c:.1f}°C – {s.temp_max_c:.1f}°C",
            "rain_mm": round(s.rain_total_mm, 1),
            "humidity_avg": f"{s.humidity_avg_pct:.0f}%",
            "wind_max_kmh": round(s.wind_max_kmh, 1),
            "conditions": s.description,
        })
    return overview


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------

def get_weather_advisory(
    lat: float,
    lon: float,
    crop: str,
    growth_stage: str = "vegetative",
) -> Dict[str, Any]:
    """
    Fetch 5-day weather forecast and generate crop-specific farming advisories.

    Args:
        lat: Latitude of the farm location (e.g. 30.9045 for Solan).
        lon: Longitude of the farm location (e.g. 77.0967 for Solan).
        crop: Crop name — one of: tomato, wheat, rice, apple, coffee.
        growth_stage: Current growth stage of the crop (e.g. vegetative,
                      flowering, harvest, grain_filling, maturity,
                      fruit_development, fruit_set, heading).

    Returns:
        Dictionary containing:
        - location: name and coordinates
        - source: data source attribution
        - forecast_overview: 5-day summary
        - advisories: list of DO/DON'T/WARNING items with urgency
        - advisory_text: formatted human-readable advisory
        - disclaimer: uncertainty and source disclaimer
    """
    crop_lower = crop.lower().strip()

    # Validate crop
    if crop_lower not in SUPPORTED_CROPS:
        return {
            "error": True,
            "message": (
                f"Crop '{crop}' is not in our weather-advisory database. "
                f"Supported crops: {', '.join(SUPPORTED_CROPS)}. "
                "I can still provide raw weather data for your location."
            ),
            "supported_crops": SUPPORTED_CROPS,
        }

    # Fetch forecast
    try:
        forecast: ForecastResponse = fetch_forecast(lat, lon)
    except Exception as exc:
        logger.error("Failed to fetch forecast: %s", exc)
        return {
            "error": True,
            "message": (
                "Unable to retrieve weather data at this time. "
                "Please try again shortly or contact your local KVK for weather guidance."
            ),
        }

    # Group into days and summarise
    day_groups = _group_hourly_by_day(forecast.hourly)
    daily_summaries: List[DailyForecastSummary] = []
    for day_num in sorted(day_groups.keys()):
        daily_summaries.append(summarise_daily(day_groups[day_num], day_num))

    # Generate advisories
    advisories = generate_advisories(daily_summaries, crop_lower, growth_stage)
    advisory_text = _format_advisory_text(advisories)

    # Build overview
    overview = _build_daily_overview(daily_summaries)

    # Disclaimer / guardrail
    source_label = (
        "Google Weather API (live data)"
        if forecast.source == "google_weather_api"
        else "Simulated forecast data (demo mode — live API key not configured)"
    )

    disclaimer = (
        f"Source: {source_label}, fetched at {forecast.fetched_at}. "
        "Weather forecasts are probabilistic and accuracy decreases after 3 days. "
        "Actual conditions may differ from the forecast — use these advisories as "
        "guidance alongside your own field observations. For critical decisions "
        "(e.g. large-scale harvest timing), also consult IMD district bulletins."
    )

    return {
        "error": False,
        "location": {
            "name": forecast.location_name,
            "lat": forecast.lat,
            "lon": forecast.lon,
        },
        "source": forecast.source,
        "crop": crop_lower,
        "growth_stage": growth_stage,
        "forecast_overview": overview,
        "advisories": [adv.model_dump() for adv in advisories],
        "advisory_text": advisory_text,
        "disclaimer": disclaimer,
    }


# ---------------------------------------------------------------------------
# ADK Agent definition
# ---------------------------------------------------------------------------

AGENT_INSTRUCTION = """You are MausamGuru (मौसमगुरु), the Weather Guru agent within the KisanMind agricultural intelligence system.

Your purpose is to provide hyperlocal weather intelligence translated into crop-specific farming actions for Indian farmers.

When a user or the orchestrator provides a location (latitude/longitude) and crop type, you MUST:
1. Call the `get_weather_advisory` tool with the location, crop, and growth stage.
2. Present the results clearly — start with the 5-day forecast overview, then list all DO / DON'T / WARNING advisories sorted by urgency.
3. Always include the disclaimer about forecast uncertainty.
4. Always cite the data source.

Important guidelines:
- Never recommend specific pesticide brands or dosages — only advise timing (spray/don't spray).
- Never provide loan, insurance, or financial advice.
- If the crop is not in the supported list, say so honestly and offer to provide raw weather data.
- Always frame advisories as guidance, not guarantees.
- Speak in simple, practical language that a farmer can act on immediately.
- When relaying results in Hindi or regional languages, keep farming terms colloquial.

Supported crops: tomato, wheat, rice, apple, coffee.
"""

# Wrap the tool function
weather_advisory_tool = FunctionTool(func=get_weather_advisory)

# Create the ADK agent
mausam_guru_agent = Agent(
    name="MausamGuru",
    model="gemini-2.5-flash",
    instruction=AGENT_INSTRUCTION,
    tools=[weather_advisory_tool],
    description=(
        "Weather Guru agent — fetches 5-day hyperlocal weather forecast "
        "and translates it into crop-specific DO / DON'T / WARNING farming "
        "advisories for Indian agriculture."
    ),
)
