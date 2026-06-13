"""
KisanMind — real transport economics.

The old model charged a flat Rs 3.5/km/quintal. This computes an explainable, diesel-based
fare: pick the vehicle a farmer would actually hire for the load, cost the round trip from
real distance + fuel mileage + diesel price + loading labour, and divide over the quintals
carried. Pure functions (stdlib) — fully testable, no external calls.

Indicative by design: diesel price and mileage vary by state and vehicle age; the breakdown
is transparent so a farmer can see every rupee and adjust.
"""

from __future__ import annotations

import math
from typing import Optional

# Default pump diesel price (Rs/litre), India mid-2026 ballpark. Override per request/env.
DEFAULT_DIESEL_PRICE = 90.0

# Vehicle tiers a smallholder/aggregator actually uses. (capacity_q, mileage_kmpl, label)
VEHICLES = [
    (10, 12.0, "mini-truck (pickup)"),
    (25, 6.0, "tractor-trolley"),
    (80, 5.0, "medium truck (LCV)"),
]
ROUND_TRIP_FACTOR = 2.0      # hired vehicle returns empty — farmer pays both ways
LOADING_LABOUR_PER_LOAD = 150.0  # load + unload labour, Rs per trip-load


def _pick_vehicle(quantity_quintals: float):
    qty = quantity_quintals if quantity_quintals and quantity_quintals > 0 else 8.0
    for cap, mileage, label in VEHICLES:
        if qty <= cap:
            return cap, mileage, label
    return VEHICLES[-1]


def estimate_transport_fare(
    distance_km: Optional[float],
    quantity_quintals: float = 0,
    crop: str = "",
    diesel_price: Optional[float] = None,
) -> dict:
    """Diesel-distance fare model. Returns a full breakdown + per-quintal cost, or {} if no
    distance is known (cannot cost an unknown trip)."""
    if distance_km is None or distance_km <= 0:
        return {}
    diesel = diesel_price if diesel_price and diesel_price > 0 else DEFAULT_DIESEL_PRICE
    cap, mileage, label = _pick_vehicle(quantity_quintals)

    qty = quantity_quintals if quantity_quintals and quantity_quintals > 0 else None
    loads = math.ceil(qty / cap) if qty else 1
    round_trip_km = distance_km * ROUND_TRIP_FACTOR
    fuel_cost = round_trip_km * loads * (diesel / mileage)
    labour = LOADING_LABOUR_PER_LOAD * loads
    total = fuel_cost + labour

    # Per-quintal: over the real load if known, else over a representative load for this vehicle.
    basis = qty if qty else min(cap, 8.0)
    per_quintal = total / basis

    return {
        "vehicle": label,
        "capacity_quintals": cap,
        "loads_needed": loads,
        "quantity_basis_quintals": round(basis, 1),
        "diesel_price_per_l": diesel,
        "mileage_kmpl": mileage,
        "distance_km": round(distance_km, 1),
        "round_trip_km": round(round_trip_km, 1),
        "fuel_cost": round(fuel_cost),
        "labour_cost": round(labour),
        "total_trip_cost": round(total),
        "per_quintal": round(per_quintal, 1),
        "method": "diesel_distance_model",
        "indicative": True,
        "farmer_line": (
            f"By {label}, the round trip of about {round(round_trip_km)} km costs roughly "
            f"Rs {round(total)} in diesel and loading — about Rs {round(per_quintal)} per quintal."
        ),
    }


def transport_rate_per_km_per_quintal(quantity_quintals: float = 0,
                                      diesel_price: Optional[float] = None) -> float:
    """Diesel-derived Rs/km/quintal, for net-profit ranking. Degrades to a stable default
    when quantity is unknown so rankings never swing wildly on missing input."""
    diesel = diesel_price if diesel_price and diesel_price > 0 else DEFAULT_DIESEL_PRICE
    cap, mileage, _ = _pick_vehicle(quantity_quintals)
    basis = quantity_quintals if quantity_quintals and quantity_quintals > 0 else min(cap, 8.0)
    # Round-trip fuel per km, spread over the load.
    return round(ROUND_TRIP_FACTOR * (diesel / mileage) / basis, 3)
