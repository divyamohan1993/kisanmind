"""
KisanMind — NASA Earthdata cluster (GES DISC Data Rods, GLDAS land-surface model).

A third, independent soil-water + evapotranspiration source (on top of SMAP, NASA POWER and
Open-Meteo). Independence is the point: the agentic verification gate trusts a water signal
far more when sensors from different agencies and physics agree. GLDAS-Noah 0.25° gives
root-zone moisture, a 3-layer soil-moisture profile, evapotranspiration and surface
temperature at a point.

Free, but Earthdata Login is required. Create a token at
https://urs.earthdata.nasa.gov (Profile → Generate Token) and set EARTHDATA_TOKEN. Without it
this returns {"available": False} with zero network calls.

httpx only. Defensive throughout: any parse/network issue yields {} or a partial dict, never
an exception — the caller treats every field as present-or-absent.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx

log = logging.getLogger("kisanmind.earthdata")

_DATARODS_URL = "https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi"
_PRODUCT = "GLDAS_NOAH025_3H_v2.1"
_FILL = -9990.0  # GLDAS fill values are large-negative (~ -9999)

# variable -> (datarods id, converter(raw)->(value, unit)) handled inline below.
_VARIABLES = {
    "root_moist_kgm2": f"GLDAS2:{_PRODUCT}:RootMoist_inst",
    "soil_0_10_kgm2": f"GLDAS2:{_PRODUCT}:SoilMoi0_10cm_inst",
    "soil_10_40_kgm2": f"GLDAS2:{_PRODUCT}:SoilMoi10_40cm_inst",
    "soil_40_100_kgm2": f"GLDAS2:{_PRODUCT}:SoilMoi40_100cm_inst",
    "evap_kgm2s": f"GLDAS2:{_PRODUCT}:Evap_tavg",
    "surf_temp_k": f"GLDAS2:{_PRODUCT}:AvgSurfT_inst",
}

_ROW = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s+(-?\d+(?:\.\d+)?)")


def _latest_value(text: str) -> Optional[float]:
    """Parse Data Rods asc2 text; return the most recent non-fill numeric value."""
    latest = None
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if m:
            try:
                v = float(m.group(2))
            except ValueError:
                continue
            if v > _FILL:
                latest = v  # rows are chronological; keep overwriting → ends on newest
    return latest


async def _fetch_var(client: httpx.AsyncClient, variable: str, lat: float, lon: float,
                     token: str) -> Optional[float]:
    end = datetime.utcnow()
    start = end - timedelta(days=10)
    params = {
        "variable": variable,
        "location": f"GEOM:POINT({lon}, {lat})",
        "startDate": start.strftime("%Y-%m-%dT00"),
        "endDate": end.strftime("%Y-%m-%dT00"),
        "type": "asc2",
    }
    resp = await client.get(_DATARODS_URL, params=params,
                            headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return _latest_value(resp.text)


async def fetch_earthdata(lat: float, lon: float, timeout: float = 18.0) -> dict:
    """GLDAS root-zone moisture, soil profile, ET and surface temp at a point. Optional/graceful."""
    token = os.getenv("EARTHDATA_TOKEN", "")
    if not token:
        return {"available": False, "reason": "no_earthdata_token"}

    raw: dict = {}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            results = await asyncio.gather(
                *[_fetch_var(client, v, lat, lon, token) for v in _VARIABLES.values()],
                return_exceptions=True,
            )
        for key, res in zip(_VARIABLES.keys(), results):
            if isinstance(res, (int, float)):
                raw[key] = res
    except Exception as e:
        log.info(f"Earthdata (GLDAS) unavailable: {e}")
        return {"available": False, "reason": str(e)[:120]}

    if not raw:
        return {"available": False, "reason": "no_valid_data"}

    out: dict = {}
    # Layer soil moisture: kg/m2 over the layer thickness (mm) -> volumetric m3/m3.
    def _vol(kgm2, thickness_mm):
        return round(kgm2 / thickness_mm, 4) if kgm2 is not None else None
    out["soil_0_10_m3m3"] = _vol(raw.get("soil_0_10_kgm2"), 100)
    out["soil_10_40_m3m3"] = _vol(raw.get("soil_10_40_kgm2"), 300)
    out["soil_40_100_m3m3"] = _vol(raw.get("soil_40_100_kgm2"), 600)
    # Root-zone (0-100cm): RootMoist is kg/m2 over ~1000mm -> volumetric.
    if raw.get("root_moist_kgm2") is not None:
        out["rootzone_moisture_m3m3"] = round(raw["root_moist_kgm2"] / 1000.0, 4)
    # ET: kg/m2/s -> mm/day.
    if raw.get("evap_kgm2s") is not None:
        out["et_mm_day"] = round(raw["evap_kgm2s"] * 86400.0, 2)
    # Surface temp: K -> C.
    if raw.get("surf_temp_k") is not None:
        out["surface_temp_c"] = round(raw["surf_temp_k"] - 273.15, 1)

    out = {k: v for k, v in out.items() if v is not None}
    if not out:
        return {"available": False, "reason": "no_valid_data"}
    out["available"] = True
    out["source"] = "NASA Earthdata GES DISC (GLDAS-Noah 0.25° land-surface model)"
    return out
