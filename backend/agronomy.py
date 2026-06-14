"""
KisanMind — derived agronomy parameters (pure functions, stdlib only).

These fuse signals we already collect (LST, air temp, VPD, ET, rainfall, temperature history,
latitude/date) into higher-order, decision-ready facts that no single sensor gives directly:
water stress (CWSI/ESI), heat load, frost risk, chill accumulation, photoperiod and aridity.
Each is indicative and carries that flag; together they sharpen both the mapping and the
prediction. No network, no heavy deps — unit-testable anywhere.
"""

from __future__ import annotations

import math
from typing import Optional

# Crop heat-damage threshold (°C) and frost threshold (°C). Indicative defaults.
CROP_TEMP_LIMITS = {
    "tomato": (32, 4), "wheat": (32, 0), "rice": (35, 8), "potato": (28, 2),
    "onion": (32, 0), "capsicum": (32, 6), "cabbage": (28, -2), "cauliflower": (28, -1),
    "apple": (30, -2), "mango": (38, 4), "maize": (35, 2), "cotton": (38, 2),
}
_DEFAULT_LIMITS = (35, 2)
# Crops where winter chill accumulation matters (temperate fruit).
CHILL_CROPS = {"apple", "pear", "peach", "plum", "cherry", "apricot", "almond", "grapes"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v)) if v is not None else None


def photoperiod_hours(lat: float, day_of_year: int) -> Optional[float]:
    """Day length (sunrise→sunset) in hours — Forsythe et al. (1995) CBM model. Pure astronomy.
    Drives flowering in photoperiod-sensitive crops (onion bulbing, rice, soybean, mustard)."""
    try:
        theta = 0.2163108 + 2 * math.atan(0.9671396 * math.tan(0.00860 * (day_of_year - 186)))
        phi = math.asin(0.39795 * math.cos(theta))
        lat_r = math.radians(lat)
        arg = (math.sin(math.radians(0.8333)) + math.sin(lat_r) * math.sin(phi)) / \
              (math.cos(lat_r) * math.cos(phi))
        arg = _clamp(arg, -1.0, 1.0)
        return round(24.0 - (24.0 / math.pi) * math.acos(arg), 2)
    except (ValueError, ZeroDivisionError):
        return None


def chill_hours(historical_weather: Optional[list], threshold: float = 7.0) -> Optional[int]:
    """Approximate accumulated chill hours (<7°C) from daily min/max — triangular within-day
    estimate. Indicative; meaningful for temperate fruit dormancy/bud-break."""
    if not historical_weather:
        return None
    total = 0.0
    counted = False
    for d in historical_weather:
        tmin, tmax = d.get("min_temp_c"), d.get("max_temp_c")
        if tmin is None or tmax is None:
            continue
        counted = True
        if tmax <= threshold:
            total += 24.0
        elif tmin >= threshold:
            total += 0.0
        elif tmax > tmin:
            total += 24.0 * (threshold - tmin) / (tmax - tmin)
    return int(round(total)) if counted else None


def heat_stress_degree_days(historical_weather: Optional[list], crop: str) -> Optional[float]:
    """Accumulated heat above the crop's damage threshold (Σ max(0, Tmax − limit)). Indicative
    cumulative heat load — high values flag spikelet sterility / fruit drop risk."""
    if not historical_weather:
        return None
    limit = CROP_TEMP_LIMITS.get(crop.lower().strip(), _DEFAULT_LIMITS)[0]
    total = 0.0
    counted = False
    for d in historical_weather:
        tmax = d.get("max_temp_c")
        if tmax is None:
            continue
        counted = True
        total += max(0.0, tmax - limit)
    return round(total, 1) if counted else None


def frost_risk(forecast_daily: Optional[list], crop: str) -> dict:
    """Frost risk over the next 3 forecast days vs the crop's frost threshold."""
    if not forecast_daily:
        return {}
    frost_t = CROP_TEMP_LIMITS.get(crop.lower().strip(), _DEFAULT_LIMITS)[1]
    mins = [d.get("min_temp_c") for d in forecast_daily[:3] if d.get("min_temp_c") is not None]
    if not mins:
        return {}
    lowest = min(mins)
    if lowest <= frost_t:
        level, line = "high", f"Frost risk — temperature near {round(lowest)}°C in the next 3 days. Protect the crop."
    elif lowest <= frost_t + 3:
        level, line = "watch", f"Cold nights ahead (about {round(lowest)}°C) — watch for frost."
    else:
        level, line = "none", ""
    return {"level": level, "min_temp_c": round(lowest, 1), "threshold_c": frost_t,
            "indicative": True, "farmer_line": line}


def aridity_index(precip_recent_mm: Optional[float], et0_mm_day: Optional[float],
                  days: int = 7) -> Optional[float]:
    """Recent water-balance ratio P / PET. <0.2 arid, 0.2–0.5 semi-arid, >0.65 humid."""
    if precip_recent_mm is None or not et0_mm_day or et0_mm_day <= 0:
        return None
    pet = et0_mm_day * days
    return round(precip_recent_mm / pet, 3) if pet > 0 else None


def esi(et_actual_mm: Optional[float], et0_mm: Optional[float]) -> Optional[float]:
    """Evaporative Stress Index = actual ET ÷ reference ET. <0.5 = the crop can't transpire
    at demand → water stress. A clean, sensor-grounded drought early-warning."""
    if et_actual_mm is None or not et0_mm or et0_mm <= 0:
        return None
    return round(_clamp(et_actual_mm / et0_mm, 0.0, 1.5), 3)


def cwsi(lst_day_c: Optional[float], air_temp_c: Optional[float],
         vpd_kpa: Optional[float]) -> Optional[float]:
    """Crop Water Stress Index (simplified Idso–Jackson). Canopy-minus-air temperature
    normalised by well-watered/non-transpiring baselines. 0 = unstressed, 1 = fully stressed.
    Indicative — LST_day is a surface proxy for canopy temperature."""
    if lst_day_c is None or air_temp_c is None:
        return None
    dT = lst_day_c - air_temp_c
    # Well-watered baseline drops with atmospheric demand; non-transpiring upper bound ~6°C.
    dT_ll = 2.0 - 1.5 * (vpd_kpa if vpd_kpa is not None else 1.0)
    dT_ul = 6.0
    if dT_ul <= dT_ll:
        return None
    return round(_clamp((dT - dT_ll) / (dT_ul - dT_ll), 0.0, 1.0), 3)


# --- classification + farmer language for the decision-driving ones ---
def classify_esi(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    if v >= 0.8:
        return "no_stress"
    if v >= 0.5:
        return "mild_stress"
    return "water_stress"


def classify_cwsi(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    if v >= 0.6:
        return "high_stress"
    if v >= 0.3:
        return "moderate_stress"
    return "low_stress"


def compute_agronomy(lat: float, day_of_year: int, crop: str = "", *,
                     lst_day_c=None, air_temp_c=None, vpd_kpa=None,
                     et_actual_mm=None, et0_mm=None, precip_recent_mm=None,
                     relative_humidity=None, wind_speed_ms=None, soil_temp_c=None,
                     surface_moisture_m3m3=None, thermal_anomaly_c=None,
                     historical_weather=None, forecast_daily=None) -> dict:
    """Assemble all derived agronomy parameters that the inputs allow. Returns only what's
    computable (present-or-absent), plus farmer-language interpretation for the actionable ones."""
    out: dict = {}
    interp: dict = {}

    out["photoperiod_hours"] = photoperiod_hours(lat, day_of_year)
    out["chill_hours"] = chill_hours(historical_weather)
    out["heat_stress_dd"] = heat_stress_degree_days(historical_weather, crop)
    out["aridity_index"] = aridity_index(precip_recent_mm, et0_mm)
    out["esi"] = esi(et_actual_mm, et0_mm)
    out["cwsi"] = cwsi(lst_day_c, air_temp_c, vpd_kpa)
    # Direct passthrough signals (already measured upstream) — formalised as parameters.
    for k, v in (("relative_humidity", relative_humidity), ("wind_speed_ms", wind_speed_ms),
                 ("soil_temp_c", soil_temp_c), ("surface_moisture_m3m3", surface_moisture_m3m3),
                 ("thermal_anomaly_c", thermal_anomaly_c)):
        if v is not None:
            out[k] = v
    frost = frost_risk(forecast_daily, crop)
    if frost:
        out["frost_risk"] = frost

    # Interpretation (jargon-free) for the decision-driving signals.
    if out.get("esi") is not None and classify_esi(out["esi"]) == "water_stress":
        interp["water_stress"] = "The crop is struggling to transpire — a sign it needs water."
    elif out.get("cwsi") is not None and classify_cwsi(out["cwsi"]) == "high_stress":
        interp["water_stress"] = "Canopy heat suggests the crop is water-stressed."
    if relative_humidity is not None and relative_humidity >= 80:
        interp["disease_pressure"] = "Humidity is high — conditions favour fungal disease; watch the leaves."
    if wind_speed_ms is not None and wind_speed_ms >= 8:
        interp["spray_caution"] = "Wind is strong — avoid spraying today, it will drift."
    if out.get("chill_hours") is not None and crop.lower().strip() in CHILL_CROPS:
        interp["chill"] = f"About {out['chill_hours']} chill hours accumulated — relevant for {crop} bud-break."
    if frost.get("farmer_line"):
        interp["frost"] = frost["farmer_line"]
    if out.get("photoperiod_hours") is not None:
        interp["daylength"] = f"Day length is about {out['photoperiod_hours']} hours now."

    out = {k: v for k, v in out.items() if v is not None}
    out["interpretation"] = interp
    out["indicative"] = True
    return out
