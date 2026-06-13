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

from backend import indices, prediction, logistics, verification  # noqa: E402
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


def main():
    test_indices()
    test_prediction()
    test_logistics()
    test_verification()
    try:
        asyncio.run(test_agroclimate_live())
    except Exception as e:
        check("agroclimate live call (network)", False, f"network error: {e}")

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
