"""
Crop-Weather Rule Matrix for MausamGuru.

Translates raw weather forecast data into farming-specific DO / DON'T / WARNING
advisories based on crop type, growth stage, and weather thresholds drawn from
the KisanMind architecture document.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AdvisoryType(str, Enum):
    DO = "do"
    DONT = "dont"
    WARNING = "warning"


class Urgency(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Advisory(BaseModel):
    """A single weather-driven farming advisory."""
    type: AdvisoryType
    message: str
    urgency: Urgency
    day: int = Field(..., description="Forecast day number (1-5)")


class HourlyForecast(BaseModel):
    """One hour of forecast data."""
    datetime_iso: str
    temp_c: float
    humidity_pct: float
    rain_mm: float = 0.0
    wind_kmh: float = 0.0
    description: str = ""


class DailyForecastSummary(BaseModel):
    """Aggregated daily numbers derived from hourly data."""
    day: int
    date: str
    temp_min_c: float
    temp_max_c: float
    humidity_avg_pct: float
    rain_total_mm: float
    wind_max_kmh: float
    description: str


# ---------------------------------------------------------------------------
# Crop threshold definitions
# ---------------------------------------------------------------------------

# Each crop maps to a dict of rule callables.  Every callable receives a
# DailyForecastSummary and a growth_stage string, and returns a list of
# Advisory items (possibly empty).

def _tomato_rules(day: DailyForecastSummary, growth_stage: str) -> List[Advisory]:
    advisories: List[Advisory] = []

    # Temperature
    if day.temp_min_c < 10:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Min temperature {day.temp_min_c:.1f}°C — "
                "frost damage risk for tomatoes. Cover plants with mulch or plastic sheets tonight."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    if day.temp_max_c > 40:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Max temperature {day.temp_max_c:.1f}°C — "
                "flower drop likely in tomatoes. Provide shade nets if possible."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    # Rain
    if day.rain_total_mm > 20:
        advisories.append(Advisory(
            type=AdvisoryType.DO,
            message=(
                f"Day {day.day} ({day.date}): Heavy rain expected ({day.rain_total_mm:.0f} mm). "
                "Harvest all ripe tomatoes immediately before rain starts."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    if day.rain_total_mm > 5:
        advisories.append(Advisory(
            type=AdvisoryType.DONT,
            message=(
                f"Day {day.day} ({day.date}): Rain forecasted ({day.rain_total_mm:.0f} mm). "
                "Do NOT spray pesticides or fungicides — they will wash off."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))
        advisories.append(Advisory(
            type=AdvisoryType.DONT,
            message=(
                f"Day {day.day} ({day.date}): Skip irrigation today — "
                "rain will provide adequate moisture."
            ),
            urgency=Urgency.LOW,
            day=day.day,
        ))

    # Humidity
    if day.humidity_avg_pct > 85:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): High humidity ({day.humidity_avg_pct:.0f}%). "
                "Fungal disease risk (early/late blight) for tomatoes. "
                "Apply preventive fungicide spray before the wet spell, NOT during."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Wind
    if day.wind_max_kmh > 40:
        advisories.append(Advisory(
            type=AdvisoryType.DO,
            message=(
                f"Day {day.day} ({day.date}): Strong winds expected ({day.wind_max_kmh:.0f} km/h). "
                "Stake and support tomato plants securely to prevent snapping."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Drainage check before rain
    if day.rain_total_mm > 10:
        advisories.append(Advisory(
            type=AdvisoryType.DO,
            message=(
                f"Day {day.day} ({day.date}): Ensure drainage channels around tomato beds "
                "are clear — waterlogging causes root rot."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    return advisories


def _wheat_rules(day: DailyForecastSummary, growth_stage: str) -> List[Advisory]:
    advisories: List[Advisory] = []

    # Temperature
    if day.temp_min_c < 5 and growth_stage in ("flowering", "heading", "grain_filling"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Min temperature {day.temp_min_c:.1f}°C during "
                f"{growth_stage} stage — potential yield loss for wheat. "
                "Light irrigation in the evening can raise field temperature by 1-2°C."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    # Rain
    if day.rain_total_mm > 30 and growth_stage in ("harvest", "grain_filling", "maturity"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Heavy rain ({day.rain_total_mm:.0f} mm) "
                f"during {growth_stage} — grain damage and sprouting risk. "
                "Harvest immediately if crop is mature enough."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    if day.rain_total_mm > 5:
        advisories.append(Advisory(
            type=AdvisoryType.DONT,
            message=(
                f"Day {day.day} ({day.date}): Do NOT apply urea or fertiliser — "
                "rain will cause nitrogen leaching."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Humidity
    if day.humidity_avg_pct > 90:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Very high humidity ({day.humidity_avg_pct:.0f}%). "
                "Yellow/brown rust risk in wheat. Scout for pustules on leaves."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Wind
    if day.wind_max_kmh > 50:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Gale-force winds ({day.wind_max_kmh:.0f} km/h). "
                "Lodging risk for wheat — no preventive action possible at this stage."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    return advisories


def _rice_rules(day: DailyForecastSummary, growth_stage: str) -> List[Advisory]:
    advisories: List[Advisory] = []

    # Temperature
    if day.temp_min_c < 15:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Cold stress risk for rice "
                f"(min {day.temp_min_c:.1f}°C). Maintain 5-7 cm standing water "
                "in paddy to buffer temperature."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    # Rain — rice tolerates water well during vegetative stage
    if day.rain_total_mm > 50 and growth_stage in ("flowering", "grain_filling", "maturity"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Very heavy rain ({day.rain_total_mm:.0f} mm). "
                "Ensure bund outlets are working to prevent excess flooding during "
                f"{growth_stage} stage."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    if day.rain_total_mm > 5:
        advisories.append(Advisory(
            type=AdvisoryType.DONT,
            message=(
                f"Day {day.day} ({day.date}): Do NOT spray herbicides or pesticides before rain."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Wind
    if day.wind_max_kmh > 30 and growth_stage in ("flowering", "grain_filling"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Winds ({day.wind_max_kmh:.0f} km/h) risk "
                "panicle damage during flowering/grain filling."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    return advisories


def _apple_rules(day: DailyForecastSummary, growth_stage: str) -> List[Advisory]:
    advisories: List[Advisory] = []

    # Temperature — frost
    if day.temp_min_c < -2:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Severe frost expected ({day.temp_min_c:.1f}°C). "
                "Use smudge pots, wind machines, or sprinkler irrigation for frost protection "
                "on apple trees."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    elif day.temp_min_c < 2 and growth_stage in ("flowering", "fruit_set"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Near-freezing temperature ({day.temp_min_c:.1f}°C). "
                "Monitor apple blossoms closely — light frost can damage flowers."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Rain
    if day.rain_total_mm > 25 and growth_stage in ("fruit_development", "maturity", "harvest"):
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Heavy rain ({day.rain_total_mm:.0f} mm). "
                "Fruit cracking risk for apples. Harvest mature fruit before rain."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    # Humidity — scab
    if day.humidity_avg_pct > 80:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): High humidity ({day.humidity_avg_pct:.0f}%). "
                "Apple scab risk — apply protective fungicide in dry window before rain."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Wind
    if day.wind_max_kmh > 60:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Very strong winds ({day.wind_max_kmh:.0f} km/h). "
                "Fruit drop risk for apples. Harvest what is ready."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    return advisories


def _coffee_rules(day: DailyForecastSummary, growth_stage: str) -> List[Advisory]:
    advisories: List[Advisory] = []

    # Temperature
    if day.temp_min_c < 10:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Low temperature ({day.temp_min_c:.1f}°C). "
                "Coffee berry damage risk — shade trees help buffer temperature."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))

    # Rain
    if day.rain_total_mm > 50:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Very heavy rain ({day.rain_total_mm:.0f} mm). "
                "Root rot risk for coffee. Ensure drainage in plantation is clear."
            ),
            urgency=Urgency.HIGH,
            day=day.day,
        ))
    if day.rain_total_mm > 5:
        advisories.append(Advisory(
            type=AdvisoryType.DONT,
            message=(
                f"Day {day.day} ({day.date}): Rain expected — "
                "do NOT spray fungicides or pesticides on coffee today."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Humidity — too low means irrigation needed
    if day.humidity_avg_pct < 40:
        advisories.append(Advisory(
            type=AdvisoryType.DO,
            message=(
                f"Day {day.day} ({day.date}): Low humidity ({day.humidity_avg_pct:.0f}%). "
                "Coffee needs irrigation — soil moisture likely dropping."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    # Wind
    if day.wind_max_kmh > 40:
        advisories.append(Advisory(
            type=AdvisoryType.WARNING,
            message=(
                f"Day {day.day} ({day.date}): Strong winds ({day.wind_max_kmh:.0f} km/h). "
                "Branch damage risk for coffee. Check windbreaks are intact."
            ),
            urgency=Urgency.MEDIUM,
            day=day.day,
        ))

    return advisories


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CROP_RULES = {
    "tomato": _tomato_rules,
    "wheat": _wheat_rules,
    "rice": _rice_rules,
    "apple": _apple_rules,
    "coffee": _coffee_rules,
}

SUPPORTED_CROPS = list(CROP_RULES.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def summarise_daily(hourly_forecasts: List[HourlyForecast], day_number: int) -> DailyForecastSummary:
    """Aggregate a list of hourly forecasts (for one day) into a daily summary."""
    if not hourly_forecasts:
        raise ValueError("No hourly data to summarise")

    temps = [h.temp_c for h in hourly_forecasts]
    humidities = [h.humidity_pct for h in hourly_forecasts]
    winds = [h.wind_kmh for h in hourly_forecasts]
    rain_total = sum(h.rain_mm for h in hourly_forecasts)

    # Pick the most common description, or the first one
    descriptions = [h.description for h in hourly_forecasts if h.description]
    description = max(set(descriptions), key=descriptions.count) if descriptions else "N/A"

    date_str = hourly_forecasts[0].datetime_iso[:10]

    return DailyForecastSummary(
        day=day_number,
        date=date_str,
        temp_min_c=min(temps),
        temp_max_c=max(temps),
        humidity_avg_pct=sum(humidities) / len(humidities),
        rain_total_mm=rain_total,
        wind_max_kmh=max(winds),
        description=description,
    )


def generate_advisories(
    daily_summaries: List[DailyForecastSummary],
    crop: str,
    growth_stage: str = "vegetative",
) -> List[Advisory]:
    """
    Apply the crop-weather rule matrix to daily forecast summaries.

    Args:
        daily_summaries: List of DailyForecastSummary (typically 5 days).
        crop: Crop name (must be in SUPPORTED_CROPS).
        growth_stage: Current growth stage (e.g. vegetative, flowering,
                      harvest, grain_filling, maturity, fruit_development,
                      fruit_set, heading).

    Returns:
        Sorted list of Advisory objects (highest urgency first).
    """
    crop_lower = crop.lower().strip()
    if crop_lower not in CROP_RULES:
        raise ValueError(
            f"Unsupported crop '{crop}'. Supported: {SUPPORTED_CROPS}"
        )

    rule_fn = CROP_RULES[crop_lower]
    all_advisories: List[Advisory] = []

    for day_summary in daily_summaries:
        all_advisories.extend(rule_fn(day_summary, growth_stage.lower().strip()))

    # Sort: high urgency first, then by day
    urgency_order = {Urgency.HIGH: 0, Urgency.MEDIUM: 1, Urgency.LOW: 2}
    all_advisories.sort(key=lambda a: (urgency_order[a.urgency], a.day))

    return all_advisories
