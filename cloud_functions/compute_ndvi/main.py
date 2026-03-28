"""
Compute NDVI Cloud Function
============================
Wrapper around Google Earth Engine for NDVI/EVI/NDWI computation.
Returns vegetation indices and health assessment.
Falls back to simulated data for demo purposes.
"""

import json
import math
import os
import random
from datetime import datetime, timedelta

import functions_framework

# ---------------------------------------------------------------------------
# Earth Engine integration (requires ee library and service account)
# ---------------------------------------------------------------------------

def _compute_via_earth_engine(lat: float, lon: float, crop: str,
                               radius_m: int = 500) -> dict | None:
    """
    Compute NDVI/EVI/NDWI from Sentinel-2 via Earth Engine.
    Returns None if EE is not available.
    """
    try:
        import ee

        # Initialise with default credentials or service account
        project = os.environ.get("GCP_PROJECT_ID", "")
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()

        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(radius_m)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
              .filterBounds(roi)
              .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
              .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
              .sort("system:time_start", False))

        if s2.size().getInfo() == 0:
            return None

        image = s2.first()

        # Compute indices
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        evi = image.expression(
            "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
            {"NIR": image.select("B8"), "RED": image.select("B4"), "BLUE": image.select("B2")}
        ).rename("EVI")
        ndwi = image.normalizedDifference(["B8", "B11"]).rename("NDWI")

        stats_ndvi = ndvi.reduceRegion(ee.Reducer.mean(), roi, 10).getInfo()
        stats_evi = evi.reduceRegion(ee.Reducer.mean(), roi, 10).getInfo()
        stats_ndwi = ndwi.reduceRegion(ee.Reducer.mean(), roi, 10).getInfo()

        # Generate thumbnail URL
        vis_params = {"min": 0, "max": 1, "palette": ["red", "yellow", "green"]}
        thumb_url = ndvi.getThumbURL({**vis_params, "region": roi, "dimensions": "256x256"})

        return {
            "ndvi_mean": round(stats_ndvi.get("NDVI", 0), 4),
            "evi_mean": round(stats_evi.get("EVI", 0), 4),
            "ndwi_mean": round(stats_ndwi.get("NDWI", 0), 4),
            "image_date": image.get("system:time_start").getInfo(),
            "image_url": thumb_url,
            "source": "earth_engine",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Simulated NDVI data for demo
# ---------------------------------------------------------------------------

# Crop-specific NDVI benchmarks (typical healthy ranges)
CROP_BENCHMARKS = {
    "tomato": {"healthy_ndvi": (0.55, 0.80), "peak_ndvi": 0.75, "growth_days": 120},
    "wheat": {"healthy_ndvi": (0.45, 0.75), "peak_ndvi": 0.70, "growth_days": 150},
    "rice": {"healthy_ndvi": (0.50, 0.80), "peak_ndvi": 0.78, "growth_days": 135},
    "apple": {"healthy_ndvi": (0.50, 0.85), "peak_ndvi": 0.80, "growth_days": 200},
    "coffee": {"healthy_ndvi": (0.55, 0.85), "peak_ndvi": 0.82, "growth_days": 300},
    "potato": {"healthy_ndvi": (0.45, 0.70), "peak_ndvi": 0.65, "growth_days": 90},
    "maize": {"healthy_ndvi": (0.50, 0.80), "peak_ndvi": 0.76, "growth_days": 110},
}


def _simulate_ndvi(lat: float, lon: float, crop: str) -> dict:
    """Generate realistic simulated NDVI data for demo."""
    # Use location as seed for reproducible "random" values
    seed = int(abs(lat * 1000 + lon * 100)) % 10000
    rng = random.Random(seed)

    benchmark = CROP_BENCHMARKS.get(crop.lower(), CROP_BENCHMARKS["tomato"])
    low, high = benchmark["healthy_ndvi"]

    # Simulate slightly stressed crop
    ndvi_mean = round(rng.uniform(low - 0.10, high), 4)
    evi_mean = round(ndvi_mean * rng.uniform(0.65, 0.80), 4)
    ndwi_mean = round(rng.uniform(0.05, 0.30), 4)

    # Determine health status
    if ndvi_mean >= benchmark["peak_ndvi"] * 0.9:
        status = "healthy"
        trend = "stable"
    elif ndvi_mean >= benchmark["peak_ndvi"] * 0.7:
        status = "moderate_stress"
        trend = "declining_slightly"
    else:
        status = "severe_stress"
        trend = "declining_sharply"

    image_date = (datetime.utcnow() - timedelta(days=rng.randint(1, 5))).strftime("%Y-%m-%d")

    return {
        "ndvi_mean": ndvi_mean,
        "evi_mean": evi_mean,
        "ndwi_mean": ndwi_mean,
        "health_status": status,
        "trend": trend,
        "crop": crop,
        "benchmark_range": list(benchmark["healthy_ndvi"]),
        "image_date": image_date,
        "image_url": f"https://earthengine.googleapis.com/v1/demo/ndvi_thumb_{seed}.png",
        "source": "simulated_demo",
    }


@functions_framework.http
def compute_ndvi(request):
    """
    HTTP Cloud Function entry point.

    Query params or JSON body:
        lat (float): Latitude.
        lon (float): Longitude.
        crop (str): Crop name (default: tomato).
        radius_m (int): Analysis radius in metres (default: 500).

    Returns:
        JSON with ndvi_mean, evi_mean, ndwi_mean, trend, image_url.
    """
    if request.is_json:
        body = request.get_json(silent=True) or {}
        lat = float(body.get("lat", 0))
        lon = float(body.get("lon", 0))
        crop = body.get("crop", "tomato")
        radius_m = int(body.get("radius_m", 500))
    else:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
        crop = request.args.get("crop", "tomato")
        radius_m = int(request.args.get("radius_m", 500))

    if lat == 0 and lon == 0:
        return json.dumps({"error": "Missing 'lat' and 'lon' parameters"}), 400, {"Content-Type": "application/json"}

    # Try Earth Engine first
    ee_result = _compute_via_earth_engine(lat, lon, crop, radius_m)
    if ee_result:
        result = ee_result
    else:
        result = _simulate_ndvi(lat, lon, crop)

    result["lat"] = lat
    result["lon"] = lon
    result["radius_m"] = radius_m

    return json.dumps(result), 200, {"Content-Type": "application/json"}
