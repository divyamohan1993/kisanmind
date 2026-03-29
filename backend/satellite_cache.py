"""
Local satellite data cache — instant lookup from pre-computed JSON files.

Replaces real-time Earth Engine calls with <1ms local file reads.
Falls back to live EE only if cache misses (farmer at exact location not in grid).

Usage:
    from satellite_cache import SatelliteCache
    cache = SatelliteCache("data/satellite_cache")
    data = cache.lookup(30.9, 77.1)  # Returns nearest cached satellite data
"""

import json
import math
import os
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisanmind.satellite_cache")


class SatelliteCache:
    """In-memory satellite data cache loaded from pre-computed JSON files.

    On init, loads ALL cached points into memory as a list + spatial index.
    Lookup is O(1) via grid-snap for regular grids, O(n) nearest-neighbor fallback.
    """

    def __init__(self, cache_dir: str = "data/satellite_cache"):
        self.cache_dir = Path(cache_dir)
        self.points: list[dict] = []
        self.grid_index: dict[str, dict] = {}  # "lat_lon" -> data
        self.grid_step: float = 0.1
        self.computed_at: str = ""
        self.sources: dict = {}
        self._loaded = False
        self._load()

    def _load(self):
        """Load the latest cache file into memory."""
        latest_path = self.cache_dir / "latest.json"
        if not latest_path.exists():
            # Try to find any satellite cache file
            json_files = sorted(self.cache_dir.glob("*.json"), reverse=True)
            if json_files:
                latest_path = json_files[0]
            else:
                log.warning(f"No satellite cache files found in {self.cache_dir}")
                return

        try:
            with open(latest_path) as f:
                data = json.load(f)

            self.computed_at = data.get("computed_at", "")
            self.sources = data.get("sources", {})
            self.grid_step = data.get("grid_step_degrees", 0.1)
            self.points = data.get("points", [])

            # Build spatial index: snap lat/lon to grid step for O(1) lookup
            for p in self.points:
                key = self._grid_key(p["lat"], p["lon"])
                self.grid_index[key] = p

            self._loaded = True
            log.info(f"Satellite cache loaded: {len(self.points)} points from {latest_path.name} (computed {self.computed_at})")

        except Exception as e:
            log.warning(f"Failed to load satellite cache: {e}")

    def _grid_key(self, lat: float, lon: float) -> str:
        """Snap to nearest grid point and return key string."""
        snap_lat = round(round(lat / self.grid_step) * self.grid_step, 2)
        snap_lon = round(round(lon / self.grid_step) * self.grid_step, 2)
        return f"{snap_lat}_{snap_lon}"

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km between two points."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @property
    def is_loaded(self) -> bool:
        return self._loaded and len(self.points) > 0

    @property
    def cache_age_hours(self) -> float:
        """Hours since cache was computed."""
        if not self.computed_at:
            return 999
        try:
            from datetime import datetime
            computed = datetime.fromisoformat(self.computed_at.replace("Z", "+00:00"))
            now = datetime.now(computed.tzinfo)
            return (now - computed).total_seconds() / 3600
        except Exception:
            return 999

    def lookup(self, lat: float, lon: float, max_distance_km: float = 15.0) -> Optional[dict]:
        """Look up satellite data for a location.

        1. Try grid-snap O(1) lookup
        2. Fall back to nearest-neighbor search within max_distance_km
        3. Return None if no cached point within range (triggers live EE fallback)
        """
        if not self._loaded:
            return None

        # 1. Grid-snap lookup (O(1))
        key = self._grid_key(lat, lon)
        if key in self.grid_index:
            result = self.grid_index[key].copy()
            result["cache_distance_km"] = self._haversine_km(lat, lon, result["lat"], result["lon"])
            result["cache_hit"] = "grid"
            result["computed_at"] = self.computed_at
            return result

        # 2. Nearest-neighbor search within max_distance_km
        # Check adjacent grid cells first (3x3 neighborhood)
        best = None
        best_dist = max_distance_km + 1
        for dlat in [-self.grid_step, 0, self.grid_step]:
            for dlon in [-self.grid_step, 0, self.grid_step]:
                adj_key = self._grid_key(lat + dlat, lon + dlon)
                if adj_key in self.grid_index:
                    p = self.grid_index[adj_key]
                    d = self._haversine_km(lat, lon, p["lat"], p["lon"])
                    if d < best_dist:
                        best = p
                        best_dist = d

        if best and best_dist <= max_distance_km:
            result = best.copy()
            result["cache_distance_km"] = round(best_dist, 1)
            result["cache_hit"] = "neighbor"
            result["computed_at"] = self.computed_at
            return result

        # 3. Cache miss — no data within range
        return None

    def lookup_enriched(self, lat: float, lon: float) -> dict:
        """Look up and format satellite data for the advisory pipeline.
        Returns structured data matching what _run_advisory expects, or empty dicts on miss."""
        raw = self.lookup(lat, lon)

        if not raw:
            return {
                "ndvi_data": None,
                "satellite_extras": {},
                "cache_hit": False,
            }

        # Build ndvi_data (matches existing _compute_ndvi_sync output format)
        ndvi_data = None
        if raw.get("ndvi") is not None:
            ndvi_val = raw["ndvi"]
            health = raw.get("health", "unknown")
            ndvi_data = {
                "ndvi": ndvi_val,
                "evi": raw.get("evi"),
                "ndwi": raw.get("ndwi"),
                "trend": "stable",  # From cache we don't have multi-temporal trend
                "health": health.capitalize() if health != "unknown" else "Unknown",
                "image_date": self.computed_at[:10] if self.computed_at else "unknown",
                "images_found": 1,
                "true_color_url": None,  # Not available from cache
                "ndvi_color_url": None,
                "source": f"Satellite cache (pre-computed, {raw.get('cache_distance_km', 0):.1f}km from exact location)",
            }

        # Build satellite_extras (SAR, LST, SMAP)
        satellite_extras = {}

        if raw.get("vv_db") is not None:
            moisture_detail = {
                "wet": "Soil appears wet — possible recent rain or irrigation",
                "moist": "Soil moisture appears adequate",
                "dry": "Soil appears dry — may need irrigation",
                "very_dry": "Soil appears very dry — irrigation recommended",
            }
            satellite_extras["sar"] = {
                "vv_backscatter_db": raw["vv_db"],
                "vh_backscatter_db": raw.get("vh_db"),
                "moisture_class": raw.get("moisture", "unknown"),
                "moisture_detail": moisture_detail.get(raw.get("moisture", ""), ""),
                "vegetation_density": None,
                "trend": "unknown",
                "image_date": self.computed_at[:10] if self.computed_at else "unknown",
                "source": "Sentinel-1 SAR (pre-computed cache)",
            }

        if raw.get("lst_day_c") is not None:
            lst_day = raw["lst_day_c"]
            heat_detail = {
                "extreme": f"Surface temperature {lst_day}°C — extreme heat stress",
                "high": f"Surface temperature {lst_day}°C — significant heat stress",
                "moderate": f"Surface temperature {lst_day}°C — moderate heat",
                "none": f"Surface temperature {lst_day}°C — within normal range",
            }
            satellite_extras["lst"] = {
                "lst_day_celsius": lst_day,
                "lst_night_celsius": raw.get("lst_night_c"),
                "diurnal_range_celsius": round(lst_day - raw["lst_night_c"], 1) if raw.get("lst_night_c") is not None else None,
                "heat_stress": raw.get("heat_stress", "none"),
                "heat_detail": heat_detail.get(raw.get("heat_stress", "none"), ""),
                "regional_lst_celsius": None,
                "lst_anomaly_celsius": None,
                "image_date": self.computed_at[:10] if self.computed_at else "unknown",
                "source": "MODIS Terra MOD11A1 (pre-computed cache)",
            }

        if raw.get("sm_rootzone") is not None:
            rootzone_detail = {
                "wet": "Root zone is well-watered. No irrigation needed.",
                "adequate": "Root zone moisture is adequate for most crops.",
                "low": "Root zone moisture is getting low. Plan irrigation soon.",
                "critical": "Root zone moisture critically low. Irrigate immediately.",
            }
            satellite_extras["smap"] = {
                "surface_moisture_m3m3": raw.get("sm_surface"),
                "rootzone_moisture_m3m3": raw["sm_rootzone"],
                "surface_wetness_fraction": None,
                "rootzone_class": raw.get("rootzone_class", "unknown"),
                "rootzone_detail": rootzone_detail.get(raw.get("rootzone_class", ""), ""),
                "depth_insight": "",
                "image_date": self.computed_at[:10] if self.computed_at else "unknown",
                "source": "NASA SMAP L4 (pre-computed cache)",
            }

        return {
            "ndvi_data": ndvi_data,
            "satellite_extras": satellite_extras,
            "cache_hit": True,
            "cache_distance_km": raw.get("cache_distance_km", 0),
            "computed_at": self.computed_at,
        }

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "loaded": self._loaded,
            "total_points": len(self.points),
            "grid_step_degrees": self.grid_step,
            "computed_at": self.computed_at,
            "cache_age_hours": round(self.cache_age_hours, 1),
            "sources": self.sources,
            "index_size": len(self.grid_index),
        }
