"""AgMarkNet API client for fetching live mandi (wholesale market) prices.

Uses the data.gov.in open API to query commodity prices across Indian mandis.
Returns empty results when the API is unavailable or credentials are missing.
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
    source: str  # "api" or "error"
    fetched_at: str  # ISO timestamp


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
    AgMarkNetResponse with records sourced from the API, or empty on
    failure.
    """
    api_key = os.getenv("AGMARKNET_API_KEY", "")
    if not api_key:
        logger.error("AGMARKNET_API_KEY not set — cannot fetch prices for %s", commodity)
        return AgMarkNetResponse(
            records=[],
            source="error",
            fetched_at=datetime.utcnow().isoformat(),
        )

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
        logger.error("AgMarkNet API request failed: %s", exc)
        return AgMarkNetResponse(
            records=[],
            source="error",
            fetched_at=datetime.utcnow().isoformat(),
        )

    raw_records = data.get("records", [])
    if not raw_records:
        logger.info(
            "AgMarkNet returned 0 records for commodity=%s, state=%s",
            commodity,
            state,
        )
        return AgMarkNetResponse(
            records=[],
            source="api",
            fetched_at=datetime.utcnow().isoformat(),
        )

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
        return AgMarkNetResponse(
            records=[],
            source="api",
            fetched_at=datetime.utcnow().isoformat(),
        )

    return AgMarkNetResponse(
        records=records,
        source="api",
        fetched_at=datetime.utcnow().isoformat(),
    )
