"""
Earth Engine integration for SatDrishti.

Connects to Google Earth Engine (project 'dmjone') to fetch Sentinel-2
imagery, compute vegetation/water indices, and generate thumbnail URLs.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import ee
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class IndexValues(BaseModel):
    """Computed spectral indices for a single image or aggregation."""
    ndvi: float = Field(..., description="Normalized Difference Vegetation Index")
    evi: float = Field(..., description="Enhanced Vegetation Index")
    ndwi: float = Field(..., description="Normalized Difference Water Index")


class TimeSeriesPoint(BaseModel):
    """One data point in a temporal index series."""
    date: str
    ndvi: float


class SatelliteResult(BaseModel):
    """Full result returned to the agent from an Earth Engine query."""
    mean_indices: IndexValues
    time_series: list[TimeSeriesPoint] = Field(
        default_factory=list,
        description="NDVI time series over the past ~3 months",
    )
    thumbnail_url: Optional[str] = Field(
        None, description="False-color composite thumbnail URL"
    )
    image_date: str = Field(..., description="Date of the imagery used (YYYY-MM-DD)")
    cloud_fallback: bool = Field(
        False,
        description="True if we fell back to an older image due to cloud cover",
    )
    warning: Optional[str] = None


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

_initialized = False


def _ensure_initialized() -> None:
    """Initialize Earth Engine once per process."""
    global _initialized
    if _initialized:
        return
    try:
        ee.Initialize(project="dmjone")
        _initialized = True
        logger.info("Earth Engine initialized (project=dmjone)")
    except Exception as exc:
        logger.error("Earth Engine initialization failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cloud_mask_s2(image: ee.Image) -> ee.Image:
    """Mask clouds and cirrus using the Sentinel-2 SCL band."""
    scl = image.select("SCL")
    # Keep vegetation(4), bare soil(5), water(6) — mask cloud shadows(3),
    # cloud medium(8), cloud high(9), cirrus(10)
    clear = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return image.updateMask(clear)


def _add_indices(image: ee.Image) -> ee.Image:
    """Add NDVI, EVI, and NDWI bands to a Sentinel-2 image."""
    # NDVI = (B8 - B4) / (B8 + B4)
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # EVI = 2.5 * (B8 - B4) / (B8 + 6*B4 - 7.5*B2 + 1)
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    blue = image.select("B2").divide(10000)
    evi = (
        nir.subtract(red)
        .multiply(2.5)
        .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
        .rename("EVI")
    )

    # NDWI = (B3 - B8) / (B3 + B8)
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")

    return image.addBands([ndvi, evi, ndwi])


def _get_collection(
    point: ee.Geometry.Point,
    start_date: str,
    end_date: str,
) -> ee.ImageCollection:
    """Return cloud-masked, index-augmented Sentinel-2 SR collection."""
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate(start_date, end_date)
        .map(_cloud_mask_s2)
        .map(_add_indices)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_satellite_data(
    lat: float,
    lon: float,
    days_back: int = 30,
    buffer_m: int = 500,
) -> SatelliteResult:
    """
    Fetch satellite indices for *lat/lon* over the last *days_back* days.

    A 500 m buffer around the point is used for spatial averaging.  If no
    clear imagery is found in the primary window, the search expands to 90
    days and a warning is attached.

    Returns a ``SatelliteResult`` with mean indices, a 3-month NDVI time
    series, and a false-color thumbnail URL.
    """
    _ensure_initialized()

    point = ee.Geometry.Point([lon, lat])
    roi = point.buffer(buffer_m)
    now = datetime.utcnow()

    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

    collection = _get_collection(point, start_date, end_date)
    count = collection.size().getInfo()

    cloud_fallback = False
    warning = None

    # Fallback: expand window if nothing clear in the primary range
    if count == 0:
        logger.warning(
            "No clear Sentinel-2 imagery in last %d days — expanding to 90 days",
            days_back,
        )
        start_date = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        collection = _get_collection(point, start_date, end_date)
        count = collection.size().getInfo()
        cloud_fallback = True
        warning = (
            f"No clear imagery in the last {days_back} days due to cloud cover. "
            "Using the most recent clear image available (up to 90 days back)."
        )

    if count == 0:
        raise RuntimeError(
            "No usable Sentinel-2 imagery found for this location in the last 90 days."
        )

    # --- Mean indices from the most recent clear composite ----------------
    latest = collection.sort("system:time_start", False).first()
    image_date_ms = latest.get("system:time_start").getInfo()
    image_date = datetime.utcfromtimestamp(image_date_ms / 1000).strftime("%Y-%m-%d")

    means = latest.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=10,
        maxPixels=1e8,
    ).getInfo()

    mean_indices = IndexValues(
        ndvi=round(means.get("NDVI", 0.0) or 0.0, 4),
        evi=round(means.get("EVI", 0.0) or 0.0, 4),
        ndwi=round(means.get("NDWI", 0.0) or 0.0, 4),
    )

    # --- 3-month NDVI time series -----------------------------------------
    ts_start = (now - timedelta(days=90)).strftime("%Y-%m-%d")
    ts_collection = _get_collection(point, ts_start, end_date)

    def _extract_ndvi(img: ee.Image) -> ee.Feature:
        """Reduce one image to mean NDVI over the ROI."""
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=10,
            maxPixels=1e8,
        )
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            "ndvi": stats.get("NDVI"),
        })

    ts_features = ts_collection.map(_extract_ndvi).getInfo()
    time_series: list[TimeSeriesPoint] = []
    for feat in ts_features.get("features", []):
        props = feat.get("properties", {})
        ndvi_val = props.get("ndvi")
        if ndvi_val is not None:
            time_series.append(
                TimeSeriesPoint(date=props["date"], ndvi=round(ndvi_val, 4))
            )
    time_series.sort(key=lambda p: p.date)

    # --- False-color thumbnail (B8/B4/B3 = NIR/Red/Green) -----------------
    vis_params = {
        "bands": ["B8", "B4", "B3"],
        "min": 0,
        "max": 5000,
        "dimensions": 512,
        "region": roi,
        "format": "png",
    }
    try:
        thumbnail_url = latest.getThumbURL(vis_params)
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        thumbnail_url = None

    return SatelliteResult(
        mean_indices=mean_indices,
        time_series=time_series,
        thumbnail_url=thumbnail_url,
        image_date=image_date,
        cloud_fallback=cloud_fallback,
        warning=warning,
    )
