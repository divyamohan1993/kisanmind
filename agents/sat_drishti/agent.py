"""
SatDrishti (Satellite Eye) — ADK agent for crop health monitoring.

Takes a farmer's location and crop type, pulls Sentinel-2 satellite imagery
via Earth Engine, interprets spectral indices, and returns a plain-language
crop health assessment using Gemini.

Guardrails
----------
- Never recommends specific pesticide brands or dosages.
- Always includes a confidence level with its assessment.
- Falls back gracefully when satellite data is unavailable.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from pydantic import BaseModel, Field

from .earth_engine import fetch_satellite_data
from .ndvi_interpreter import (
    CropHealthAssessment,
    RegionalBenchmark,
    interpret,
)

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SatDrishtiRequest(BaseModel):
    """Input expected by the satellite analysis tool."""
    lat: float = Field(..., description="Latitude of the field")
    lon: float = Field(..., description="Longitude of the field")
    crop: str = Field(..., description="Crop type (e.g. 'tomato', 'wheat', 'rice')")
    region: Optional[str] = Field(
        None, description="Region name for benchmark lookup (e.g. 'Solan', 'Punjab')"
    )
    benchmark_ndvi_min: Optional[float] = Field(
        None, description="Expected NDVI lower bound for this crop/region"
    )
    benchmark_ndvi_max: Optional[float] = Field(
        None, description="Expected NDVI upper bound for this crop/region"
    )


class SatDrishtiResponse(BaseModel):
    """Structured output from the satellite analysis tool."""
    assessment: CropHealthAssessment
    image_date: str
    thumbnail_url: Optional[str] = None
    cloud_fallback: bool = False
    warning: Optional[str] = None


# ---------------------------------------------------------------------------
# Guardrail: scrub pesticide brand / dosage recommendations
# ---------------------------------------------------------------------------

_PESTICIDE_GUARDRAIL_NOTE = (
    "Note: For any pest or disease issues, consult your local Krishi Vigyan "
    "Kendra (KVK) or agricultural extension officer for approved treatment "
    "recommendations. SatDrishti does not prescribe specific pesticide "
    "brands or dosages."
)


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------

def analyze_crop_health(
    lat: float,
    lon: float,
    crop: str,
    region: str = "",
    benchmark_ndvi_min: float = 0.0,
    benchmark_ndvi_max: float = 0.0,
) -> dict:
    """
    Fetch satellite imagery for a field and return a crop health assessment.

    Parameters
    ----------
    lat : float
        Field latitude.
    lon : float
        Field longitude.
    crop : str
        Crop being grown (e.g. 'wheat', 'rice', 'tomato').
    region : str
        Optional region name for benchmark comparison.
    benchmark_ndvi_min : float
        Optional lower NDVI benchmark for this crop/region.
    benchmark_ndvi_max : float
        Optional upper NDVI benchmark for this crop/region.

    Returns
    -------
    dict
        Structured crop health assessment including NDVI category, trend,
        confidence, benchmark comparison, thumbnail URL, and advisory notes.
    """
    try:
        sat_data = fetch_satellite_data(lat=lat, lon=lon)
    except RuntimeError as exc:
        logger.error("Satellite fetch failed for (%s, %s): %s", lat, lon, exc)
        return {
            "error": str(exc),
            "advice": (
                "Satellite imagery is currently unavailable for this location. "
                "Please try again later or consult local observations."
            ),
        }

    # Build benchmark if both bounds were supplied
    benchmark: Optional[RegionalBenchmark] = None
    if benchmark_ndvi_min > 0 and benchmark_ndvi_max > 0:
        benchmark = RegionalBenchmark(
            crop=crop,
            region=region or "unknown",
            expected_ndvi_min=benchmark_ndvi_min,
            expected_ndvi_max=benchmark_ndvi_max,
        )

    assessment = interpret(
        ndvi=sat_data.mean_indices.ndvi,
        time_series=[pt.model_dump() for pt in sat_data.time_series],
        benchmark=benchmark,
        cloud_fallback=sat_data.cloud_fallback,
        num_images=len(sat_data.time_series),
    )

    result = SatDrishtiResponse(
        assessment=assessment,
        image_date=sat_data.image_date,
        thumbnail_url=sat_data.thumbnail_url,
        cloud_fallback=sat_data.cloud_fallback,
        warning=sat_data.warning,
    ).model_dump()

    # Attach guardrail note so downstream Gemini responses stay safe
    result["guardrail"] = _PESTICIDE_GUARDRAIL_NOTE
    return result


# ---------------------------------------------------------------------------
# ADK Agent definition
# ---------------------------------------------------------------------------

sat_drishti_tool = FunctionTool(func=analyze_crop_health)

sat_drishti_agent = Agent(
    name="sat_drishti",
    model=os.getenv("SAT_DRISHTI_MODEL", "gemini-2.0-flash"),
    description=(
        "SatDrishti (Satellite Eye) analyses crop health from space. "
        "Given a field location and crop type it fetches Sentinel-2 satellite "
        "imagery, computes vegetation indices (NDVI, EVI, NDWI), and provides "
        "a plain-language crop health assessment with confidence level."
    ),
    instruction=(
        "You are SatDrishti, the satellite intelligence layer of KisanMind.\n\n"
        "When the user provides a location (latitude/longitude) and crop type:\n"
        "1. Call the analyze_crop_health tool with the provided coordinates and crop.\n"
        "2. Interpret the returned assessment in simple, farmer-friendly language.\n"
        "3. Always mention the NDVI value, health category, and trend direction.\n"
        "4. If a benchmark comparison is available, explain whether the crop is\n"
        "   performing above, within, or below expectations for the region.\n"
        "5. Include the confidence level and explain if it is lower than normal\n"
        "   (e.g. due to cloud cover fallback).\n"
        "6. If the trend is declining, suggest the farmer inspect the field for\n"
        "   possible water stress, nutrient deficiency, or pest issues — but\n"
        "   NEVER recommend specific pesticide brands or dosages.\n"
        "7. Respond in the same language the user spoke in.\n\n"
        "GUARDRAILS — you MUST follow these:\n"
        "- NEVER recommend specific pesticide brand names.\n"
        "- NEVER suggest specific chemical dosages.\n"
        "- ALWAYS direct pest/disease concerns to the local KVK or extension officer.\n"
        "- ALWAYS include the confidence level in your response.\n"
        "- If satellite data is unavailable, say so honestly and suggest retrying later."
    ),
    tools=[sat_drishti_tool],
)
