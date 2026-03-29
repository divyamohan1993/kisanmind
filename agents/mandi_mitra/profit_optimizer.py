"""Profit optimiser — ranks mandis by estimated net profit for a farmer.

Net profit per quintal =
    modal_price
    - transport_cost_per_quintal
    - (commission_rate * modal_price)
    - spoilage_loss_per_quintal

Transport cost is derived from the Google Maps Distance Matrix API when a key
is available; otherwise a straight-line estimate is used as a fallback.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from .agmarknet_client import MandiPrice

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANSPORT_RATE_PER_KM_PER_QUINTAL = 3.5  # ₹
DEFAULT_COMMISSION_RATE = 0.04  # 4 %
AVERAGE_SPEED_KMH = 30  # fallback when Maps API unavailable

# Perishability tiers — spoilage percentage of modal_price per hour of travel
PERISHABILITY: dict[str, float] = {
    "high": 0.005,   # tomato, leafy greens, strawberry
    "medium": 0.002,  # potato, onion, cabbage
    "low": 0.0005,   # wheat, rice, pulses, spices
}

# Crop → perishability tier lookup (extend as needed)
CROP_PERISHABILITY: dict[str, str] = {
    "tomato": "high",
    "banana": "high",
    "strawberry": "high",
    "spinach": "high",
    "lettuce": "high",
    "mango": "high",
    "grape": "high",
    "papaya": "high",
    "potato": "medium",
    "onion": "medium",
    "cabbage": "medium",
    "cauliflower": "medium",
    "carrot": "medium",
    "apple": "medium",
    "wheat": "low",
    "rice": "low",
    "maize": "low",
    "soybean": "low",
    "mustard": "low",
    "chilli": "low",
    "turmeric": "low",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MandiRanking(BaseModel):
    """A single mandi entry with profit breakdown."""

    market: str
    district: str
    state: str
    modal_price: float  # ₹ per quintal
    distance_km: float
    travel_time_min: float
    transport_cost: float  # ₹ per quintal
    commission: float  # ₹ per quintal
    spoilage_loss: float  # ₹ per quintal
    net_profit: float  # ₹ per quintal
    data_source: str  # e.g. "api"
    arrival_date: str


class OptimizationResult(BaseModel):
    """Full result returned by the optimizer."""

    crop: str
    quantity_quintals: float
    farmer_lat: float
    farmer_lon: float
    commission_rate: float
    rankings: list[MandiRanking]
    disclaimer: str


# ---------------------------------------------------------------------------
# Google Maps Distance Matrix helper
# ---------------------------------------------------------------------------

def _get_distance_matrix(
    origin_lat: float,
    origin_lon: float,
    destinations: list[str],
    timeout: int = 10,
) -> Optional[list[dict]]:
    """Call Google Maps Distance Matrix API.

    Returns a list of {"distance_km": float, "duration_min": float} dicts,
    one per destination, or None on failure.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return None

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lon}",
        "destinations": "|".join(destinations),
        "mode": "driving",
        "key": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Google Maps Distance Matrix request failed: %s", exc)
        return None

    if data.get("status") != "OK":
        logger.error("Distance Matrix API status: %s", data.get("status"))
        return None

    results: list[dict] = []
    for element in data.get("rows", [{}])[0].get("elements", []):
        if element.get("status") == "OK":
            results.append(
                {
                    "distance_km": element["distance"]["value"] / 1000.0,
                    "duration_min": element["duration"]["value"] / 60.0,
                }
            )
        else:
            results.append({"distance_km": None, "duration_min": None})
    return results


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate straight-line distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Rough lat/lon for major Himachal Pradesh markets (fallback geocoding)
_MARKET_COORDS: dict[str, tuple[float, float]] = {
    "solan": (30.9045, 77.0967),
    "shimla": (31.1048, 77.1734),
    "kullu": (31.9579, 77.1095),
    "mandi": (31.7084, 76.9318),
    "palampur": (32.1109, 76.5363),
    "dharamshala": (32.2190, 76.3234),
    "bilaspur": (31.3380, 76.7560),
    "hamirpur": (31.6862, 76.5213),
    "una": (31.4685, 76.2708),
    "nahan": (30.5596, 77.2960),
}


# ---------------------------------------------------------------------------
# Core optimiser
# ---------------------------------------------------------------------------

def rank_mandis(
    mandi_prices: list[MandiPrice],
    farmer_lat: float,
    farmer_lon: float,
    crop: str,
    quantity_quintals: float = 10.0,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    data_source: str = "api",
) -> OptimizationResult:
    """Rank mandis by estimated net profit per quintal.

    Parameters
    ----------
    mandi_prices:
        List of MandiPrice records (from agmarknet_client).
    farmer_lat, farmer_lon:
        Farmer's location.
    crop:
        Crop name (used for perishability lookup).
    quantity_quintals:
        Quantity the farmer intends to sell (used for total profit display).
    commission_rate:
        Fraction charged as market commission (default 4 %).
    data_source:
        "api" — forwarded into the ranking for transparency.

    Returns
    -------
    OptimizationResult with mandis sorted best-first by net_profit.
    """
    crop_lower = crop.strip().lower()
    perishability_tier = CROP_PERISHABILITY.get(crop_lower, "medium")
    spoilage_rate_per_hour = PERISHABILITY[perishability_tier]

    # Build destination strings for Distance Matrix
    destination_strings = [
        f"{mp.market}, {mp.district}, {mp.state}" for mp in mandi_prices
    ]

    # Try Google Maps first
    dm_results = _get_distance_matrix(
        farmer_lat, farmer_lon, destination_strings
    )

    rankings: list[MandiRanking] = []

    for idx, mp in enumerate(mandi_prices):
        # Distance + duration
        if dm_results and dm_results[idx].get("distance_km") is not None:
            distance_km = dm_results[idx]["distance_km"]
            travel_time_min = dm_results[idx]["duration_min"]
        else:
            # Fallback: haversine with 1.3x road-factor
            market_key = mp.market.strip().lower()
            if market_key in _MARKET_COORDS:
                mlat, mlon = _MARKET_COORDS[market_key]
            else:
                # Use district name as second attempt
                mlat, mlon = _MARKET_COORDS.get(
                    mp.district.strip().lower(), (farmer_lat, farmer_lon)
                )
            straight_line = _haversine_km(farmer_lat, farmer_lon, mlat, mlon)
            distance_km = straight_line * 1.3  # road winding factor
            travel_time_min = (distance_km / AVERAGE_SPEED_KMH) * 60

        transport_cost = TRANSPORT_RATE_PER_KM_PER_QUINTAL * distance_km
        commission = commission_rate * mp.modal_price
        travel_hours = travel_time_min / 60.0
        spoilage_loss = spoilage_rate_per_hour * travel_hours * mp.modal_price

        net_profit = mp.modal_price - transport_cost - commission - spoilage_loss

        rankings.append(
            MandiRanking(
                market=mp.market,
                district=mp.district,
                state=mp.state,
                modal_price=mp.modal_price,
                distance_km=round(distance_km, 1),
                travel_time_min=round(travel_time_min, 0),
                transport_cost=round(transport_cost, 2),
                commission=round(commission, 2),
                spoilage_loss=round(spoilage_loss, 2),
                net_profit=round(net_profit, 2),
                data_source=data_source,
                arrival_date=mp.arrival_date,
            )
        )

    # Sort by net profit descending
    rankings.sort(key=lambda r: r.net_profit, reverse=True)

    return OptimizationResult(
        crop=crop,
        quantity_quintals=quantity_quintals,
        farmer_lat=farmer_lat,
        farmer_lon=farmer_lon,
        commission_rate=commission_rate,
        rankings=rankings,
        disclaimer=(
            "These are estimated figures based on publicly available mandi "
            "prices and approximate transport costs. Actual prices may vary "
            "at the time of sale. Data sourced from AgMarkNet / data.gov.in. "
            "This is not a guarantee of any price or profit."
        ),
    )
