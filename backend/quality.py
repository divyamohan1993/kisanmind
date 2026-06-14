"""
KisanMind — location accuracy + data freshness handling (pure, stdlib only).

Advice is only as trustworthy as WHERE and WHEN the data is. This module turns two raw facts
into honest, farmer-facing quality signals:

  - Location: the worse of GPS accuracy (metres) and the satellite-cache grid offset becomes an
    effective uncertainty. A precise fix gets field-level advice; an IP-located farmer (~50 km)
    is told plainly the advice is area-level — instead of being silently treated as exact.
  - Freshness: every layer carries an age. NASA POWER lags 2-3 days, Sentinel-2 revisits every
    5, mandi prints daily; the farmer's own eyes are fresher than any of them. We surface each
    age and the staleness caveat rather than implying everything is live.

Unit-tested; no network.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def assess_location_quality(accuracy_m: Optional[float],
                            cache_distance_km: Optional[float] = 0.0) -> dict:
    """Effective location uncertainty = worse of GPS accuracy and satellite-grid offset.
    Returns level + a plain-language note + whether it is reliable for a single field."""
    gps = float(accuracy_m or 0)
    grid = float(cache_distance_km or 0) * 1000.0
    eff = max(gps, grid)
    if eff <= 0:
        eff = 1000.0  # unknown → assume ~1 km rather than pretend precision

    if eff <= 500:
        level, note = "high", "Precise GPS location — advice is for your exact field."
    elif eff <= 2000:
        level, note = "good", "Good location fix — advice fits your field area."
    elif eff <= 10000:
        level, note = ("approximate",
                       "Location is approximate — this advice is for your general area, not an "
                       "exact field. Allow GPS for field-level accuracy.")
    else:
        level, note = ("area",
                       "Location is very approximate (likely no GPS) — treat this as area-level "
                       "guidance only.")
    return {
        "effective_uncertainty_m": round(eff),
        "gps_accuracy_m": round(gps) if gps else None,
        "satellite_offset_m": round(grid) if grid else None,
        "level": level,
        "reliable_for_field": eff <= 2000,
        "farmer_note": note,
    }


def days_since(date_str: Optional[str]) -> Optional[int]:
    """Whole days since a YYYY-MM-DD (or ISO) date; None if unparseable."""
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return max(0, (datetime.utcnow() - d).days)
    except (ValueError, TypeError):
        return None


def _age_label(days: Optional[int]) -> str:
    if days is None:
        return "unknown age"
    if days == 0:
        return "today"
    if days == 1:
        return "1 day old"
    return f"{days} days old"


def summarize_freshness(*, satellite_image_date: Optional[str] = None,
                        cache_computed_at: Optional[str] = None,
                        agro_as_of: Optional[str] = None,
                        agro_live: bool = False,
                        mandi_arrival_date: Optional[str] = None,
                        advisory_age_minutes: Optional[int] = None) -> dict:
    """Consolidate the age of every data layer into one structured block + a farmer caveat.
    The caveat always reminds the farmer that their own field observation is the freshest data."""
    sat_days = days_since(satellite_image_date) or days_since(cache_computed_at)
    layers = {
        "satellite_crop_health": {
            "as_of": satellite_image_date or (cache_computed_at[:10] if cache_computed_at else None),
            "days_old": sat_days, "label": _age_label(sat_days),
            "note": "Optical satellite revisits every ~5 days; clouds can delay it.",
        },
        "soil_agroclimate": {
            "as_of": "live" if agro_live else agro_as_of,
            "label": "near-live" if agro_live else _age_label(days_since(agro_as_of)),
            "note": "ET/soil from Open-Meteo are near-live; NASA POWER lags ~2-3 days.",
        },
        "mandi_prices": {
            "as_of": mandi_arrival_date, "days_old": days_since(mandi_arrival_date),
            "label": _age_label(days_since(mandi_arrival_date)),
            "note": "Mandi prices print roughly daily and can move intraday.",
        },
        "weather": {"as_of": "live", "label": "live forecast"},
    }
    if advisory_age_minutes is not None:
        layers["this_advisory"] = {"age_minutes": advisory_age_minutes,
                                   "label": f"{advisory_age_minutes} min old" if advisory_age_minutes else "fresh"}

    # Lead caveat: oldest meaningful layer + the always-true reminder.
    caveat = "Your own look at the field today is fresher than any satellite."
    if sat_days and sat_days > 5:
        caveat = (f"The crop-health image is {sat_days} days old, so anything you did since "
                  f"(watering, spraying, harvesting) will not show in it. " + caveat)
    return {"layers": layers, "satellite_days_old": sat_days, "farmer_caveat": caveat}
