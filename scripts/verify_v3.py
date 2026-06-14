#!/usr/bin/env python3
"""
v3 verification harness — runs the new pure modules + live no-key APIs against REAL data.
No fastapi / earthengine / google-cloud / API keys required.

    python scripts/verify_v3.py

Exits non-zero if any assertion fails.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import indices, prediction, logistics, verification, fusion  # noqa: E402
from backend.agroclimate import fetch_agroclimate  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(f"  [{PASS if cond else FAIL}] {name}{(' — ' + extra) if extra else ''}")


def test_indices():
    print("\n== indices: EVI scaling bug fix + 14 params ==")
    # Realistic healthy-vegetation Sentinel-2 SR DN (0-10000 scale).
    dn = {"B2": 400, "B3": 700, "B4": 600, "B5": 1400, "B6": 2600,
          "B7": 3000, "B8": 3400, "B8A": 3500, "B11": 2000, "B12": 1200}
    idx = indices.compute_s2_indices(dn, already_reflectance=False)
    print("  values:", {k: v for k, v in idx.items()})
    check("EVI within [-1,1] (old cache had 2.046)", idx["evi"] is not None and -1 <= idx["evi"] <= 1,
          f"evi={idx['evi']}")
    check("NDVI healthy (>0.6) for vegetation", idx["ndvi"] and idx["ndvi"] > 0.6, f"ndvi={idx['ndvi']}")
    check("NDRE present & in range", idx["ndre"] is not None and -1 <= idx["ndre"] <= 1)
    check("NDMI present & in range", idx["ndmi"] is not None)
    check("LAI present & 0-8", idx["lai"] is not None and 0 <= idx["lai"] <= 8, f"lai={idx['lai']}")
    check("FAPAR present & 0-0.95", idx["fapar"] is not None and 0 <= idx["fapar"] <= 0.95, f"fapar={idx['fapar']}")
    n_params = sum(1 for v in idx.values() if v is not None)
    check(">=12 S2 parameters computed", n_params >= 12, f"{n_params} params")

    # Scale-invariance sanity: NDVI identical whether DN or reflectance.
    refl = {k: v * 1e-4 for k, v in dn.items()}
    idx_r = indices.compute_s2_indices(refl, already_reflectance=True)
    check("NDVI scale-invariant", abs(idx["ndvi"] - idx_r["ndvi"]) < 1e-6)
    check("EVI scale-corrected matches reflectance path", abs(idx["evi"] - idx_r["evi"]) < 1e-6)

    rows = indices.build_index_assessment(idx)
    check("assessment emits farmer lines", rows and all(r["farmer_line"] for r in rows),
          f"{len(rows)} rows")


def test_prediction():
    print("\n== prediction: soil-water balance + honest trajectory ==")
    # Soil-water balance with realistic dry-ish root zone + hot ET forecast, no rain.
    irr = prediction.predict_irrigation_need(
        crop="tomato", rootzone_moisture_m3m3=0.17,
        et_forecast_mm=[5.2, 5.3, 4.9, 5.0, 5.1], rain_forecast_mm=[0, 0, 0, 0, 0])
    print("  irrigation:", irr)
    check("irrigation forecast returned", bool(irr))
    check("days_until_irrigation is int>=0 or now", irr.get("status") in
          ("irrigate_now", "irrigate_in_days", "sufficient"))
    check("etc uses crop coefficient (>et0)", irr.get("etc_mm_day", 0) >= 5.2)

    wet = prediction.predict_irrigation_need(
        crop="tomato", rootzone_moisture_m3m3=0.27,
        et_forecast_mm=[3, 3, 3], rain_forecast_mm=[20, 0, 0])
    check("wet soil + rain => not irrigate_now", wet.get("status") != "irrigate_now", wet.get("status"))

    # Trajectory honesty.
    one = prediction.predict_vegetation_trajectory([{"date": "2026-06-01", "ndvi": 0.5}])
    check("single point => NO extrapolation", one.get("method") == "insufficient_observations")
    multi = prediction.predict_vegetation_trajectory([
        {"date": "2026-05-20", "ndvi": 0.40}, {"date": "2026-05-30", "ndvi": 0.50},
        {"date": "2026-06-09", "ndvi": 0.60}])
    check("3 rising points => improving + forecast", multi.get("direction") == "improving"
          and multi.get("ndvi_in_7_days") is not None, str(multi.get("ndvi_in_7_days")))

    price = prediction.predict_price(
        {"daily_prices": [2000, 2100, 2050, 2200, 2300, 2250, 2400, 2350, 2500, 2450],
         "price_range_90d": {"avg": 2200}, "volatility_30d": 0.08}, current_modal=2500)
    check("price prediction band + lean", price.get("lean") in ("sell_soon", "hold")
          and price.get("low") is not None, f"lean={price.get('lean')}")


def test_logistics():
    print("\n== logistics: diesel-distance fare ==")
    fare = logistics.estimate_transport_fare(distance_km=120, quantity_quintals=15, crop="tomato")
    print("  fare:", fare)
    check("fare breakdown returned", bool(fare) and fare.get("per_quintal", 0) > 0)
    check("vehicle chosen by load", fare["vehicle"] == "tractor-trolley", fare["vehicle"])
    check("per-quintal in sane range (Rs 1-15/km/q equiv)",
          0 < fare["per_quintal"] / 120 < 15, f"{fare['per_quintal']}/q over 120km")
    rate = logistics.transport_rate_per_km_per_quintal(quantity_quintals=15)
    check("rate/km/q sane vs old flat 3.5", 0.5 < rate < 8, f"rate={rate}")
    check("no distance => empty", logistics.estimate_transport_fare(None, 10) == {})


def test_verification():
    print("\n== verification: deterministic grounding + safety ==")
    payload = {
        "best_mandi": {"market": "APMC Bhuntar", "modal_price": 7500, "net_profit_per_quintal": 6175},
        "local_mandi": {"market": "Solan", "modal_price": 6000, "net_profit_per_quintal": 5800},
        "mandis": [{"modal_price": 7500, "net_profit_per_quintal": 6175}],
    }
    clean = "Sell at APMC Bhuntar for Rs 7500 per quintal, net Rs 6175 after transport."
    halluc = "Sell at APMC Bhuntar for Rs 9999 per quintal — best price around."
    c_clean = verification.run_deterministic_checks(clean, payload)
    c_hall = verification.run_deterministic_checks(halluc, payload)
    pg_clean = next(f for f in c_clean if f["check"] == "price_grounding")
    pg_hall = next(f for f in c_hall if f["check"] == "price_grounding")
    check("grounded prices PASS", pg_clean["passed"])
    check("hallucinated Rs 9999 FAILS grounding", not pg_hall["passed"], pg_hall["detail"])
    loan = verification.run_deterministic_checks("Take a loan at 10% interest rate to buy seed.", payload)
    fin = next(f for f in loan if f["check"] == "no_financial_advice")
    check("loan advice FAILS safety", not fin["passed"])
    verdict = verification.summarize_verdict(c_hall)
    check("hallucination => FAIL verdict + regenerate", verdict["verdict"] == "FAIL"
          and verdict["should_regenerate"])


async def test_agroclimate_live():
    print("\n== agroclimate: LIVE no-key (NASA POWER + Open-Meteo), Solan 30.9,77.1 ==")
    ac = await fetch_agroclimate(30.9, 77.1)
    print("  keys:", sorted(ac.keys()))
    print("  et_mm_day:", ac.get("et_mm_day"), "et0:", ac.get("et0_mm_day"),
          "rootzone_wetness:", ac.get("rootzone_wetness"),
          "soil_root_m3m3:", ac.get("soil_moisture_root_m3m3"),
          "vpd:", ac.get("vpd_kpa"), "solar:", ac.get("solar_radiation_mj"))
    check("agroclimate available (live)", ac.get("available") is True)
    has_et = ac.get("et_mm_day") is not None or ac.get("et0_mm_day") is not None
    check("ET available (POWER or Open-Meteo)", has_et)
    check("root-zone moisture available", ac.get("soil_moisture_root_m3m3") is not None
          or ac.get("rootzone_wetness") is not None)
    check("forecast block for prediction", "forecast" in ac
          and isinstance(ac["forecast"].get("et0_forecast_mm"), list))
    check(">=2 independent sources", len(ac.get("sources", [])) >= 2, str(ac.get("sources")))

    # End-to-end: live agroclimate -> soil-water prediction.
    root = ac.get("soil_moisture_root_m3m3")
    if root is not None:
        irr = prediction.predict_irrigation_need(
            "tomato", root, ac["forecast"].get("et0_forecast_mm"),
            ac["forecast"].get("rain_forecast_mm"), et_today_mm=ac.get("et0_mm_day"))
        print("  live irrigation forecast:", irr)
        check("live data feeds irrigation forecast", bool(irr))


async def test_integration_sim():
    """Replicate main.py's _run_advisory enrichment + verification data-flow (no fastapi),
    for both the live-EE path (raw bands) and the cache path (stored extra_indices)."""
    print("\n== integration sim: enrichment + verification data-flow (15+ params) ==")
    ac = await fetch_agroclimate(30.9, 77.1)
    extras = {"sar": {"moisture_class": "dry"},
              "lst": {"lst_day_celsius": 34.0},
              "smap": {"rootzone_moisture_m3m3": 0.18, "rootzone_class": "low"}}

    # --- live-EE path: ndvi_data carries reflectance bands ---
    bands = {"B2": 0.04, "B3": 0.07, "B4": 0.06, "B5": 0.14, "B6": 0.26,
             "B7": 0.30, "B8": 0.34, "B8A": 0.35, "B11": 0.20, "B12": 0.12}
    ndvi_data_live = {"ndvi": 0.70, "evi": 0.5, "ndwi": -0.65, "bands": bands}
    imap = {}
    _evi = ndvi_data_live.get("evi")
    imap["ndvi"] = ndvi_data_live["ndvi"]
    imap["evi"] = _evi if (isinstance(_evi, (int, float)) and -1 <= _evi <= 1) else None
    imap["ndwi_water"] = ndvi_data_live["ndwi"]
    imap.update(ndvi_data_live.get("extra_indices") or {})
    if ndvi_data_live.get("bands"):
        imap.update({k: v for k, v in indices.compute_s2_indices(bands, already_reflectance=True).items()
                     if v is not None})
    imap = {k: v for k, v in imap.items() if v is not None}
    assessment = indices.build_index_assessment(imap)
    n_params = indices.count_available_parameters(imap, extras, ac)
    print(f"  live-EE path: {len(imap)} optical indices, {len(assessment)} farmer rows, {n_params} total params")
    check("live-EE path maps >=15 total growth parameters", n_params >= 15, f"{n_params} params")
    check("assessment has farmer lines", assessment and all(r["farmer_line"] for r in assessment))

    # --- cache path: ndvi_data with the FULL stored extra_indices a precompute rerun writes ---
    ndvi_data_cache = {"ndvi": 0.62, "evi": None, "ndwi": -0.57,
                       "extra_indices": {"ndre": 0.30, "savi": 0.45, "msavi": 0.44, "gndvi": 0.55,
                                         "ci_rededge": 1.1, "psri": 0.05, "ndmi": 0.22, "nmdi": 0.5,
                                         "nbr": 0.4, "lai": 1.5, "fapar": 0.6}}
    imap2 = {"ndvi": ndvi_data_cache["ndvi"], "evi": ndvi_data_cache["evi"],
             "ndwi_water": ndvi_data_cache["ndwi"]}
    imap2.update(ndvi_data_cache.get("extra_indices") or {})
    imap2 = {k: v for k, v in imap2.items() if v is not None}
    n2 = indices.count_available_parameters(imap2, extras, ac)
    check("cache path (future precompute) maps >=15 params", n2 >= 15, f"{n2} params")

    # --- predictions from live data ---
    root = extras["smap"]["rootzone_moisture_m3m3"]
    fc = ac.get("forecast", {})
    preds = {
        "irrigation": prediction.predict_irrigation_need("tomato", root, fc.get("et0_forecast_mm"),
                                                          fc.get("rain_forecast_mm"),
                                                          et_today_mm=ac.get("et0_mm_day")),
        "trajectory": prediction.predict_vegetation_trajectory(None),  # cache => single obs => no extrapolation
    }
    check("irrigation prediction present", bool(preds["irrigation"]))
    check("trajectory refuses single-obs extrapolation",
          preds["trajectory"].get("method") == "insufficient_observations")

    # --- verification payload + gate (deterministic, no LLM) ---
    best = {"market": "APMC Bhuntar", "modal_price": 7500, "net_profit_per_quintal": 6175, "distance_km": 120}
    payload = {
        "best_mandi": best, "local_mandi": {"market": "Solan", "modal_price": 6000}, "mandis": [best],
        "indices": imap, "satellite_extras": extras, "agroclimate": ac,
        "irrigation_forecast": preds["irrigation"],
        "ndvi_status": indices.classify_ndvi(imap.get("ndvi")),
        "ndmi_status": indices.classify_ndmi(imap.get("ndmi")),
        "ndre_status": indices.classify_ndre(imap.get("ndre")),
    }
    good = "Crop is healthy. Sell at APMC Bhuntar for Rs 7500, net Rs 6175. Water the crop now."
    gate = await verification.verify_advisory(good, payload, gemini_call=None, regenerate=None)
    print(f"  verification verdict: {gate['verdict']}, checks: {len(gate['checks'])}")
    check("verification runs end-to-end", gate.get("verdict") in ("PASS", "REVIEW", "FAIL"))
    # Real fare attaches to best mandi.
    fare = logistics.estimate_transport_fare(best["distance_km"], 15, "tomato")
    check("fare attaches to recommended mandi", bool(fare) and fare["per_quintal"] > 0)


async def test_new_clusters():
    """Sentinel-3 + NASA Earthdata providers: graceful no-cred paths + parser correctness."""
    print("\n== new satellite clusters: Sentinel-3 (CDSE) + NASA Earthdata (GLDAS) ==")
    from backend import copernicus, earthdata
    s3 = await copernicus.fetch_sentinel3_indices(30.9, 77.1)
    check("Sentinel-3 graceful without CDSE creds", s3.get("available") is False
          and s3.get("reason") == "no_cdse_credentials")
    ed = await earthdata.fetch_earthdata(30.9, 77.1)
    check("Earthdata graceful without token", ed.get("available") is False
          and ed.get("reason") == "no_earthdata_token")
    # Data Rods asc2 parser: chronological rows, skip fill (-9999), take newest valid.
    sample = ("Date&Time\tRootMoist_inst\n2026-06-10T00:00\t412.5\n"
              "2026-06-10T03:00\t-9999.0\n2026-06-10T06:00\t408.7")
    check("Earthdata parser skips fill, takes newest", earthdata._latest_value(sample) == 408.7)
    check("OTCI registered + classified", indices.classify_otci(2.5) == "adequate"
          and any(p["key"] == "otci" for p in indices.PARAMETER_REGISTRY))


def test_expansion():
    """v3.1 expansion to 44 parameters: 10 new S2 indices + 12 derived agronomy params."""
    print("\n== expansion: 44 parameters (new S2 indices + agronomy fusion) ==")
    from backend import agronomy
    dn = {"B2": 400, "B3": 700, "B4": 600, "B5": 1400, "B6": 2600,
          "B7": 3000, "B8": 3400, "B8A": 3500, "B11": 2000, "B12": 1200}
    idx = indices.compute_s2_indices(dn)
    new_s2 = ["ccci", "mtci", "s2rep", "ari", "dswi", "arvi", "vari", "wdrvi", "bsi", "ndti"]
    check("10 new S2 indices all computed", all(idx.get(k) is not None for k in new_s2),
          str([k for k in new_s2 if idx.get(k) is None]))
    check("S2REP in red-edge nm range", 680 <= idx["s2rep"] <= 760, f"{idx['s2rep']}")
    check("DSWI classified (disease/water)", indices.classify_dswi(idx["dswi"]) in
          ("healthy", "watch", "stress"))
    check("registry now 44 parameters", len(indices.PARAMETER_REGISTRY) == 44,
          f"{len(indices.PARAMETER_REGISTRY)}")

    pp = agronomy.photoperiod_hours(30.9, 172)
    check("photoperiod plausible (midsummer 30.9N ~14h)", pp and 13 < pp < 15, f"{pp}")
    check("ESI water-stress classification", agronomy.classify_esi(agronomy.esi(2, 5)) == "water_stress")
    check("CWSI bounded 0-1", 0 <= agronomy.cwsi(40, 30, 2) <= 1)
    check("chill hours accumulate from cold days",
          agronomy.chill_hours([{"min_temp_c": 2, "max_temp_c": 10}] * 30) > 0)
    check("frost risk fires below threshold",
          agronomy.frost_risk([{"min_temp_c": 2}], "tomato").get("level") == "high")
    check("heat-stress degree days accumulate",
          agronomy.heat_stress_degree_days([{"max_temp_c": 40, "min_temp_c": 25}] * 5, "wheat") > 0)

    ag = agronomy.compute_agronomy(
        30.9, 172, "apple", lst_day_c=40, air_temp_c=30, vpd_kpa=2, et_actual_mm=2, et0_mm=5,
        precip_recent_mm=5, relative_humidity=85, wind_speed_ms=9, soil_temp_c=24,
        surface_moisture_m3m3=0.15, thermal_anomaly_c=3,
        historical_weather=[{"min_temp_c": 2, "max_temp_c": 10}] * 30,
        forecast_daily=[{"min_temp_c": 2}])
    check("agronomy emits farmer alerts", len(ag.get("interpretation", {})) >= 3,
          f"{len(ag.get('interpretation', {}))} alerts")
    n = indices.count_available_parameters(
        idx, {"lst": {"lst_day_celsius": 40}, "sar": {"moisture_class": "dry"},
              "smap": {"rootzone_moisture_m3m3": 0.2}},
        {"et_mm_day": 2, "solar_radiation_mj": 25, "vpd_kpa": 2, "rootzone_wetness": 0.3, "gdd": 1}, ag)
    check("full request maps 44 parameters", n == 44, f"{n}")


def test_fusion():
    """Multi-sensor fusion: independence-weighted agreement, conflict, hidden deficiency,
    disease, and verification's use of the combined diagnosis."""
    print("\n== fusion: combine 44 params into cross-checked diagnoses ==")
    # 6 physically independent water sensors agree dry → HIGH.
    s = {"ndmi_status": "water_stress", "sar_moisture": "dry", "smap_rootzone_class": "low",
         "power_gwetroot": 0.2, "cwsi_status": "high_stress", "esi_status": "water_stress"}
    w = fusion.fuse_water(s)
    check("6 independent sensors agree -> HIGH water stress",
          w["verdict"] == "water_stress" and w["confidence"] == "HIGH"
          and w["independent_bases_agreeing"] == 6, str(w["independent_bases_agreeing"]))
    # Correlated red-edge indices must NOT inflate independence → one basis; Sentinel-3 = 2nd.
    sn = {"ndvi_status": "healthy", "ndre_status": "deficient", "ccci_status": "low",
          "gndvi": 0.3, "mtci": 1.0, "otci_status": "low"}
    n = fusion.fuse_nitrogen(sn)
    check("hidden N deficiency (green canopy, low N)", n["verdict"] == "hidden_deficiency")
    check("correlated S2 indices count as ONE basis (+S3 = 2)",
          n["independent_bases_checked"] == 2, str(n["independent_bases_checked"]))
    # Plant-vs-soil even split -> flagged conflict, not a false verdict.
    sc = {"ndmi_status": "water_stress", "cwsi_status": "high_stress",
          "sar_moisture": "wet", "smap_rootzone_class": "adequate"}
    check("plant-vs-soil split -> flagged conflict", fusion.fuse_water(sc)["conflict"])
    # Disease: vigour down while water is fine → not thirst.
    sd = {"dswi_status": "stress", "trajectory_direction": "declining", "humidity": 85}
    check("disease fused (vigour down + water ok)",
          fusion.fuse_disease(sd, "adequate")["verdict"] == "possible_disease")
    syn = fusion.synthesize({**s, **sn})
    check("synthesize returns combined picture", bool(syn["picture"]) and syn["fused_count"] >= 2,
          f"{syn['fused_count']} findings")
    # Verification leverages fusion: HIGH water stress but advisory silent on water → flag.
    payload = {"best_mandi": {"market": "X", "modal_price": 1000}, "mandis": [],
               "fusion": {"findings": [{"diagnosis": "water", "verdict": "water_stress",
                                        "confidence": "HIGH"}]}}
    fchecks = verification.run_deterministic_checks("Sell at X for Rs 1000. Crop looks fine.", payload)
    fw = next((c for c in fchecks if c["check"] == "fused_water_addressed"), None)
    check("verification flags ignored fused water stress", fw is not None and not fw["passed"])


def main():
    test_indices()
    test_prediction()
    test_logistics()
    test_verification()
    test_expansion()
    test_fusion()
    try:
        asyncio.run(test_agroclimate_live())
    except Exception as e:
        check("agroclimate live call (network)", False, f"network error: {e}")
    try:
        asyncio.run(test_integration_sim())
    except Exception as e:
        check("integration sim", False, f"error: {e}")
    try:
        asyncio.run(test_new_clusters())
    except Exception as e:
        check("new clusters", False, f"error: {e}")

    print("\n" + "=" * 50)
    n_pass = sum(1 for _, ok in results if ok)
    n_total = len(results)
    print(f"RESULT: {n_pass}/{n_total} checks passed")
    failed = [n for n, ok in results if not ok]
    if failed:
        print("FAILED:", failed)
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    main()
