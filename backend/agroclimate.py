"""
KisanMind — agro-climate layer from satellite/model open data BEYOND Google Earth Engine.

Two independent, free, **no-API-key** providers (both live-verified to cover India):
  • NASA POWER  (power.larc.nasa.gov) — satellite + reanalysis agroclimatology:
      evapotranspiration, root/surface soil wetness, solar radiation, precip, air temp.
  • Open-Meteo  (open-meteo.com) — layered soil moisture, FAO reference ET (ET0),
      vapour-pressure deficit, soil temperature.

Why this matters: the production satellite cache only carries the original 9 optical/SAR/
thermal fields, and refreshing the full Sentinel-2 index set needs an Earth-Engine
precompute we may not rerun on every deploy. These agro-climate signals, by contrast, are
fetched LIVE per request with no key and no GEE — so the "predict the crop's water need"
intelligence works for every farmer tonight. This is the concrete "don't rely only on Earth
Engine" provider.

httpx only — no fastapi / earthengine / google-cloud. Best-effort: any failure returns a
partial dict (or {}); the caller treats every field as present-or-absent.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from statistics import median
from typing import Optional

import httpx

log = logging.getLogger("kisanmind.agroclimate")

_POWER_FILL = -999.0  # NASA POWER missing-data sentinel


def _latest_valid(series: dict) -> Optional[float]:
    """Most recent non-fill value from a NASA POWER {date: value} mapping."""
    if not series:
        return None
    for date in sorted(series.keys(), reverse=True):
        v = series[date]
        if v is not None and v > _POWER_FILL:
            return float(v)
    return None


def _recent_sum(series: dict, days: int) -> Optional[float]:
    """Sum of the last `days` non-fill values (e.g. recent rainfall)."""
    if not series:
        return None
    vals = [series[d] for d in sorted(series.keys(), reverse=True)[:days]
            if series[d] is not None and series[d] > _POWER_FILL]
    return round(sum(vals), 2) if vals else None


async def _fetch_nasa_power(lat: float, lon: float, client: httpx.AsyncClient) -> dict:
    """Daily agroclimatology from NASA POWER (last ~12 days; POWER has a 2-3 day latency)."""
    end = datetime.utcnow()
    start = end - timedelta(days=12)
    params = {
        "parameters": "T2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN,EVPTRNS,GWETROOT,GWETTOP",
        "community": "AG",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    resp = await client.get("https://power.larc.nasa.gov/api/temporal/daily/point", params=params)
    resp.raise_for_status()
    p = resp.json().get("properties", {}).get("parameter", {})
    return {
        "et_mm_day": _latest_valid(p.get("EVPTRNS", {})),
        "solar_radiation_mj": _latest_valid(p.get("ALLSKY_SFC_SW_DWN", {})),
        "rootzone_wetness": _latest_valid(p.get("GWETROOT", {})),
        "surface_wetness": _latest_valid(p.get("GWETTOP", {})),
        "air_temp_c": _latest_valid(p.get("T2M", {})),
        "precip_recent_mm": _recent_sum(p.get("PRECTOTCORR", {}), days=7),
    }


async def _fetch_open_meteo_soil(lat: float, lon: float, client: httpx.AsyncClient) -> dict:
    """Layered soil moisture, ET0, VPD and soil temperature from Open-Meteo.

    We avoid fragile timezone alignment: soil moisture/temperature barely move within a day,
    so we take the median of the first 24 hourly samples; VPD uses the next-24h MAX, because
    the agronomically meaningful figure is the midday peak that actually stresses the crop.
    """
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": ("soil_moisture_0_to_1cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm,"
                   "vapour_pressure_deficit,soil_temperature_18cm,et0_fao_evapotranspiration"),
        "daily": "et0_fao_evapotranspiration,precipitation_sum",
        "forecast_days": 5,
        "timezone": "auto",
    }
    resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
    resp.raise_for_status()
    data = resp.json()
    h = data.get("hourly", {})
    d = data.get("daily", {})

    def _med24(key):
        vals = [x for x in (h.get(key) or [])[:24] if x is not None]
        return round(median(vals), 4) if vals else None

    def _max24(key):
        vals = [x for x in (h.get(key) or [])[:24] if x is not None]
        return round(max(vals), 3) if vals else None

    sm_surface = _med24("soil_moisture_0_to_1cm")
    sm_mid = _med24("soil_moisture_9_to_27cm")
    sm_deep = _med24("soil_moisture_27_to_81cm")
    root_vals = [v for v in (sm_mid, sm_deep) if v is not None]
    sm_root = round(sum(root_vals) / len(root_vals), 4) if root_vals else None

    return {
        "et0_mm_day": (d.get("et0_fao_evapotranspiration") or [None])[0],
        "vpd_kpa": _max24("vapour_pressure_deficit"),
        "soil_temp_c": _med24("soil_temperature_18cm"),
        "soil_moisture_surface_m3m3": sm_surface,
        "soil_moisture_root_m3m3": sm_root,
        "et0_forecast_mm": [x for x in (d.get("et0_fao_evapotranspiration") or []) if x is not None],
        "rain_forecast_mm": [x for x in (d.get("precipitation_sum") or []) if x is not None],
    }


# --- farmer-language interpretation -----------------------------------------
def _interpret(merged: dict) -> dict:
    """Plain-language reads of the agro-climate signals (no jargon, translated later)."""
    out = {}
    et = merged.get("et_mm_day") or merged.get("et0_mm_day")
    if et is not None:
        if et >= 6:
            out["water_use"] = "The crop is losing a lot of water to the heat right now."
        elif et >= 3.5:
            out["water_use"] = "The crop is using a moderate amount of water daily."
        else:
            out["water_use"] = "Water loss from the crop is low at the moment."
    rz = merged.get("rootzone_wetness")
    if rz is not None:
        if rz >= 0.5:
            out["root_water"] = "Deep soil has good moisture for the roots."
        elif rz >= 0.3:
            out["root_water"] = "Root-zone moisture is adequate."
        else:
            out["root_water"] = "Deep soil is getting dry — plan watering soon."
    vpd = merged.get("vpd_kpa")
    if vpd is not None and vpd >= 2.0:
        out["air_dryness"] = "The air is very dry today, which pulls extra water from the crop."
    return out


async def fetch_agroclimate(lat: float, lon: float, timeout: float = 12.0) -> dict:
    """Fetch the combined agro-climate parameter block. Best-effort, never raises.

    Returns a normalized dict with raw values, a `forecast` block (for soil-water prediction)
    and farmer-language interpretation. `available` is True if any field came back.
    """
    merged: dict = {}
    sources: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            results = await asyncio.gather(
                _fetch_nasa_power(lat, lon, client),
                _fetch_open_meteo_soil(lat, lon, client),
                return_exceptions=True,
            )
        power_res, om_res = results
        if isinstance(power_res, dict):
            merged.update({k: v for k, v in power_res.items() if v is not None})
            sources.append("NASA POWER (satellite + reanalysis agroclimatology)")
        else:
            log.info(f"NASA POWER unavailable: {power_res}")
        if isinstance(om_res, dict):
            merged.update({k: v for k, v in om_res.items() if v is not None
                           or k in ("et0_forecast_mm", "rain_forecast_mm")})
            sources.append("Open-Meteo (soil moisture, ET0, VPD)")
        else:
            log.info(f"Open-Meteo soil/ET unavailable: {om_res}")
    except Exception as e:
        log.warning(f"Agroclimate fetch failed: {e}")
        return {}

    if not merged:
        return {}

    merged["forecast"] = {
        "et0_forecast_mm": merged.pop("et0_forecast_mm", []),
        "rain_forecast_mm": merged.pop("rain_forecast_mm", []),
    }
    merged["interpretation"] = _interpret(merged)
    merged["sources"] = sources
    merged["available"] = True
    return merged
