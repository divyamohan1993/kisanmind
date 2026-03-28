"""AgMarkNet API client for fetching live mandi (wholesale market) prices.

Uses the data.gov.in open API to query commodity prices across Indian mandis.
Falls back to demo data when the API is unavailable or credentials are missing.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

AGMARKNET_ENDPOINT = (
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class MandiPrice(BaseModel):
    """A single mandi price record."""

    state: str
    district: str
    market: str
    commodity: str
    variety: str
    arrival_date: str
    min_price: float  # ₹ per quintal
    max_price: float  # ₹ per quintal
    modal_price: float  # ₹ per quintal (most frequent transaction price)


class AgMarkNetResponse(BaseModel):
    """Wrapper around the list of mandi prices returned to callers."""

    records: list[MandiPrice]
    source: str  # "api" or "demo"
    fetched_at: str  # ISO timestamp


# ---------------------------------------------------------------------------
# Demo / fallback data — Himachal Pradesh tomato prices
# ---------------------------------------------------------------------------

_DEMO_RECORDS: list[dict] = [
    {
        "state": "Himachal Pradesh",
        "district": "Solan",
        "market": "Solan",
        "commodity": "Tomato",
        "variety": "Hybrid",
        "arrival_date": "2026-03-27",
        "min_price": 1800.0,
        "max_price": 2400.0,
        "modal_price": 2100.0,
    },
    {
        "state": "Himachal Pradesh",
        "district": "Shimla",
        "market": "Shimla",
        "commodity": "Tomato",
        "variety": "Hybrid",
        "arrival_date": "2026-03-27",
        "min_price": 2000.0,
        "max_price": 2800.0,
        "modal_price": 2400.0,
    },
    {
        "state": "Himachal Pradesh",
        "district": "Kullu",
        "market": "Kullu",
        "commodity": "Tomato",
        "variety": "Local",
        "arrival_date": "2026-03-27",
        "min_price": 1600.0,
        "max_price": 2200.0,
        "modal_price": 1900.0,
    },
    {
        "state": "Himachal Pradesh",
        "district": "Mandi",
        "market": "Mandi",
        "commodity": "Tomato",
        "variety": "Hybrid",
        "arrival_date": "2026-03-27",
        "min_price": 1700.0,
        "max_price": 2500.0,
        "modal_price": 2200.0,
    },
    {
        "state": "Himachal Pradesh",
        "district": "Kangra",
        "market": "Palampur",
        "commodity": "Tomato",
        "variety": "Local",
        "arrival_date": "2026-03-27",
        "min_price": 1500.0,
        "max_price": 2100.0,
        "modal_price": 1800.0,
    },
]


def _get_demo_data(commodity: Optional[str] = None) -> AgMarkNetResponse:
    """Return hard-coded demo data, optionally filtered by commodity."""
    records = _DEMO_RECORDS
    if commodity:
        commodity_lower = commodity.strip().lower()
        records = [r for r in records if r["commodity"].lower() == commodity_lower]
    return AgMarkNetResponse(
        records=[MandiPrice(**r) for r in records],
        source="demo",
        fetched_at=datetime.utcnow().isoformat(),
    )


# ---------------------------------------------------------------------------
# Live API fetch
# ---------------------------------------------------------------------------

def fetch_mandi_prices(
    commodity: str,
    state: Optional[str] = None,
    limit: int = 50,
    timeout: int = 10,
) -> AgMarkNetResponse:
    """Fetch current mandi prices from the AgMarkNet / data.gov.in API.

    Parameters
    ----------
    commodity:
        Crop name, e.g. "Tomato", "Wheat", "Onion".
    state:
        Indian state to filter by (optional).
    limit:
        Max records to return.
    timeout:
        HTTP request timeout in seconds.

    Returns
    -------
    AgMarkNetResponse with records sourced from the API, or demo data on
    failure.
    """
    api_key = os.getenv("AGMARKNET_API_KEY", "")
    if not api_key:
        logger.warning(
            "AGMARKNET_API_KEY not set — returning demo data for %s", commodity
        )
        return _get_demo_data(commodity)

    params: dict = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        "filters[commodity]": commodity.strip().title(),
    }
    if state:
        params["filters[state]"] = state.strip().title()

    try:
        resp = requests.get(
            AGMARKNET_ENDPOINT, params=params, timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("AgMarkNet API request failed: %s — falling back to demo data", exc)
        return _get_demo_data(commodity)

    raw_records = data.get("records", [])
    if not raw_records:
        logger.info(
            "AgMarkNet returned 0 records for commodity=%s, state=%s — using demo data",
            commodity,
            state,
        )
        return _get_demo_data(commodity)

    records: list[MandiPrice] = []
    for rec in raw_records:
        try:
            records.append(
                MandiPrice(
                    state=rec.get("state", ""),
                    district=rec.get("district", ""),
                    market=rec.get("market", ""),
                    commodity=rec.get("commodity", ""),
                    variety=rec.get("variety", "Other"),
                    arrival_date=rec.get("arrival_date", ""),
                    min_price=float(rec.get("min_price", 0)),
                    max_price=float(rec.get("max_price", 0)),
                    modal_price=float(rec.get("modal_price", 0)),
                )
            )
        except (ValueError, TypeError) as exc:
            logger.debug("Skipping malformed AgMarkNet record: %s", exc)

    if not records:
        return _get_demo_data(commodity)

    return AgMarkNetResponse(
        records=records,
        source="api",
        fetched_at=datetime.utcnow().isoformat(),
    )
