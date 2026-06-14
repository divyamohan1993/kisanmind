"""
KisanMind — multi-sensor fusion / synthesis.

44 parameters are only useful if they combine into a diagnosis. This layer fuses them by
PHYSICALLY INDEPENDENT measurement basis and reports how many independent bases agree, so:
  - agreement across independent sensors (radar + microwave + thermal + flux all say "dry")
    yields HIGH confidence — that is the "better picture when combined";
  - correlated indices (seven red-edge chlorophyll proxies) count as ONE basis, so they cannot
    fake independent agreement (honest confidence, not inflated vote-counting);
  - disagreement is surfaced as a caveat to hedge, not hidden.

The fused findings — not the 44 raw numbers — are what drive the advisory and feed the
verification gate. Pure functions (stdlib); unit-tested.
"""

from __future__ import annotations

from typing import Optional


def _conf(agree: int) -> str:
    return "HIGH" if agree >= 3 else ("MEDIUM" if agree == 2 else "LOW")


def _finding(diagnosis, verdict, agree, total, bases, line, conflict=False) -> dict:
    return {
        "diagnosis": diagnosis,
        "verdict": verdict,
        "independent_bases_agreeing": agree,
        "independent_bases_checked": total,
        "bases": bases,
        "confidence": "MEDIUM" if conflict else _conf(agree),
        "conflict": conflict,
        "farmer_line": line,
    }


# ---------------------------------------------------------------------------
# WATER — the highest-value fusion: 6 physically independent ways to sense water.
# ---------------------------------------------------------------------------
def fuse_water(s: dict) -> Optional[dict]:
    """Each basis votes dry / wet. Bases are independent physics: optical canopy water,
    C-band radar, L-band microwave, land-surface model, canopy thermal, evaporative flux."""
    votes = {}  # basis -> "dry" | "wet"

    # 1. Optical canopy water (Sentinel-2 NDMI)
    if s.get("ndmi_status") in ("water_stress", "mild_stress"):
        votes["optical_canopy"] = "dry"
    elif s.get("ndmi_status") in ("adequate", "well_watered"):
        votes["optical_canopy"] = "wet"

    # 2. C-band radar soil moisture (Sentinel-1 SAR)
    if s.get("sar_moisture") in ("dry", "very_dry"):
        votes["radar"] = "dry"
    elif s.get("sar_moisture") in ("moist", "wet"):
        votes["radar"] = "wet"

    # 3. L-band microwave root-zone (NASA SMAP)
    if s.get("smap_rootzone_class") in ("low", "critical"):
        votes["microwave"] = "dry"
    elif s.get("smap_rootzone_class") in ("adequate", "wet"):
        votes["microwave"] = "wet"

    # 4. Land-surface model root moisture (NASA POWER / GLDAS / Open-Meteo)
    model_root = s.get("power_gwetroot")
    if model_root is not None:
        votes["model"] = "dry" if model_root < 0.3 else "wet"
    else:
        mv = s.get("model_root_m3m3")
        if mv is not None:
            votes["model"] = "dry" if mv < 0.18 else "wet"

    # 5. Canopy thermal water stress (LST-derived CWSI)
    if s.get("cwsi_status") == "high_stress":
        votes["thermal"] = "dry"
    elif s.get("cwsi_status") == "low_stress":
        votes["thermal"] = "wet"

    # 6. Evaporative flux (ESI = actual/reference ET)
    if s.get("esi_status") == "water_stress":
        votes["flux"] = "dry"
    elif s.get("esi_status") == "no_stress":
        votes["flux"] = "wet"

    if len(votes) < 2:
        return None  # not enough independent evidence to fuse

    dry = [b for b, v in votes.items() if v == "dry"]
    wet = [b for b, v in votes.items() if v == "wet"]
    total = len(votes)

    if len(dry) >= 2 and len(dry) >= len(wet) * 2:
        line = (f"{len(dry)} independent sensors (e.g. {', '.join(_pretty(dry))}) agree the crop "
                f"is short of water — a strong, cross-checked signal to irrigate.")
        return _finding("water", "water_stress", len(dry), total, dry, line)
    if len(wet) >= 2 and len(wet) >= len(dry) * 2:
        line = f"{len(wet)} independent sensors agree soil moisture is adequate — no urgent watering."
        return _finding("water", "adequate", len(wet), total, wet, line)
    # Split → genuine disagreement (e.g. wet surface, dry root). Hedge, don't pick a side.
    line = ("Water sensors disagree (some read dry, some wet — likely a surface-vs-deep "
            "difference). Check the soil by hand before irrigating.")
    return _finding("water", "mixed", max(len(dry), len(wet)), total, dry + wet, line, conflict=True)


# ---------------------------------------------------------------------------
# NITROGEN / CHLOROPHYLL — many correlated optical indices = ONE basis; Sentinel-3 independent.
# ---------------------------------------------------------------------------
def fuse_nitrogen(s: dict) -> Optional[dict]:
    bases = {}

    # Basis A: Sentinel-2 red-edge family (correlated) → majority vote = ONE basis.
    re_low = 0
    re_total = 0
    for key in ("ndre_status", "ccci_status"):
        st = s.get(key)
        if st:
            re_total += 1
            if st in ("low", "deficient"):
                re_low += 1
    # Magnitude indices without a status: threshold GNDVI/MTCI lightly.
    for key, thr in (("gndvi", 0.5), ("mtci", 2.0)):
        v = s.get(key)
        if v is not None:
            re_total += 1
            if v < thr:
                re_low += 1
    if re_total:
        bases["s2_rededge"] = "low" if re_low > re_total / 2 else "ok"

    # Basis B: Sentinel-3 OLCI chlorophyll (independent platform).
    if s.get("otci_status"):
        bases["sentinel3"] = "low" if s["otci_status"] in ("low", "deficient") else "ok"

    if not bases:
        return None
    low = [b for b, v in bases.items() if v == "low"]
    total = len(bases)

    # Highest-value cross-check: canopy looks green but nitrogen reads low → HIDDEN deficiency.
    green = s.get("ndvi_status") in ("healthy", "very_healthy")
    if low and green:
        line = ("The canopy looks green, but chlorophyll/nitrogen signals read low — a hidden "
                "deficiency NDVI alone would miss. Confirm leaf colour with your KVK before feeding.")
        return _finding("nitrogen", "hidden_deficiency", len(low), total, low, line)
    if low:
        line = "Chlorophyll/nitrogen signals read low across sensors — check leaf nourishment."
        return _finding("nitrogen", "low", len(low), total, low, line)
    return _finding("nitrogen", "adequate", total - len(low), total, list(bases),
                    "Nitrogen and chlorophyll look adequate across sensors.")


# ---------------------------------------------------------------------------
# DISEASE / BIOTIC — declining vigour WITH adequate water + favourable humidity = not thirst.
# ---------------------------------------------------------------------------
def fuse_disease(s: dict, water_verdict: Optional[str]) -> Optional[dict]:
    signals = []
    if s.get("dswi_status") == "stress":
        signals.append("disease-stress index elevated")
    if s.get("trajectory_direction") == "declining":
        signals.append("crop vigour declining")
    if s.get("humidity") is not None and s["humidity"] >= 80:
        signals.append("humidity favours fungal disease")
    if s.get("ari_status") == "stress":
        signals.append("stress pigments rising")

    # The decisive logic: vigour dropping but water is NOT the problem → look for disease.
    water_ok = water_verdict in ("adequate", "mixed", None)
    if len(signals) >= 2 and water_ok:
        line = ("Crop vigour is dropping while water looks adequate — this points to pest, "
                "disease or a nutrient issue rather than thirst. A KVK field check is the safe step.")
        return _finding("biotic_stress", "possible_disease", len(signals), len(signals),
                        signals, line)
    return None


# ---------------------------------------------------------------------------
# HEAT — thermal + anomaly + accumulated load + atmospheric demand.
# ---------------------------------------------------------------------------
def fuse_heat(s: dict) -> Optional[dict]:
    hot = []
    if s.get("lst_heat_stress") in ("high", "extreme"):
        hot.append("surface temperature")
    if s.get("thermal_anomaly") is not None and s["thermal_anomaly"] >= 2.5:
        hot.append("field hotter than surroundings")
    if s.get("vpd") is not None and s["vpd"] >= 2.0:
        hot.append("dry air")
    if s.get("heat_dd") is not None and s["heat_dd"] >= 30:
        hot.append("accumulated heat load")
    if len(hot) >= 2:
        line = (f"{len(hot)} signals point to heat stress — irrigate in the early morning and, "
                f"for sensitive crops, consider shade.")
        return _finding("heat", "heat_stress", len(hot), len(hot), hot, line)
    return None


# ---------------------------------------------------------------------------
# HARVEST READINESS — phenology stage + senescence + trajectory converge.
# ---------------------------------------------------------------------------
def fuse_harvest(s: dict) -> Optional[dict]:
    near = []
    if s.get("gdd_stage") in ("ripening", "maturation", "grain_filling", "harvest_ready",
                              "fruit_development"):
        near.append("growth stage near maturity")
    if s.get("psri_status") in ("senescing", "early_senescence"):
        near.append("leaves ageing")
    if s.get("trajectory_direction") == "declining":
        near.append("greenness past its peak")
    if len(near) >= 2:
        line = "Multiple signals agree the crop is approaching harvest — plan labour and market now."
        return _finding("harvest", "approaching", len(near), len(near), near, line)
    return None


def _pretty(bases: list) -> list:
    names = {"optical_canopy": "leaf-water", "radar": "radar", "microwave": "microwave satellite",
             "model": "soil model", "thermal": "canopy heat", "flux": "evapotranspiration",
             "s2_rededge": "red-edge", "sentinel3": "Sentinel-3"}
    return [names.get(b, b) for b in bases]


def synthesize(signals: dict, optical_age_days: Optional[int] = None) -> dict:
    """Run all fusions. Returns {findings: [...], picture: 'one-line combined summary'}.
    Each finding fuses independent sensors into one diagnosis with agreement-based confidence.

    optical_age_days lets stale optical imagery temper optical-derived diagnoses: a green-vs-
    nitrogen or harvest call built on a 10-day-old image should not claim HIGH confidence. Water
    is largely spared — it leans on radar/microwave/model/thermal/flux, mostly near-live."""
    findings = []
    water = fuse_water(signals)
    if water:
        findings.append(water)
    nitro = fuse_nitrogen(signals)
    if nitro:
        findings.append(nitro)
    disease = fuse_disease(signals, water["verdict"] if water else None)
    if disease:
        findings.append(disease)
    heat = fuse_heat(signals)
    if heat:
        findings.append(heat)
    harvest = fuse_harvest(signals)
    if harvest:
        findings.append(harvest)

    # Age-aware tempering: optical-derived diagnoses drop one confidence level on a stale image.
    if optical_age_days is not None and optical_age_days > 7:
        _down = {"HIGH": "MEDIUM", "MEDIUM": "LOW"}
        for f in findings:
            if f["diagnosis"] in ("nitrogen", "harvest") and f["confidence"] in _down:
                f["confidence"] = _down[f["confidence"]]
                f["age_caveat"] = f"from a {optical_age_days}-day-old satellite image"

    # One-line combined picture: lead with the highest-confidence actionable finding.
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    actionable = sorted([f for f in findings if f["verdict"] not in ("adequate",)],
                        key=lambda f: order.get(f["confidence"], 3))
    picture = actionable[0]["farmer_line"] if actionable else (
        findings[0]["farmer_line"] if findings else "")
    return {"findings": findings, "picture": picture,
            "fused_count": len(findings)}
