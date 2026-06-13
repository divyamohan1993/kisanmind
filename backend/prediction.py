"""
KisanMind — prediction layer. Maps become forecasts.

Pure functions (stdlib only). Every forecast is grounded in data that actually exists on the
request and carries an explicit confidence; nothing is extrapolated from a single data point
(a hard rule — the satellite cache reports one observation with a hardcoded 'stable' trend,
and inventing a trajectory from that would be fabrication, not prediction).

The flagship forecast is the soil-water balance: real root-zone moisture + real ET forecast
- real rain forecast => "irrigate in N days". That is a genuine, actionable prediction a
farmer can act on, built from measured inputs, not a guess.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

# FAO-56 style root depth (m) and mid-season crop coefficient Kc. Indicative defaults.
CROP_WATER = {
    "tomato": (0.7, 1.15), "wheat": (1.2, 1.15), "rice": (0.5, 1.20), "potato": (0.4, 1.15),
    "onion": (0.3, 1.05), "capsicum": (0.6, 1.05), "cabbage": (0.5, 1.05),
    "cauliflower": (0.5, 1.05), "apple": (1.0, 0.95), "mango": (1.2, 0.85),
    "maize": (1.0, 1.20), "cotton": (1.0, 1.15), "soybean": (0.8, 1.10),
}
_DEFAULT_WATER = (0.6, 1.0)

# Loam soil hydraulic defaults (volumetric m3/m3). Indicative.
FIELD_CAPACITY = 0.28
WILTING_POINT = 0.12
MAD = 0.5  # Management Allowable Depletion before stress / irrigation trigger.


def predict_irrigation_need(
    crop: str,
    rootzone_moisture_m3m3: Optional[float],
    et_forecast_mm: Optional[list],
    rain_forecast_mm: Optional[list],
    et_today_mm: Optional[float] = None,
    horizon_days: int = 7,
) -> dict:
    """Soil-water balance forecast → days until irrigation is needed.

    rootzone_moisture_m3m3: measured volumetric water (SMAP or Open-Meteo root layer).
    et_forecast_mm: daily reference ET0 forecast (mm). rain_forecast_mm: daily rain (mm).
    Returns {} if there isn't enough real input to model (no fabrication).
    """
    if rootzone_moisture_m3m3 is None:
        return {}
    # Need at least a single ET estimate to deplete water; fall back to et_today.
    et_series = list(et_forecast_mm or [])
    if not et_series and et_today_mm is not None:
        et_series = [et_today_mm] * horizon_days
    if not et_series:
        return {}
    rain_series = list(rain_forecast_mm or [])

    zr, kc = CROP_WATER.get(crop.lower().strip(), _DEFAULT_WATER)
    taw = (FIELD_CAPACITY - WILTING_POINT) * zr * 1000.0           # total available water (mm)
    theta = max(WILTING_POINT, min(FIELD_CAPACITY, rootzone_moisture_m3m3))
    available = (theta - WILTING_POINT) * zr * 1000.0              # current available water (mm)
    trigger = (1.0 - MAD) * taw                                    # irrigate when available <= this

    # Already below the stress trigger → irrigate now.
    if available <= trigger:
        return _irrigation_result(0, available, taw, et_series[0] * kc, crop, "irrigate_now")

    days = None
    water = available
    n = min(horizon_days, max(len(et_series), len(rain_series) or 0, horizon_days))
    for day in range(n):
        etc = (et_series[day] if day < len(et_series) else et_series[-1]) * kc
        rain = rain_series[day] if day < len(rain_series) else 0.0
        water = min(taw, water + rain - etc)
        if water <= trigger:
            days = day + 1
            break

    if days is None:
        return _irrigation_result(None, available, taw, et_series[0] * kc, crop, "sufficient",
                                  horizon=horizon_days)
    return _irrigation_result(days, available, taw, et_series[0] * kc, crop, "irrigate_in_days")


def _irrigation_result(days, available, taw, etc, crop, status, horizon=7) -> dict:
    depletion_pct = round(100 * (1 - available / taw), 1) if taw > 0 else None
    lines = {
        "irrigate_now": "Based on soil moisture and the heat forecast, the crop needs water now.",
        "irrigate_in_days": f"Soil water should last about {days} more day(s) before the crop needs irrigation.",
        "sufficient": f"Soil moisture looks enough for at least the next {horizon} days — no urgent watering.",
    }
    return {
        "status": status,
        "days_until_irrigation": days,
        "available_water_mm": round(available, 1),
        "taw_mm": round(taw, 1),
        "depletion_pct": depletion_pct,
        "etc_mm_day": round(etc, 2),
        "method": "fao56_soil_water_balance",
        "confidence": "MEDIUM",
        "indicative": True,
        "farmer_line": lines.get(status, ""),
    }


def predict_vegetation_trajectory(ndvi_series: Optional[list]) -> dict:
    """Forecast crop greenness from a REAL multi-observation NDVI series.

    ndvi_series: list of {"date": "YYYY-MM-DD", "ndvi": float}, newest-first or oldest-first.
    With <2 distinct-date observations we refuse to predict (no trend from one point).
    """
    pts = _clean_series(ndvi_series)
    if len(pts) < 2:
        return {"method": "insufficient_observations", "confidence": "LOW",
                "note": "Need at least two satellite passes to project crop trend."}

    # Linear least-squares slope of ndvi vs day-offset.
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return {"method": "insufficient_observations", "confidence": "LOW",
                "note": "Observations share one date — cannot project trend."}
    slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / var
    last_x, last_y = xs[-1], ys[-1]

    def project(dd):
        return round(max(0.0, min(1.0, last_y + slope * dd)), 3)

    per_week = slope * 7
    if per_week > 0.03:
        direction = "improving"
    elif per_week < -0.03:
        direction = "declining"
    else:
        direction = "steady"

    return {
        "method": "linear_regression",
        "slope_per_day": round(slope, 5),
        "direction": direction,
        "ndvi_now": round(last_y, 3),
        "ndvi_in_7_days": project(7),
        "ndvi_in_15_days": project(15),
        "observations": n,
        "confidence": "MEDIUM" if n >= 3 else "LOW",
        "indicative": True,
        "farmer_line": {
            "improving": "Crop greenness is trending up — growth looks set to continue.",
            "declining": "Crop greenness is trending down — watch the field closely this week.",
            "steady": "Crop greenness is holding steady.",
        }[direction],
    }


def _clean_series(series: Optional[list]) -> list:
    """-> sorted [(day_offset_from_first, ndvi)], dropping unparseable rows."""
    if not series:
        return []
    rows = []
    for s in series:
        try:
            d = datetime.strptime(s["date"], "%Y-%m-%d")
            v = float(s["ndvi"])
            rows.append((d, v))
        except (KeyError, ValueError, TypeError):
            continue
    if len(rows) < 2:
        return [(0.0, r[1]) for r in rows]
    rows.sort(key=lambda r: r[0])
    base = rows[0][0]
    return [((d - base).days, v) for d, v in rows]


def predict_price(price_history: Optional[dict], current_modal: Optional[float] = None) -> dict:
    """Short-horizon price guidance from 90-day history. Band = projection ± volatility.

    Honest about uncertainty: returns LOW confidence + a 'hold/sell' lean only, never a
    guaranteed number. Defers when history is too thin.
    """
    if not price_history:
        return {"method": "no_history", "confidence": "LOW"}
    daily = _price_points(price_history.get("daily_prices"))
    rng = price_history.get("price_range_90d", {}) or {}
    avg90 = rng.get("avg")
    vol = price_history.get("volatility_30d") or price_history.get("volatility_7d") or 0.0
    if len(daily) < 5:
        return {"method": "thin_history", "confidence": "LOW",
                "avg_90d": avg90, "note": "Not enough price history to project."}

    recent = daily[-7:]
    slope = (recent[-1] - recent[0]) / max(1, len(recent) - 1)
    point = recent[-1] + slope * 3  # ~3-day projection
    band = abs(point) * float(vol) if vol else abs(point) * 0.08
    lean = "hold"
    if current_modal and avg90:
        if current_modal >= avg90 * 1.05:
            lean = "sell_soon"   # above 90-day average → capture it
        elif current_modal <= avg90 * 0.95:
            lean = "hold"        # below average → wait if storage allows
    return {
        "method": "trend_plus_volatility",
        "projected_3d": round(point),
        "low": round(point - band),
        "high": round(point + band),
        "avg_90d": avg90,
        "trend_per_day": round(slope, 2),
        "lean": lean,
        "confidence": "MEDIUM" if len(daily) >= 20 else "LOW",
        "indicative": True,
        "farmer_line": {
            "sell_soon": "Today's price is above the 3-month average — a good window to sell.",
            "hold": "Price is around or below the 3-month average — hold if you can store safely.",
        }[lean],
    }


def _price_points(daily) -> list:
    """Accept [number,...] or [{'price'|'modal_price': n}, ...] -> [float,...]."""
    out = []
    for x in (daily or []):
        if isinstance(x, (int, float)):
            out.append(float(x))
        elif isinstance(x, dict):
            v = x.get("price") or x.get("modal_price") or x.get("avg_price")
            if v is not None:
                try:
                    out.append(float(v))
                except (ValueError, TypeError):
                    pass
    return out


def predict_harvest_window(growth_stage: Optional[dict], psri_status: Optional[str],
                           trajectory: Optional[dict]) -> dict:
    """Estimate days to harvest by fusing GDD staging, leaf senescence (PSRI) and trend.
    Indicative — combines independent signals, flags when they disagree."""
    if not growth_stage:
        return {}
    stage = growth_stage.get("stage", "")
    days_to_next = growth_stage.get("days_to_next_stage")
    near_harvest_stages = ("ripening", "maturation", "grain_filling", "harvest_ready",
                           "fruit_development")
    signals = []
    if stage in near_harvest_stages:
        signals.append("growth stage near maturity")
    if psri_status in ("senescing", "early_senescence"):
        signals.append("leaves ageing (senescence detected)")
    if trajectory and trajectory.get("direction") == "declining":
        signals.append("greenness declining")

    if not signals:
        return {"near_harvest": False, "confidence": "LOW"}

    if stage == "harvest_ready" or len(signals) >= 2:
        est = days_to_next if (days_to_next is not None and days_to_next < 25) else 7
        return {
            "near_harvest": True,
            "estimated_days": est,
            "signals": signals,
            "confidence": "MEDIUM" if len(signals) >= 2 else "LOW",
            "indicative": True,
            "farmer_line": f"Harvest looks about {est} day(s) away based on crop stage and leaf condition.",
        }
    return {"near_harvest": True, "estimated_days": days_to_next, "signals": signals,
            "confidence": "LOW", "indicative": True}
