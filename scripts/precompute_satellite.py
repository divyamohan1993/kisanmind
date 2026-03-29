#!/usr/bin/env python3
"""
Pre-compute satellite data for ALL of India and store as local JSON cache.

Grid: 0.1° spacing (~11km) covering India (lat 6-38°N, lon 68-98°E)
Points: ~96,000 grid points covering all of India
Satellites: Sentinel-2 (NDVI/EVI/NDWI), Sentinel-1 SAR (VV/VH), MODIS LST, SMAP soil moisture

Output: data/satellite_cache/india_satellite_YYYY-MM-DD.json
        data/satellite_cache/latest.json (symlink/copy)

Usage:
    python scripts/precompute_satellite.py                  # Full India
    python scripts/precompute_satellite.py --region solan    # Single region for testing
    python scripts/precompute_satellite.py --lat 30.9 --lon 77.1 --radius 50  # 50km around point

Requires: Earth Engine credentials configured
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import ee

# ---------------------------------------------------------------------------
# Earth Engine initialization
# ---------------------------------------------------------------------------
EE_PROJECT = os.getenv("EE_PROJECT", "dmjone")


def init_ee():
    """Initialize Earth Engine with available credentials."""
    ee_key_json = os.getenv("EE_SERVICE_KEY_JSON", "")
    ee_key_path = os.getenv("EE_SERVICE_KEY_PATH", "/secrets/ee-key/ee-service-key")

    if ee_key_json:
        from google.oauth2 import service_account as _sa
        key_data = json.loads(ee_key_json)
        creds = _sa.Credentials.from_service_account_info(
            key_data, scopes=["https://www.googleapis.com/auth/earthengine"]
        )
        ee.Initialize(credentials=creds, project=EE_PROJECT)
    elif os.path.exists(ee_key_path):
        from google.oauth2 import service_account as _sa
        creds = _sa.Credentials.from_service_account_file(
            ee_key_path, scopes=["https://www.googleapis.com/auth/earthengine"]
        )
        ee.Initialize(credentials=creds, project=EE_PROJECT)
    else:
        ee.Initialize(project=EE_PROJECT)

    print(f"Earth Engine initialized (project: {EE_PROJECT})")


# ---------------------------------------------------------------------------
# Grid generation
# ---------------------------------------------------------------------------
INDIA_BOUNDS = {
    "lat_min": 6.0,
    "lat_max": 38.0,
    "lon_min": 68.0,
    "lon_max": 98.0,
}

DEMO_REGIONS = {
    "solan": {"lat": 30.9, "lon": 77.1, "radius_km": 30},
    "delhi": {"lat": 28.6, "lon": 77.2, "radius_km": 30},
    "bangalore": {"lat": 12.97, "lon": 77.59, "radius_km": 30},
    "mumbai": {"lat": 19.08, "lon": 72.88, "radius_km": 30},
    "chennai": {"lat": 13.08, "lon": 80.27, "radius_km": 30},
    "kolkata": {"lat": 22.57, "lon": 88.36, "radius_km": 30},
    "jaipur": {"lat": 26.91, "lon": 75.79, "radius_km": 30},
    "lucknow": {"lat": 26.85, "lon": 80.95, "radius_km": 30},
    "hyderabad": {"lat": 17.39, "lon": 78.49, "radius_km": 30},
    "ahmedabad": {"lat": 23.02, "lon": 72.57, "radius_km": 30},
    "punjab": {"lat": 31.15, "lon": 75.34, "radius_km": 50},
    "shimla": {"lat": 31.10, "lon": 77.17, "radius_km": 20},
}

# Hackathon reviewer office locations — compute at 0.05° for instant demo
REVIEWER_LOCATIONS = {
    # Unstop HQ — Bhikaji Cama Place, New Delhi
    "unstop_delhi": {"lat": 28.5672, "lon": 77.1856, "radius_km": 10},
    # Avataar.ai — Vaishnavi Tech Park, Bellandur, Bangalore
    "avataar_bangalore": {"lat": 12.9279, "lon": 77.6789, "radius_km": 10},
    # Economic Times — CST Fort, Mumbai
    "et_mumbai": {"lat": 18.9398, "lon": 72.8354, "radius_km": 10},
    # Economic Times — ITO, Delhi
    "et_delhi": {"lat": 28.6273, "lon": 77.2457, "radius_km": 10},
    # Economic Times — Gurgaon office
    "et_gurgaon": {"lat": 28.4957, "lon": 77.0634, "radius_km": 10},
    # ET Bangalore office
    "et_bangalore": {"lat": 12.9716, "lon": 77.5946, "radius_km": 10},
}


def generate_grid(step: float = 0.1, bounds: dict = None) -> list[tuple[float, float]]:
    """Generate lat/lon grid covering India at given step size."""
    b = bounds or INDIA_BOUNDS
    points = []
    lat = b["lat_min"]
    while lat <= b["lat_max"]:
        lon = b["lon_min"]
        while lon <= b["lon_max"]:
            points.append((round(lat, 2), round(lon, 2)))
            lon += step
        lat += step
    return points


def generate_region_grid(center_lat: float, center_lon: float,
                         radius_km: float, step: float = 0.05) -> list[tuple[float, float]]:
    """Generate grid around a center point."""
    # 1 degree ≈ 111 km
    radius_deg = radius_km / 111.0
    points = []
    lat = round(center_lat - radius_deg, 2)
    while lat <= center_lat + radius_deg:
        lon = round(center_lon - radius_deg, 2)
        while lon <= center_lon + radius_deg:
            points.append((round(lat, 2), round(lon, 2)))
            lon += step
        lat += step
    return points


# ---------------------------------------------------------------------------
# Satellite computation (batch via Earth Engine)
# ---------------------------------------------------------------------------
def compute_batch(points: list[tuple[float, float]], batch_size: int = 500) -> list[dict]:
    """Compute satellite data for a batch of points using Earth Engine.
    Uses ee.FeatureCollection.map() for efficiency — one EE call per batch."""
    end_date = datetime.utcnow()
    results = []
    total_batches = (len(points) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_points = points[batch_start:batch_start + batch_size]
        t0 = time.time()

        try:
            # Create feature collection from points
            features = [
                ee.Feature(ee.Geometry.Point([lon, lat]), {"lat": lat, "lon": lon})
                for lat, lon in batch_points
            ]
            fc = ee.FeatureCollection(features)

            # --- Sentinel-2 NDVI/EVI/NDWI (last 30 days, <30% cloud) ---
            s2_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
            s2_end = end_date.strftime("%Y-%m-%d")
            s2 = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(s2_start, s2_end)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .median()  # Cloud-free composite
            )
            ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi")
            evi = s2.expression(
                "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
                {"NIR": s2.select("B8"), "RED": s2.select("B4"), "BLUE": s2.select("B2")}
            ).rename("evi")
            ndwi = s2.normalizedDifference(["B3", "B8"]).rename("ndwi")

            # --- Sentinel-1 SAR (last 30 days) ---
            s1_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
            s1 = (
                ee.ImageCollection("COPERNICUS/S1_GRD")
                .filterDate(s1_start, s2_end)
                .filter(ee.Filter.eq("instrumentMode", "IW"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
                .select(["VV", "VH"])
                .median()
            )

            # --- MODIS LST (last 10 days) ---
            modis_start = (end_date - timedelta(days=10)).strftime("%Y-%m-%d")
            modis = (
                ee.ImageCollection("MODIS/061/MOD11A1")
                .filterDate(modis_start, s2_end)
                .select(["LST_Day_1km", "LST_Night_1km"])
                .median()
            )

            # --- SMAP Soil Moisture (last 5 days) ---
            smap_start = (end_date - timedelta(days=5)).strftime("%Y-%m-%d")
            smap = (
                ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
                .filterDate(smap_start, s2_end)
                .select(["sm_surface", "sm_rootzone"])
                .median()
            )

            # Combine all bands into one image
            combined = (
                ndvi.addBands(evi).addBands(ndwi)
                .addBands(s1)
                .addBands(modis)
                .addBands(smap)
            )

            # Sample at all points
            sampled = combined.sampleRegions(
                collection=fc,
                scale=500,  # 500m for Sentinel-2, coarser bands auto-resampled
                geometries=False,
            )

            # Get results
            sampled_list = sampled.getInfo()
            features_result = sampled_list.get("features", [])

            for f in features_result:
                props = f.get("properties", {})
                lat = props.get("lat")
                lon = props.get("lon")

                # Convert MODIS LST from scale factor
                lst_day_raw = props.get("LST_Day_1km")
                lst_night_raw = props.get("LST_Night_1km")
                lst_day_c = round(lst_day_raw * 0.02 - 273.15, 1) if lst_day_raw else None
                lst_night_c = round(lst_night_raw * 0.02 - 273.15, 1) if lst_night_raw else None

                # Classify values
                ndvi_val = props.get("ndvi")
                vv_val = props.get("VV")
                sm_root = props.get("sm_rootzone")

                # NDVI health
                health = "unknown"
                if ndvi_val is not None:
                    if ndvi_val >= 0.6:
                        health = "healthy"
                    elif ndvi_val >= 0.4:
                        health = "moderate"
                    elif ndvi_val >= 0.2:
                        health = "stressed"
                    else:
                        health = "bare"

                # SAR moisture class
                moisture = "unknown"
                if vv_val is not None:
                    if vv_val >= -8:
                        moisture = "wet"
                    elif vv_val >= -12:
                        moisture = "moist"
                    elif vv_val >= -15:
                        moisture = "dry"
                    else:
                        moisture = "very_dry"

                # Heat stress
                heat_stress = "none"
                if lst_day_c is not None:
                    if lst_day_c >= 45:
                        heat_stress = "extreme"
                    elif lst_day_c >= 40:
                        heat_stress = "high"
                    elif lst_day_c >= 35:
                        heat_stress = "moderate"

                # Root zone class
                rootzone_class = "unknown"
                if sm_root is not None:
                    if sm_root >= 0.35:
                        rootzone_class = "wet"
                    elif sm_root >= 0.25:
                        rootzone_class = "adequate"
                    elif sm_root >= 0.15:
                        rootzone_class = "low"
                    else:
                        rootzone_class = "critical"

                results.append({
                    "lat": lat,
                    "lon": lon,
                    "ndvi": round(ndvi_val, 4) if ndvi_val is not None else None,
                    "evi": round(props.get("evi", 0) or 0, 4) if props.get("evi") is not None else None,
                    "ndwi": round(props.get("ndwi", 0) or 0, 4) if props.get("ndwi") is not None else None,
                    "health": health,
                    "vv_db": round(vv_val, 2) if vv_val is not None else None,
                    "vh_db": round(props.get("VH", 0) or 0, 2) if props.get("VH") is not None else None,
                    "moisture": moisture,
                    "lst_day_c": lst_day_c,
                    "lst_night_c": lst_night_c,
                    "heat_stress": heat_stress,
                    "sm_surface": round(props.get("sm_surface", 0) or 0, 4) if props.get("sm_surface") is not None else None,
                    "sm_rootzone": round(sm_root, 4) if sm_root is not None else None,
                    "rootzone_class": rootzone_class,
                })

            elapsed = time.time() - t0
            print(f"  Batch {batch_idx + 1}/{total_batches}: {len(features_result)} points in {elapsed:.1f}s")

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  Batch {batch_idx + 1}/{total_batches}: FAILED in {elapsed:.1f}s — {e}")
            # Add empty entries for failed points
            for lat, lon in batch_points:
                results.append({"lat": lat, "lon": lon, "error": str(e)})

    return results


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def save_cache(results: list[dict], output_dir: str, label: str = ""):
    """Save computed satellite data as JSON cache files."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Filter out errors
    valid = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]

    cache_data = {
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "grid_points": len(results),
        "valid_points": len(valid),
        "failed_points": len(errors),
        "sources": {
            "ndvi_evi_ndwi": "Sentinel-2 SR Harmonized (30-day median composite)",
            "sar_vv_vh": "Sentinel-1 GRD IW (30-day median)",
            "lst": "MODIS Terra MOD11A1 (10-day median)",
            "smap": "NASA SMAP SPL4SMGP L4 (5-day median)",
        },
        "grid_step_degrees": 0.1 if not label else 0.05,
        "points": valid,
    }

    filename = f"india_satellite_{today}"
    if label:
        filename = f"satellite_{label}_{today}"

    filepath = output_path / f"{filename}.json"
    with open(filepath, "w") as f:
        json.dump(cache_data, f, separators=(",", ":"))

    # Also save as latest.json for easy access
    latest_path = output_path / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(cache_data, f, separators=(",", ":"))

    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"\nSaved: {filepath} ({size_mb:.1f} MB, {len(valid)} points)")
    print(f"Saved: {latest_path}")

    if errors:
        print(f"Warning: {len(errors)} points failed computation")

    return str(filepath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pre-compute satellite data for India")
    parser.add_argument("--region", type=str, help="Named region (solan, delhi, bangalore, etc.)")
    parser.add_argument("--lat", type=float, help="Center latitude for custom region")
    parser.add_argument("--lon", type=float, help="Center longitude for custom region")
    parser.add_argument("--radius", type=float, default=30, help="Radius in km (default: 30)")
    parser.add_argument("--step", type=float, default=0.1, help="Grid step in degrees (default: 0.1 = ~11km)")
    parser.add_argument("--batch-size", type=int, default=500, help="Points per EE batch (default: 500)")
    parser.add_argument("--output", type=str, default="data/satellite_cache", help="Output directory")
    parser.add_argument("--all-india", action="store_true", help="Compute for all of India")
    args = parser.parse_args()

    # Initialize Earth Engine
    init_ee()

    # Determine grid
    if args.region:
        if args.region not in DEMO_REGIONS:
            print(f"Unknown region: {args.region}. Available: {', '.join(DEMO_REGIONS.keys())}")
            sys.exit(1)
        r = DEMO_REGIONS[args.region]
        points = generate_region_grid(r["lat"], r["lon"], r["radius_km"], step=args.step)
        label = args.region
        print(f"Region: {args.region} (center: {r['lat']}, {r['lon']}, radius: {r['radius_km']}km)")
    elif args.lat and args.lon:
        points = generate_region_grid(args.lat, args.lon, args.radius, step=args.step)
        label = f"custom_{args.lat}_{args.lon}"
        print(f"Custom region: ({args.lat}, {args.lon}), radius: {args.radius}km")
    elif args.all_india:
        points = generate_grid(step=args.step)
        label = ""
        print(f"ALL INDIA: {INDIA_BOUNDS}")
    else:
        # Default: compute for demo regions
        print("No region specified. Computing for all demo regions...")
        for region_name, r in DEMO_REGIONS.items():
            print(f"\n{'='*60}")
            print(f"Region: {region_name}")
            print(f"{'='*60}")
            pts = generate_region_grid(r["lat"], r["lon"], r["radius_km"], step=0.05)
            print(f"Grid: {len(pts)} points at 0.05° spacing")
            results = compute_batch(pts, batch_size=args.batch_size)
            save_cache(results, args.output, label=region_name)
        return

    print(f"Grid: {len(points)} points at {args.step}° spacing")
    print(f"Estimated compute time: {len(points) / 500 * 30:.0f} seconds")
    print()

    results = compute_batch(points, batch_size=args.batch_size)
    save_cache(results, args.output, label=label)


if __name__ == "__main__":
    main()
