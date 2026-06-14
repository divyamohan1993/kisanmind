"""
KisanMind — direct Copernicus optical indices via the Copernicus Data Space Ecosystem
(CDSE) Sentinel Hub Statistical API. This is the structural "not Earth-Engine-only" path:
the same Sentinel-2 growth parameters, fetched straight from ESA's open platform.

Credential-gated and fully optional. Without CDSE_CLIENT_ID / CDSE_CLIENT_SECRET it returns
{"available": False} with zero network calls, so the app is unaffected. With credentials it
fetches a recent index time-series directly from Copernicus — no GEE in the loop.

httpx only. Best-effort: any error returns {"available": False}.

Get free credentials: https://dataspace.copernicus.eu (register → OAuth client). The free
tier includes a monthly Processing-Unit allowance suitable for per-request statistics.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

log = logging.getLogger("kisanmind.copernicus")

_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

# Evalscript: compute the high-signal Sentinel-2 indices as output bands. Reflectance inputs
# (0-1) so additive-constant indices (EVI/SAVI) are correct by construction.
_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02","B03","B04","B05","B06","B08","B11","dataMask"]}],
    output: [
      {id: "ndvi", bands: 1}, {id: "ndre", bands: 1}, {id: "ndmi", bands: 1},
      {id: "evi", bands: 1}, {id: "savi", bands: 1}, {id: "psri", bands: 1},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);
  let ndre = (s.B08 - s.B05) / (s.B08 + s.B05);
  let ndmi = (s.B08 - s.B11) / (s.B08 + s.B11);
  let evi  = 2.5 * (s.B08 - s.B04) / (s.B08 + 6*s.B04 - 7.5*s.B02 + 1.0);
  let savi = 1.5 * (s.B08 - s.B04) / (s.B08 + s.B04 + 0.5);
  let psri = (s.B04 - s.B02) / s.B06;
  return {
    ndvi: [ndvi], ndre: [ndre], ndmi: [ndmi], evi: [evi], savi: [savi],
    psri: [psri], dataMask: [s.dataMask]
  };
}
"""


def _bbox(lat: float, lon: float, half_deg: float = 0.01) -> list:
    return [round(lon - half_deg, 5), round(lat - half_deg, 5),
            round(lon + half_deg, 5), round(lat + half_deg, 5)]


async def _get_token(client: httpx.AsyncClient, cid: str, secret: str) -> Optional[str]:
    resp = await client.post(_TOKEN_URL, data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": secret,
    })
    resp.raise_for_status()
    return resp.json().get("access_token")


async def fetch_copernicus_indices(lat: float, lon: float, timeout: float = 20.0) -> dict:
    """Latest Sentinel-2 indices straight from Copernicus Data Space. Optional/credential-gated."""
    cid = os.getenv("CDSE_CLIENT_ID", "")
    secret = os.getenv("CDSE_CLIENT_SECRET", "")
    if not cid or not secret:
        return {"available": False, "reason": "no_cdse_credentials"}

    end = datetime.utcnow()
    start = end - timedelta(days=30)
    body = {
        "input": {
            "bounds": {"bbox": _bbox(lat, lon),
                       "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"maxCloudCoverage": 40},
            }],
        },
        "aggregation": {
            "timeRange": {"from": start.strftime("%Y-%m-%dT00:00:00Z"),
                          "to": end.strftime("%Y-%m-%dT23:59:59Z")},
            "aggregationInterval": {"of": "P5D"},
            "evalscript": _EVALSCRIPT,
            "resx": 10, "resy": 10,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await _get_token(client, cid, secret)
            if not token:
                return {"available": False, "reason": "token_failed"}
            resp = await client.post(_STATS_URL, json=body,
                                     headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.info(f"CDSE statistics unavailable: {e}")
        return {"available": False, "reason": str(e)[:120]}

    # Walk intervals newest-first; take the most recent with valid stats.
    intervals = data.get("data", [])
    for interval in sorted(intervals, key=lambda i: i.get("interval", {}).get("to", ""), reverse=True):
        outputs = interval.get("outputs", {})
        vals = {}
        for key in ("ndvi", "ndre", "ndmi", "evi", "savi", "psri"):
            stats = outputs.get(key, {}).get("bands", {}).get("B0", {}).get("stats", {})
            mean = stats.get("mean")
            if mean is not None and stats.get("sampleCount", 0) > stats.get("noDataCount", 0):
                vals[key] = round(mean, 4)
        if vals:
            vals["available"] = True
            vals["image_date"] = interval.get("interval", {}).get("to", "")[:10]
            vals["source"] = "Copernicus Data Space Ecosystem (Sentinel-2 L2A, direct — no GEE)"
            return vals
    return {"available": False, "reason": "no_valid_imagery"}
