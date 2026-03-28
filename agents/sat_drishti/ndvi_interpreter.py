"""
NDVI interpretation and crop health assessment logic.

Translates raw spectral indices into actionable health categories,
compares against regional benchmarks, and computes temporal trends.
"""

import logging
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RegionalBenchmark(BaseModel):
    """Expected NDVI range for a crop in a given region and growth stage."""
    crop: str
    region: str
    expected_ndvi_min: float
    expected_ndvi_max: float
    growth_stage: Optional[str] = None


class CropHealthAssessment(BaseModel):
    """Structured assessment returned to the agent."""
    ndvi: float
    category: str = Field(
        ..., description="bare_soil | stressed | moderate | healthy | peak"
    )
    trend: str = Field(
        ..., description="improving | declining | stable"
    )
    trend_slope: float = Field(
        ..., description="Linear regression slope of NDVI over time (per day)"
    )
    benchmark_comparison: Optional[str] = Field(
        None,
        description="How the observed NDVI compares to the regional benchmark",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence level (0-1) based on data quality signals",
    )
    summary: str = Field(
        ..., description="Human-readable one-line summary"
    )


# ---------------------------------------------------------------------------
# NDVI category lookup
# ---------------------------------------------------------------------------

_NDVI_CATEGORIES: list[tuple[float, float, str]] = [
    (0.0, 0.1, "bare_soil"),
    (0.1, 0.3, "stressed"),
    (0.3, 0.5, "moderate"),
    (0.5, 0.7, "healthy"),
    (0.7, 0.9, "peak"),
]


def classify_ndvi(ndvi: float) -> str:
    """Map an NDVI value to a descriptive category."""
    if ndvi < 0.0:
        return "bare_soil"  # water or shadow
    for lo, hi, label in _NDVI_CATEGORIES:
        if lo <= ndvi < hi:
            return label
    # NDVI >= 0.9 is extremely dense vegetation — still "peak"
    return "peak"


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------

def _compute_trend(dates: list[str], values: list[float]) -> tuple[str, float]:
    """
    Fit a simple linear regression to the NDVI time series and classify
    the trend as improving / declining / stable.

    Returns (trend_label, slope_per_day).
    """
    if len(values) < 2:
        return "stable", 0.0

    # Convert dates to ordinal days for regression
    from datetime import datetime
    day_offsets = np.array([
        (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")).days
        for d in dates
    ], dtype=float)

    y = np.array(values, dtype=float)

    # numpy polyfit degree-1 → [slope, intercept]
    slope, _ = np.polyfit(day_offsets, y, 1)

    # Threshold: a slope of +/-0.001 NDVI per day is roughly +/-0.03/month
    if slope > 0.001:
        label = "improving"
    elif slope < -0.001:
        label = "declining"
    else:
        label = "stable"

    return label, round(float(slope), 6)


# ---------------------------------------------------------------------------
# Benchmark comparison
# ---------------------------------------------------------------------------

def _compare_to_benchmark(
    ndvi: float,
    benchmark: Optional[RegionalBenchmark],
) -> Optional[str]:
    """Return a human-readable comparison to the regional benchmark."""
    if benchmark is None:
        return None

    mid = (benchmark.expected_ndvi_min + benchmark.expected_ndvi_max) / 2
    range_str = f"{benchmark.expected_ndvi_min:.2f}–{benchmark.expected_ndvi_max:.2f}"

    if ndvi < benchmark.expected_ndvi_min:
        delta_pct = abs(ndvi - benchmark.expected_ndvi_min) / mid * 100
        return (
            f"Below regional benchmark for {benchmark.crop} in {benchmark.region} "
            f"(expected {range_str}, observed {ndvi:.2f} — {delta_pct:.0f}% below midpoint)"
        )
    elif ndvi > benchmark.expected_ndvi_max:
        delta_pct = abs(ndvi - benchmark.expected_ndvi_max) / mid * 100
        return (
            f"Above regional benchmark for {benchmark.crop} in {benchmark.region} "
            f"(expected {range_str}, observed {ndvi:.2f} — {delta_pct:.0f}% above midpoint)"
        )
    else:
        return (
            f"Within expected range for {benchmark.crop} in {benchmark.region} "
            f"(expected {range_str}, observed {ndvi:.2f})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret(
    ndvi: float,
    time_series: list[dict],
    benchmark: Optional[RegionalBenchmark] = None,
    cloud_fallback: bool = False,
    num_images: int = 1,
) -> CropHealthAssessment:
    """
    Produce a structured crop health assessment.

    Parameters
    ----------
    ndvi : float
        Current mean NDVI for the field.
    time_series : list[dict]
        List of ``{"date": "YYYY-MM-DD", "ndvi": float}`` entries.
    benchmark : RegionalBenchmark, optional
        Regional/crop benchmark to compare against.
    cloud_fallback : bool
        Whether the satellite data required a cloud-cover fallback.
    num_images : int
        Number of clear images found — more images = higher confidence.

    Returns
    -------
    CropHealthAssessment
    """
    category = classify_ndvi(ndvi)

    dates = [p["date"] for p in time_series]
    values = [p["ndvi"] for p in time_series]
    trend, slope = _compute_trend(dates, values)

    benchmark_comparison = _compare_to_benchmark(ndvi, benchmark)

    # Confidence heuristic: base 0.8, penalise for cloud fallback and
    # low image count, bonus for long time series
    confidence = 0.8
    if cloud_fallback:
        confidence -= 0.15
    if num_images >= 5:
        confidence += 0.1
    elif num_images <= 1:
        confidence -= 0.1
    if len(time_series) >= 6:
        confidence += 0.05
    confidence = round(max(0.1, min(1.0, confidence)), 2)

    # Build readable summary
    trend_word = {"improving": "improving", "declining": "declining", "stable": "stable"}[trend]
    summary = f"Crop health is {category.replace('_', ' ')} (NDVI {ndvi:.2f}), trend {trend_word}."
    if benchmark_comparison:
        summary += f" {benchmark_comparison}."

    return CropHealthAssessment(
        ndvi=round(ndvi, 4),
        category=category,
        trend=trend,
        trend_slope=slope,
        benchmark_comparison=benchmark_comparison,
        confidence=confidence,
        summary=summary,
    )
