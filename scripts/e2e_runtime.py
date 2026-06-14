#!/usr/bin/env python3
"""
End-to-end RUNTIME proof: import the ACTUAL backend/main.py and run the real `_run_advisory`
+ `generate_advisory_with_gemini` code path. Only the external libraries (fastapi/ee/google)
and the network helpers (Maps/AgMarkNet/Gemini/EE) are stubbed; the v3 enrichment runs for
real, and the agro-climate layer is fetched LIVE (no key). This exercises the genuine wiring
that py_compile and the pure-module harness cannot.

    python scripts/e2e_runtime.py
"""
import asyncio
import os
import sys
import types as _t
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# --- permissive dummy for attribute/call chains (ee.X, tts.SsmlVoiceGender.MALE, ...) ---
class _Dummy:
    def __getattr__(self, n): return _Dummy()
    def __call__(self, *a, **k): return _Dummy()


def _mod(name, **attrs):
    m = _t.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    m.__getattr__ = lambda n: _Dummy()  # PEP 562: missing attrs -> dummy
    sys.modules[name] = m
    return m


class _FastAPI:
    def __init__(self, *a, **k): pass
    def add_middleware(self, *a, **k): pass
    def _dec(self, *a, **k): return lambda f: f
    get = post = put = delete = websocket = _dec
    def middleware(self, *a, **k): return lambda f: f


class _HTTPException(Exception):
    def __init__(self, status_code=500, detail="", *a, **k):
        self.status_code, self.detail = status_code, detail
        super().__init__(f"{status_code}: {detail}")


class _WSDisconnect(Exception):
    pass


def install_stubs():
    _mod("ee", Initialize=lambda *a, **k: None)
    _mod("fastapi", FastAPI=_FastAPI, HTTPException=_HTTPException, Request=_Dummy,
         Form=lambda *a, **k: _Dummy(), WebSocket=_Dummy, WebSocketDisconnect=_WSDisconnect)
    _mod("fastapi.middleware", )
    _mod("fastapi.middleware.cors", CORSMiddleware=_Dummy)
    _mod("fastapi.responses", Response=_Dummy)
    _mod("starlette", )
    _mod("starlette.websockets", WebSocketState=_Dummy())
    # google namespace + submodules
    genai = _mod("google.genai", Client=lambda *a, **k: _Dummy())
    gtypes = _mod("google.genai.types")
    gcloud = _mod("google.cloud",
                  texttospeech_v1=_Dummy(), speech_v2=_Dummy(),
                  translate_v2=_Dummy(), storage=_Dummy())
    _mod("google.cloud.texttospeech_v1")
    _mod("google.cloud.speech_v2")
    _mod("google.cloud.translate_v2", Client=lambda *a, **k: _Dummy())
    _mod("google.cloud.storage", Client=lambda *a, **k: _Dummy())
    _mod("google", genai=genai, cloud=gcloud)
    sys.modules["google"].genai = genai
    sys.modules["google"].cloud = gcloud

    os.environ.setdefault("GOOGLE_MAPS_API_KEY", "stub")
    os.environ.setdefault("AGMARKNET_API_KEY", "stub")
    os.environ.setdefault("GEMINI_API_KEY", "stub")


# --- canned, real-shaped data for the network helpers we stub ---
class _GResp:
    def __init__(self, text): self.text = text


async def _geocode(lat, lon):
    return {"location_name": "Solan", "district": "Solan", "state": "Himachal Pradesh",
            "formatted_address": "Solan, HP", "maps_url": "https://maps.google.com"}


async def _mandis(crop, state):
    base = [
        {"market": "APMC Bhuntar", "district": "Kullu", "state": "Himachal Pradesh",
         "commodity": crop, "variety": "Local", "min_price": 6000, "max_price": 8000,
         "modal_price": 7500, "arrival_date": "13/06/2026"},
        {"market": "Solan", "district": "Solan", "state": "Himachal Pradesh",
         "commodity": crop, "variety": "Local", "min_price": 5000, "max_price": 6500,
         "modal_price": 6000, "arrival_date": "13/06/2026"},
        {"market": "Shimla", "district": "Shimla", "state": "Himachal Pradesh",
         "commodity": crop, "variety": "Local", "min_price": 5500, "max_price": 7000,
         "modal_price": 6500, "arrival_date": "12/06/2026"},
    ]
    return base


async def _distances(lat, lon, mandis):
    dist = {"APMC Bhuntar": 110, "Solan": 8, "Shimla": 45}
    for m in mandis:
        d = dist.get(m["market"], 30)
        m["distance_km"] = d
        m["distance_text"] = f"{d} km"
        m["duration_minutes"] = d * 2
        m["duration_text"] = f"{d*2} min"
    return mandis


async def _kvk(lat, lon):
    return {"name": "KVK Solan", "address": "Solan, HP", "phone": "1800-180-1551",
            "distance_km": 6.0, "helpline": "1800-180-1551"}


async def _weather(lat, lon):
    daily = [{"date": "14 June", "max_temp_c": 31, "min_temp_c": 19, "precipitation_mm": 0},
             {"date": "15 June", "max_temp_c": 33, "min_temp_c": 20, "precipitation_mm": 0},
             {"date": "16 June", "max_temp_c": 30, "min_temp_c": 18, "precipitation_mm": 4}]
    return {"daily_forecast": daily,
            "summary": "14 June: 19-31C, No rain\n15 June: 20-33C, No rain\n16 June: 18-30C, Rain 4mm",
            "source": "Open-Meteo"}


async def _hist(lat, lon, days_back=90):
    return [{"date": f"2026-04-{d:02d}", "max_temp_c": 28, "min_temp_c": 14,
             "precipitation_mm": 0} for d in range(1, 29)]


async def _price_history(crop):
    return {"daily_prices": [7000, 7100, 7200, 7300, 7400, 7500, 7450, 7500],
            "price_range_90d": {"min": 6000, "max": 8000, "avg": 7000},
            "volatility_30d": 0.06}


async def _none(*a, **k):
    return None


async def _empty(*a, **k):
    return {}


def patch(m):
    m.EE_INITIALIZED = False
    m.reverse_geocode = _geocode
    m.fetch_mandi_prices = _mandis
    m.get_distances = _distances
    m.find_nearest_kvk = _kvk
    m.fetch_weather = _weather
    m.fetch_historical_weather = _hist
    m.fetch_price_history = _price_history
    m.fetch_ndvi = _none
    m.fetch_ndvi_trajectory = _empty
    m.fetch_satellite_extras = _empty
    m._gcs_get = _none
    async def _gcs_set(k, v): return None
    m._gcs_set = _gcs_set
    m._gemini_generate = lambda contents, config=None: _GResp(
        "Your tomato crop looks healthy. The best rate is at APMC Bhuntar, Rs 7500 per quintal, "
        "about 110 km away. Water the crop soon based on the soil. If you see pests or disease, "
        "call your KVK at 1800-180-1551. Yeh aaj ki data ke hisaab se hai. Final faisla aapka hai.")


def main():
    install_stubs()
    from backend import main as m  # the REAL backend
    patch(m)

    req = m.AdvisoryRequest(latitude=30.9, longitude=77.1, crop="tomato", language="en",
                            quantity_quintals=20, sowing_date="2026-04-01", accuracy_m=12)
    print("Running REAL _run_advisory (live agro-climate, stubbed Maps/AgMarkNet/Gemini)...")
    result = asyncio.run(m._run_advisory(req))

    ok = []

    def chk(name, cond, extra=""):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {extra}" if extra else ""))

    adv = result.get("advisory", "")
    chk("advisory text produced", len(adv) > 50, f"{len(adv)} chars")
    chk("best_mandi chosen", result.get("best_mandi", {}).get("market"), result.get("best_mandi", {}).get("market"))
    chk("best_mandi has real fare breakdown", result.get("best_mandi", {}).get("fare_breakdown", {}).get("per_quintal"),
        f"Rs{result.get('best_mandi', {}).get('fare_breakdown', {}).get('per_quintal')}/q")
    pm = result.get("parameters_mapped", 0)
    chk("parameters_mapped > 0 (live, no precompute)", pm > 0, f"{pm} params")
    chk("indices present", len(result.get("indices", {})) > 0, f"{len(result.get('indices', {}))} indices")
    ag = result.get("agroclimate", {})
    chk("agro-climate fetched LIVE", ag.get("available") is True, str(ag.get("sources")))
    chk("agro-climate carries data date (power_as_of)", ag.get("power_as_of"), ag.get("power_as_of"))
    agr = result.get("agronomy", {})
    chk("agronomy computed", len([k for k in agr if k not in ("interpretation", "indicative")]) >= 3,
        f"{[k for k in agr if k not in ('interpretation','indicative')]}")
    fu = result.get("fusion", {})
    chk("fusion produced combined diagnosis", fu.get("fused_count", 0) >= 1,
        f"{fu.get('fused_count')} findings; picture: {fu.get('picture', '')[:70]}")
    preds = result.get("predictions", {})
    chk("irrigation prediction present", preds.get("irrigation", {}).get("status"),
        preds.get("irrigation", {}).get("status"))
    lq = result.get("location_quality", {})
    # Effective uncertainty = worse of GPS accuracy (12m) and the satellite-grid offset.
    # For a real Solan cache hit the nearest grid point is ~3km away, so the HONEST result is
    # "approximate" — the system refuses field-level precision when the satellite data is 3km off.
    chk("location confidence combines GPS + satellite-grid offset",
        lq.get("gps_accuracy_m") == 12 and lq.get("effective_uncertainty_m", 0) >= 12
        and lq.get("level") in ("high", "good", "approximate", "area"),
        f"level={lq.get('level')} eff={lq.get('effective_uncertainty_m')}m "
        f"(GPS {lq.get('gps_accuracy_m')}m vs grid {lq.get('satellite_offset_m')}m)")
    fr = result.get("freshness", {})
    chk("freshness block present", "layers" in fr, str(list(fr.get("layers", {}).keys())))
    conf = result.get("confidence", {})
    chk("verification verdict recorded", conf.get("verification", {}).get("verdict"),
        conf.get("verification", {}).get("verdict"))
    chk("location folded into confidence", conf.get("location", {}).get("level"), conf.get("location", {}).get("level"))

    print("\n  --- assembled advisory (real pipeline output) ---")
    print("  " + adv[:300].replace("\n", " "))
    print(f"\n  fusion picture: {fu.get('picture', '(none)')}")
    print(f"  params mapped: {pm} | agro sources: {len(ag.get('sources', []))} | "
          f"fused: {fu.get('fused_count')} | location: {lq.get('level')} | "
          f"verify: {conf.get('verification', {}).get('verdict')}")

    print("\n" + "=" * 56)
    print(f"E2E RUNTIME: {sum(ok)}/{len(ok)} checks passed")
    if not all(ok):
        sys.exit(1)
    print("REAL _run_advisory RAN END-TO-END")


if __name__ == "__main__":
    main()
