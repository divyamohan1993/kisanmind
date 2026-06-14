"""
KisanMind — crop-growth parameter engine (the 80/20 remote-sensing set).

Pure functions only (stdlib + math). NO fastapi / earthengine / google-cloud imports here,
so this module is importable and unit-testable in any environment, including offline.

Why these parameters:
A small set of optical/biophysical signals explains most of what "crop growth" means in
remote sensing. NDVI alone saturates in dense canopy, says nothing about water or nitrogen,
and lies during senescence. Pairing greenness (NDVI/EVI/SAVI) with chlorophyll/nitrogen
(NDRE/GNDVI/CIre), canopy water (NDMI/NMDI), structure/biomass (LAI/FAPAR/SAR) and
senescence (PSRI) gives a far truer, harder-to-fool picture — and lets us *predict*, not
just *map*. This module computes the optical family from Sentinel-2 reflectance; thermal,
soil-moisture and agro-climate signals are sourced elsewhere (MODIS/SMAP/NASA POWER/
Open-Meteo) and merged via the registry below.

Critical correctness note (scaling):
Sentinel-2 SR Harmonized stores reflectance as integer DN scaled by 1e-4 (range ~0-10000).
Ratio / normalized-difference indices (NDVI, NDRE, NDMI, ...) are scale-invariant.
Indices with an *additive constant* (EVI's "+1", SAVI's "+L", MSAVI) are NOT — they MUST be
fed true reflectance (0-1). Feeding raw DN produces garbage (e.g. EVI ≈ 2.0, impossible).
The existing cache has exactly this bug; `compute_s2_indices` always works in reflectance.
"""

from __future__ import annotations

import math
from typing import Optional

# Sentinel-2 SR Harmonized DN -> reflectance scale factor.
S2_DN_SCALE = 1e-4

# Plausible output ranges per index — used to null out impossible values (sanity gate)
# so a single bad band can never poison the advisory or the verifier.
INDEX_VALID_RANGE = {
    "ndvi": (-1.0, 1.0), "evi": (-1.0, 1.0), "savi": (-1.5, 1.5), "msavi": (-1.0, 1.0),
    "ndre": (-1.0, 1.0), "gndvi": (-1.0, 1.0), "ci_rededge": (-1.0, 12.0),
    "psri": (-1.0, 1.0), "ndmi": (-1.0, 1.0), "nmdi": (-1.0, 1.0),
    "ndwi_water": (-1.0, 1.0), "nbr": (-1.0, 1.0), "lai": (0.0, 8.0), "fapar": (0.0, 1.0),
    "otci": (0.0, 6.0),  # Sentinel-3 OLCI Terrestrial Chlorophyll Index
    # v3.1 expansion — distinct pigment / stress / soil / robustness signals
    "ccci": (0.0, 2.0),     # canopy chlorophyll content (nitrogen, biomass-decoupled)
    "mtci": (0.0, 10.0),    # red-edge chlorophyll
    "s2rep": (680.0, 760.0),  # red-edge inflection position (nm)
    "ari": (-2.0, 25.0),    # anthocyanin (reciprocal-reflectance scale ~0-20)
    "dswi": (0.0, 10.0),    # disease-water stress index
    "arvi": (-1.0, 1.0),    # atmospherically-resistant greenness (haze-robust)
    "vari": (-1.5, 1.5),    # visible-band greenness (NIR-independent)
    "wdrvi": (-1.0, 1.0),   # wide dynamic range (high-biomass sensitivity)
    "bsi": (-1.0, 1.0),     # bare soil index (germination gaps / residue)
    "ndti": (-1.0, 1.0),    # tillage / crop-residue index
}


def _safe_div(num: float, den: float) -> Optional[float]:
    """Division that returns None instead of blowing up on a zero/None denominator."""
    if den is None or num is None or den == 0:
        return None
    return num / den


def _clamp(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    if v is None:
        return None
    return max(lo, min(hi, v))


def _round(v: Optional[float], n: int = 4) -> Optional[float]:
    return round(v, n) if v is not None else None


def _in_range(key: str, v: Optional[float]) -> Optional[float]:
    """Return v only if it falls inside the index's physically-plausible range, else None."""
    if v is None:
        return None
    lo, hi = INDEX_VALID_RANGE.get(key, (-math.inf, math.inf))
    return v if lo <= v <= hi else None


def to_reflectance(bands: dict, already_reflectance: bool = False) -> dict:
    """Normalise a band dict to reflectance (0-1).

    `bands` keys are Sentinel-2 band names (B2,B3,B4,B5,B6,B7,B8,B8A,B11,B12). Values may be
    raw DN (0-10000) or already reflectance. Missing/None bands are dropped.
    """
    out = {}
    for k, v in bands.items():
        if v is None:
            continue
        out[k] = float(v) if already_reflectance else float(v) * S2_DN_SCALE
    return out


def compute_s2_indices(bands: dict, already_reflectance: bool = False) -> dict:
    """Compute the Sentinel-2 optical/biophysical parameter set from band reflectances.

    Returns a dict of index -> value (or None when required bands are absent). Every value is
    range-checked so impossible outputs become None rather than propagating.
    """
    b = to_reflectance(bands, already_reflectance=already_reflectance)
    B2, B3, B4 = b.get("B2"), b.get("B3"), b.get("B4")
    B5, B6, B7 = b.get("B5"), b.get("B6"), b.get("B7")
    B8, B8A = b.get("B8") or b.get("B8A"), b.get("B8A")
    B11, B12 = b.get("B11"), b.get("B12")

    out: dict = {}

    # --- Greenness / biomass ---
    out["ndvi"] = _safe_div((B8 - B4), (B8 + B4)) if B8 is not None and B4 is not None else None
    # EVI needs true reflectance (additive +1). This is the line the old cache got wrong.
    if None not in (B8, B4, B2):
        out["evi"] = _safe_div(2.5 * (B8 - B4), (B8 + 6 * B4 - 7.5 * B2 + 1.0))
    else:
        out["evi"] = None
    # SAVI (L=0.5) soil-adjusted — better than NDVI for sparse/early canopy.
    if None not in (B8, B4):
        out["savi"] = _safe_div(1.5 * (B8 - B4), (B8 + B4 + 0.5))
        # MSAVI2 — self-adjusting soil factor, best at emergence.
        disc = (2 * B8 + 1) ** 2 - 8 * (B8 - B4)
        out["msavi"] = (2 * B8 + 1 - math.sqrt(disc)) / 2 if disc >= 0 else None
    else:
        out["savi"] = out["msavi"] = None

    # --- Chlorophyll / nitrogen (red-edge family) ---
    out["ndre"] = _safe_div((B8 - B5), (B8 + B5)) if None not in (B8, B5) else None
    out["gndvi"] = _safe_div((B8 - B3), (B8 + B3)) if None not in (B8, B3) else None
    out["ci_rededge"] = (_safe_div(B7, B5) - 1) if (B7 is not None and B5) else None

    # --- Senescence / ripening (harvest timing) ---
    out["psri"] = _safe_div((B4 - B2), B6) if None not in (B4, B2, B6) else None

    # --- Canopy / soil water ---
    out["ndmi"] = _safe_div((B8 - B11), (B8 + B11)) if None not in (B8, B11) else None
    if None not in (B8, B11, B12):
        swir = B11 - B12
        out["nmdi"] = _safe_div((B8 - swir), (B8 + swir))
    else:
        out["nmdi"] = None
    # McFeeters NDWI — open water / waterlogging (NOT canopy water; relabelled clearly).
    out["ndwi_water"] = _safe_div((B3 - B8), (B3 + B8)) if None not in (B3, B8) else None

    # --- Structural stress ---
    out["nbr"] = _safe_div((B8 - B12), (B8 + B12)) if None not in (B8, B12) else None

    # --- Biophysical (indicative empirical proxies, clearly flagged downstream) ---
    out["lai"] = _lai_from_savi(out.get("savi"))
    out["fapar"] = _fapar_from_ndvi(out.get("ndvi"))

    # --- Expansion set: pigment / stress / soil / robustness (distinct signals) ---
    # Nitrogen decoupled from biomass: red-edge greenness ÷ broadband greenness.
    out["ccci"] = _safe_div(out.get("ndre"), out.get("ndvi")) if out.get("ndvi") else None
    # Red-edge chlorophyll (S2-native MTCI) and red-edge inflection position (nm).
    out["mtci"] = _safe_div((B6 - B5), (B5 - B4)) if None not in (B6, B5, B4) else None
    if None not in (B4, B5, B6, B7) and (B6 - B5) != 0:
        out["s2rep"] = 705.0 + 35.0 * (((B7 + B4) / 2.0 - B5) / (B6 - B5))
    else:
        out["s2rep"] = None
    # Anthocyanin (stress/senescence pigment): reciprocal-reflectance form.
    out["ari"] = ((1.0 / B3) - (1.0 / B5)) if (B3 and B5) else None
    # Disease-Water Stress Index — drops under fungal/water stress (KVK trigger).
    out["dswi"] = _safe_div((B8 + B3), (B11 + B4)) if None not in (B8, B3, B11, B4) else None
    # Haze-robust and NIR-independent greenness (dust/haze-prone India, cloud edges).
    if None not in (B8, B4, B2):
        rb = 2 * B4 - B2
        out["arvi"] = _safe_div((B8 - rb), (B8 + rb))
    else:
        out["arvi"] = None
    out["vari"] = _safe_div((B3 - B4), (B3 + B4 - B2)) if None not in (B3, B4, B2) else None
    # Wide Dynamic Range VI — sensitive where NDVI saturates (dense late-season canopy).
    out["wdrvi"] = _safe_div((0.2 * B8 - B4), (0.2 * B8 + B4)) if None not in (B8, B4) else None
    # Bare Soil Index (germination gaps, post-harvest) and tillage/residue index.
    if None not in (B11, B4, B8, B2):
        num = (B11 + B4) - (B8 + B2)
        den = (B11 + B4) + (B8 + B2)
        out["bsi"] = _safe_div(num, den)
    else:
        out["bsi"] = None
    out["ndti"] = _safe_div((B11 - B12), (B11 + B12)) if None not in (B11, B12) else None

    # Range-gate everything and round.
    return {k: _round(_in_range(k, v)) for k, v in out.items()}


def _lai_from_savi(savi: Optional[float]) -> Optional[float]:
    """Leaf Area Index from SAVI (indicative). Exponential relation (Boegh et al. 2002 form):
    LAI = -(1/0.91) * ln((0.69 - SAVI)/0.59), valid for SAVI < 0.69. Clamped [0, 7]."""
    if savi is None or savi >= 0.69:
        return 7.0 if (savi is not None and savi >= 0.69) else None
    ratio = (0.69 - savi) / 0.59
    if ratio <= 0:
        return 7.0
    return _clamp(-(1.0 / 0.91) * math.log(ratio), 0.0, 7.0)


def _fapar_from_ndvi(ndvi: Optional[float]) -> Optional[float]:
    """Fraction of absorbed PAR from NDVI (indicative linear proxy): FAPAR ≈ 1.24*NDVI - 0.168,
    clamped [0, 0.95]. A widely-used first-order approximation; not a calibrated product."""
    if ndvi is None:
        return None
    return _clamp(1.24 * ndvi - 0.168, 0.0, 0.95)


# ---------------------------------------------------------------------------
# Classification + farmer-language interpretation
# ---------------------------------------------------------------------------
def classify_ndvi(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    if v >= 0.7:
        return "very_healthy"
    if v >= 0.6:
        return "healthy"
    if v >= 0.4:
        return "moderate"
    if v >= 0.2:
        return "stressed"
    return "bare"


def classify_ndre(v: Optional[float]) -> str:
    """Red-edge chlorophyll/nitrogen status."""
    if v is None:
        return "unknown"
    if v >= 0.4:
        return "high"        # vigorous, well-nourished
    if v >= 0.25:
        return "adequate"
    if v >= 0.15:
        return "low"         # possible nitrogen deficiency
    return "deficient"


def classify_ndmi(v: Optional[float]) -> str:
    """Canopy water content / moisture stress."""
    if v is None:
        return "unknown"
    if v >= 0.3:
        return "well_watered"
    if v >= 0.1:
        return "adequate"
    if v >= 0.0:
        return "mild_stress"
    return "water_stress"


def classify_psri(v: Optional[float]) -> str:
    """Senescence / ripening. Rising PSRI = canopy ageing → approaching harvest."""
    if v is None:
        return "unknown"
    if v >= 0.2:
        return "senescing"   # ripening / drying — harvest window approaching
    if v >= 0.1:
        return "early_senescence"
    return "green"           # actively growing


def classify_lai(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    if v >= 4.0:
        return "dense"
    if v >= 2.0:
        return "moderate"
    if v >= 0.8:
        return "sparse"
    return "very_sparse"


def classify_otci(v: Optional[float]) -> str:
    """Sentinel-3 OLCI chlorophyll. Corroborates NDRE from an independent satellite."""
    if v is None:
        return "unknown"
    if v >= 3.0:
        return "high"
    if v >= 2.0:
        return "adequate"
    if v >= 1.0:
        return "low"
    return "deficient"


def classify_ccci(v: Optional[float]) -> str:
    """Canopy chlorophyll / nitrogen status, decoupled from biomass (NDRE÷NDVI)."""
    if v is None:
        return "unknown"
    if v >= 0.7:
        return "high"
    if v >= 0.5:
        return "adequate"
    if v >= 0.35:
        return "low"
    return "deficient"


def classify_dswi(v: Optional[float]) -> str:
    """Disease-Water Stress Index. Drops under fungal infection or water stress."""
    if v is None:
        return "unknown"
    if v >= 1.5:
        return "healthy"
    if v >= 1.0:
        return "watch"
    return "stress"   # possible disease/water stress → field inspection / KVK


def classify_bsi(v: Optional[float]) -> str:
    """Bare Soil Index — high = exposed soil (germination gaps, post-harvest)."""
    if v is None:
        return "unknown"
    if v >= 0.1:
        return "bare"
    if v >= -0.05:
        return "sparse"
    return "vegetated"


def classify_ari(v: Optional[float]) -> str:
    """Anthocyanin Reflectance Index (reciprocal-reflectance scale ~0-20). Rises with
    stress/senescence pigments. Generic thresholds are indicative — used as a relative signal,
    not a farmer-facing claim, since absolute calibration is crop/condition specific."""
    if v is None:
        return "unknown"
    if v >= 12.0:
        return "stress"
    if v >= 7.0:
        return "mild"
    return "normal"


# Plain-language templates. Deliberately jargon-free: the farmer never hears "NDRE".
# {status} is filled from the classify_* result; downstream translation handles language.
_FARMER_LINES = {
    "ndvi": {
        "very_healthy": "Your crop canopy is very green and vigorous.",
        "healthy": "Your crop looks healthy and green.",
        "moderate": "Your crop is doing okay but not at its best.",
        "stressed": "Your crop looks weak — it may be under stress.",
        "bare": "Very little green cover is visible — the field looks bare or just sown.",
    },
    "ndre": {
        "high": "Leaf colour is rich — nitrogen and chlorophyll look strong.",
        "adequate": "Leaf nourishment looks adequate.",
        "low": "Leaf colour suggests the crop may be a little short on nitrogen.",
        "deficient": "Leaves may be low on nitrogen — worth checking with your KVK.",
    },
    "ndmi": {
        "well_watered": "The leaves are holding plenty of water.",
        "adequate": "Leaf moisture is adequate.",
        "mild_stress": "Leaves are starting to lose moisture — watch watering.",
        "water_stress": "Leaves show water stress — the crop likely needs water.",
    },
    "psri": {
        "green": "The crop is still actively growing, not yet ageing.",
        "early_senescence": "The crop is beginning to mature.",
        "senescing": "The crop is ripening — harvest time is approaching.",
    },
    "lai": {
        "dense": "Leaf cover is thick and full.",
        "moderate": "Leaf cover is reasonable.",
        "sparse": "Leaf cover is thin.",
        "very_sparse": "Very little leaf cover yet.",
    },
    "dswi": {
        "healthy": "No sign of disease or water stress in the canopy.",
        "watch": "Early signs of stress — keep an eye on the leaves this week.",
        "stress": "The canopy shows possible disease or water stress — a field check with your KVK is wise.",
    },
    "ccci": {
        "high": "Nitrogen looks strong across the canopy.",
        "adequate": "Nitrogen nourishment looks adequate.",
        "low": "Nitrogen may be a little low — worth checking leaf colour.",
        "deficient": "Canopy nitrogen looks low — confirm with your KVK before any input.",
    },
    "bsi": {
        "bare": "Large bare patches — germination gaps or thin stand.",
        "sparse": "Some bare soil showing between plants.",
        "vegetated": "Good ground cover, little bare soil.",
    },
}


def farmer_line(param: str, status: str) -> str:
    return _FARMER_LINES.get(param, {}).get(status, "")


# ---------------------------------------------------------------------------
# Parameter registry — the single source of truth for "what we measure"
# ---------------------------------------------------------------------------
# family: greenness | chlorophyll | water | thermal | structure | climate | phenology
# source: which provider supplies it (s2=Sentinel-2, modis, sar, smap, power, openmeteo)
PARAMETER_REGISTRY = [
    {"key": "ndvi", "name": "Canopy greenness (NDVI)", "family": "greenness", "source": "s2",
     "measures": "Overall vegetation vigour and green biomass.", "kind": "index"},
    {"key": "evi", "name": "Enhanced vegetation (EVI)", "family": "greenness", "source": "s2",
     "measures": "Biomass in dense canopy without NDVI saturation.", "kind": "index"},
    {"key": "savi", "name": "Soil-adjusted greenness (SAVI)", "family": "greenness", "source": "s2",
     "measures": "Vigour corrected for bare-soil background (early season).", "kind": "index"},
    {"key": "msavi", "name": "Modified SAVI (MSAVI2)", "family": "greenness", "source": "s2",
     "measures": "Emergence-stage vigour with self-adjusting soil factor.", "kind": "index"},
    {"key": "ndre", "name": "Red-edge nitrogen (NDRE)", "family": "chlorophyll", "source": "s2",
     "measures": "Chlorophyll / nitrogen status, sensitive mid-late season.", "kind": "index"},
    {"key": "gndvi", "name": "Green chlorophyll (GNDVI)", "family": "chlorophyll", "source": "s2",
     "measures": "Chlorophyll concentration via green band.", "kind": "index"},
    {"key": "ci_rededge", "name": "Chlorophyll index (CIre)", "family": "chlorophyll", "source": "s2",
     "measures": "Canopy chlorophyll content.", "kind": "index"},
    {"key": "otci", "name": "OLCI chlorophyll (OTCI)", "family": "chlorophyll", "source": "sentinel3",
     "measures": "Chlorophyll from Sentinel-3 (independent satellite, near-daily).", "kind": "index"},
    {"key": "ccci", "name": "Canopy chlorophyll (CCCI)", "family": "chlorophyll", "source": "s2",
     "measures": "Nitrogen status decoupled from biomass.", "kind": "index"},
    {"key": "mtci", "name": "Red-edge chlorophyll (MTCI)", "family": "chlorophyll", "source": "s2",
     "measures": "Chlorophyll via S2 red-edge bands.", "kind": "index"},
    {"key": "s2rep", "name": "Red-edge position (S2REP)", "family": "chlorophyll", "source": "s2",
     "measures": "Red-edge inflection — nitrogen/stress shift.", "kind": "index"},
    {"key": "ari", "name": "Anthocyanin stress (ARI)", "family": "phenology", "source": "s2",
     "measures": "Stress / senescence pigment build-up.", "kind": "index"},
    {"key": "dswi", "name": "Disease-water stress (DSWI)", "family": "water", "source": "s2",
     "measures": "Fungal disease / water-stress canopy signal.", "kind": "index"},
    {"key": "arvi", "name": "Haze-robust greenness (ARVI)", "family": "greenness", "source": "s2",
     "measures": "Vigour corrected for haze/aerosol.", "kind": "index"},
    {"key": "vari", "name": "Visible greenness (VARI)", "family": "greenness", "source": "s2",
     "measures": "Greenness without NIR (cloud-edge robust).", "kind": "index"},
    {"key": "wdrvi", "name": "Wide-range vigour (WDRVI)", "family": "greenness", "source": "s2",
     "measures": "Biomass where NDVI saturates (late season).", "kind": "index"},
    {"key": "bsi", "name": "Bare soil (BSI)", "family": "structure", "source": "s2",
     "measures": "Exposed soil — germination gaps / residue.", "kind": "index"},
    {"key": "ndti", "name": "Tillage/residue (NDTI)", "family": "structure", "source": "s2",
     "measures": "Crop residue and tillage state.", "kind": "index"},
    {"key": "psri", "name": "Senescence (PSRI)", "family": "phenology", "source": "s2",
     "measures": "Plant ageing / ripening — harvest timing.", "kind": "index"},
    {"key": "ndmi", "name": "Canopy water (NDMI)", "family": "water", "source": "s2",
     "measures": "Leaf/canopy water content and moisture stress.", "kind": "index"},
    {"key": "nmdi", "name": "Drought index (NMDI)", "family": "water", "source": "s2",
     "measures": "Combined canopy + soil drought signal.", "kind": "index"},
    {"key": "ndwi_water", "name": "Surface water (NDWI)", "family": "water", "source": "s2",
     "measures": "Standing water / waterlogging detection.", "kind": "index"},
    {"key": "nbr", "name": "Structural stress (NBR)", "family": "structure", "source": "s2",
     "measures": "Severe stress / damage / residue.", "kind": "index"},
    {"key": "lai", "name": "Leaf area index (LAI)", "family": "structure", "source": "s2",
     "measures": "Total leaf area per ground area (indicative).", "kind": "biophysical"},
    {"key": "fapar", "name": "Light absorption (FAPAR)", "family": "structure", "source": "s2",
     "measures": "Share of sunlight the canopy captures (indicative).", "kind": "biophysical"},
    {"key": "lst_day_c", "name": "Surface temperature", "family": "thermal", "source": "modis",
     "measures": "Daytime canopy/soil heat — heat-stress risk.", "kind": "thermal"},
    {"key": "sar_moisture", "name": "Radar soil moisture", "family": "water", "source": "sar",
     "measures": "Soil wetness through clouds (Sentinel-1).", "kind": "thermal"},
    {"key": "sm_rootzone", "name": "Root-zone moisture", "family": "water", "source": "smap",
     "measures": "Water available to roots (0-100cm).", "kind": "thermal"},
    {"key": "et", "name": "Crop water use (ET)", "family": "climate", "source": "power",
     "measures": "Evapotranspiration — daily water demand.", "kind": "climate"},
    {"key": "solar_radiation", "name": "Sunlight energy", "family": "climate", "source": "power",
     "measures": "Solar radiation driving photosynthesis.", "kind": "climate"},
    {"key": "vpd", "name": "Air dryness (VPD)", "family": "climate", "source": "openmeteo",
     "measures": "Atmospheric water-stress demand.", "kind": "climate"},
    {"key": "gdd", "name": "Heat accumulation (GDD)", "family": "climate", "source": "openmeteo",
     "measures": "Thermal time driving crop stage.", "kind": "climate"},
    # v3.1 derived agronomy parameters (fused / computed)
    {"key": "esi", "name": "Evaporative stress (ESI)", "family": "water", "source": "computed",
     "measures": "Actual÷reference ET — drought early warning.", "kind": "agronomy"},
    {"key": "cwsi", "name": "Crop water stress (CWSI)", "family": "water", "source": "computed",
     "measures": "Canopy-temperature water stress.", "kind": "agronomy"},
    {"key": "surface_moisture_m3m3", "name": "Surface soil moisture", "family": "water", "source": "openmeteo",
     "measures": "Topsoil (0-1cm) water — germination/crusting.", "kind": "agronomy"},
    {"key": "thermal_anomaly_c", "name": "Field heat anomaly", "family": "thermal", "source": "modis",
     "measures": "Field temperature vs surrounding area.", "kind": "agronomy"},
    {"key": "heat_stress_dd", "name": "Heat-stress degree days", "family": "thermal", "source": "computed",
     "measures": "Accumulated heat above crop damage threshold.", "kind": "agronomy"},
    {"key": "frost_risk", "name": "Frost risk", "family": "thermal", "source": "computed",
     "measures": "Frost likelihood over next 3 days.", "kind": "agronomy"},
    {"key": "relative_humidity", "name": "Humidity (disease pressure)", "family": "climate", "source": "power",
     "measures": "Moist-air fungal-disease pressure.", "kind": "agronomy"},
    {"key": "wind_speed_ms", "name": "Wind speed", "family": "climate", "source": "power",
     "measures": "Spray drift, lodging, ET driver.", "kind": "agronomy"},
    {"key": "soil_temp_c", "name": "Soil temperature", "family": "climate", "source": "openmeteo",
     "measures": "Germination and root activity.", "kind": "agronomy"},
    {"key": "aridity_index", "name": "Aridity (P/PET)", "family": "climate", "source": "computed",
     "measures": "Recent rainfall vs water demand.", "kind": "agronomy"},
    {"key": "photoperiod_hours", "name": "Day length", "family": "phenology", "source": "computed",
     "measures": "Daylight hours — flowering trigger.", "kind": "agronomy"},
    {"key": "chill_hours", "name": "Chill accumulation", "family": "phenology", "source": "computed",
     "measures": "Winter chill for temperate fruit.", "kind": "agronomy"},
]

REGISTRY_BY_KEY = {p["key"]: p for p in PARAMETER_REGISTRY}


def build_index_assessment(indices: dict) -> list[dict]:
    """Turn raw Sentinel-2 index values into farmer-facing assessment rows.

    Only emits rows for indices that have a classifier + template (the high-signal ones),
    so the advisory stays focused rather than dumping 14 numbers at the farmer.
    """
    rows = []
    classifiers = {
        "ndvi": classify_ndvi, "ndre": classify_ndre, "ndmi": classify_ndmi,
        "psri": classify_psri, "lai": classify_lai,
        "dswi": classify_dswi, "ccci": classify_ccci, "bsi": classify_bsi,
    }
    for key, classify in classifiers.items():
        val = indices.get(key)
        if val is None:
            continue
        status = classify(val)
        rows.append({
            "key": key,
            "name": REGISTRY_BY_KEY.get(key, {}).get("name", key),
            "value": val,
            "status": status,
            "farmer_line": farmer_line(key, status),
            "indicative": REGISTRY_BY_KEY.get(key, {}).get("kind") == "biophysical",
        })
    return rows


_AGRONOMY_PARAM_KEYS = (
    "photoperiod_hours", "chill_hours", "heat_stress_dd", "aridity_index", "esi", "cwsi",
    "relative_humidity", "wind_speed_ms", "soil_temp_c", "surface_moisture_m3m3",
    "thermal_anomaly_c", "frost_risk",
)


def count_available_parameters(indices: dict, satellite_extras: dict, agroclimate: dict,
                               agronomy: dict = None) -> int:
    """How many distinct registry parameters actually have a value on this request.
    Used for transparency ('mapped 31 of 44 growth signals') and confidence."""
    n = 0
    for key in INDEX_VALID_RANGE:
        if indices.get(key) is not None:
            n += 1
    extras = satellite_extras or {}
    if extras.get("lst", {}).get("lst_day_celsius") is not None:
        n += 1
    if extras.get("sar", {}).get("moisture_class") not in (None, "unknown"):
        n += 1
    if extras.get("smap", {}).get("rootzone_moisture_m3m3") is not None:
        n += 1
    ac = agroclimate or {}
    for key in ("et_mm_day", "solar_radiation_mj", "vpd_kpa", "rootzone_wetness", "gdd"):
        if ac.get(key) is not None:
            n += 1
    ag = agronomy or {}
    for key in _AGRONOMY_PARAM_KEYS:
        if ag.get(key) is not None:
            n += 1
    return n
