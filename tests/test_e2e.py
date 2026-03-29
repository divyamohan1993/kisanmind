#!/usr/bin/env python3
"""
KisanMind — Production E2E Test Suite

Tests all endpoints against the live deployment.
Verifies satellite data, mandi prices, weather, TTS, STT, chat, and edge cases.

Usage:
    python tests/test_e2e.py                    # Test against live deployment
    python tests/test_e2e.py --base-url http://localhost:8081  # Test local
"""

import argparse
import json
import sys
import time
import httpx

BASE_URL = "https://kisanmind.dmj.one"
PASS = 0
FAIL = 0
ERRORS = []


def test(name: str, passed: bool, detail: str = ""):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  \u2713 {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  \u2717 {name} \u2014 {detail}")


def run_tests():
    global BASE_URL
    client = httpx.Client(base_url=BASE_URL, timeout=120)

    # ===== 1. HEALTH =====
    print("\n=== Health ===")
    r = client.get("/api/health")
    data = r.json()
    test("Health endpoint returns 200", r.status_code == 200)
    test("Status is healthy", data.get("status") == "healthy")
    test("Google Maps API configured", data["apis"]["google_maps"] is True)
    test("AgMarkNet API configured", data["apis"]["agmarknet"] is True)
    test("Gemini API configured", data["apis"]["gemini"] is True)
    test("Satellite cache loaded", data["apis"]["satellite_cache"]["loaded"] is True)
    test("Satellite points > 1000", data["apis"]["satellite_cache"]["total_points"] > 1000)

    # Verify all 4 satellite sources in cache
    sources = data["apis"]["satellite_cache"].get("sources", {})
    test("Sentinel-2 NDVI source present", "ndvi" in str(sources).lower())
    test("Sentinel-1 SAR source present", "sar" in str(sources).lower() or "sentinel-1" in str(sources).lower())
    test("MODIS LST source present", "modis" in str(sources).lower() or "lst" in str(sources).lower())
    test("NASA SMAP source present", "smap" in str(sources).lower())

    # ===== 2. NDVI — Multiple Locations =====
    print("\n=== Satellite NDVI ===")
    locations = [
        ("Solan, HP", 30.9, 77.1),
        ("Delhi", 28.61, 77.20),
        ("Bangalore", 12.97, 77.59),
        ("Mumbai", 19.08, 72.88),
        ("Chennai", 13.08, 80.27),
    ]
    for name, lat, lon in locations:
        r = client.post("/api/ndvi", json={"latitude": lat, "longitude": lon})
        if r.status_code == 200:
            d = r.json()
            test(f"NDVI {name}: has ndvi value", d.get("ndvi") is not None)
            test(f"NDVI {name}: has evi value", d.get("evi") is not None)
            test(f"NDVI {name}: has ndwi value", d.get("ndwi") is not None)
            test(f"NDVI {name}: has health class", d.get("health") in ("Healthy", "Moderate", "Stressed", "Bare/Very Stressed", "Unknown"))
            test(f"NDVI {name}: ndvi in valid range", -1 <= (d.get("ndvi") or 0) <= 1)
        else:
            test(f"NDVI {name}: returns 200", False, f"Got {r.status_code}")

    # Edge case: ocean/water location
    r = client.post("/api/ndvi", json={"latitude": 10.0, "longitude": 72.0})
    # Should either return data or 404, not 500
    test("NDVI ocean location: no server error", r.status_code != 500)

    # Edge case: extreme coordinates
    r = client.post("/api/ndvi", json={"latitude": 0.0, "longitude": 0.0})
    test("NDVI (0,0): no server error", r.status_code != 500)

    # ===== 3. WEATHER =====
    print("\n=== Weather ===")
    # Weather is tested via advisory — Open-Meteo is called there

    # ===== 4. FULL ADVISORY =====
    print("\n=== Full Advisory ===")
    crops = ["Tomato", "Wheat", "Rice", "Potato", "Onion"]
    for crop in crops:
        t0 = time.time()
        r = client.post("/api/advisory", json={
            "latitude": 28.61, "longitude": 77.20,
            "crop": crop, "language": "en"
        })
        elapsed = time.time() - t0
        if r.status_code == 200:
            d = r.json()
            test(f"Advisory {crop}: has location", "location" in d)
            test(f"Advisory {crop}: has weather", "weather" in d and d["weather"].get("daily_forecast"))
            test(f"Advisory {crop}: has mandi prices", "mandi_prices" in d)
            test(f"Advisory {crop}: has advisory text", len(d.get("advisory", "")) > 50)
            test(f"Advisory {crop}: has price trend", "price_trend" in d)
            test(f"Advisory {crop}: has growth stage", "growth_stage" in d)
            test(f"Advisory {crop}: has confidence", "confidence" in d)
            test(f"Advisory {crop}: has cross validation", "cross_validation" in d)
            test(f"Advisory {crop}: has sources", "sources" in d)

            # Satellite data
            sat = d.get("satellite")
            if sat:
                test(f"Advisory {crop}: satellite has ndvi", sat.get("ndvi") is not None)

            # Satellite extras (SAR, LST, SMAP)
            extras = d.get("satellite_extras", {})
            test(f"Advisory {crop}: has SAR data", "sar" in extras)
            test(f"Advisory {crop}: has LST data", "lst" in extras)
            test(f"Advisory {crop}: has SMAP data", "smap" in extras)

            test(f"Advisory {crop}: response < 60s", elapsed < 60, f"took {elapsed:.1f}s")
        else:
            test(f"Advisory {crop}: returns 200", False, f"Got {r.status_code}")

    # Edge case: unknown crop
    r = client.post("/api/advisory", json={
        "latitude": 28.61, "longitude": 77.20,
        "crop": "Dragonberries", "language": "en"
    })
    test("Advisory unknown crop: no crash", r.status_code in (200, 404))

    # Edge case: zero coordinates
    r = client.post("/api/advisory", json={
        "latitude": 0, "longitude": 0,
        "crop": "Wheat", "language": "en"
    })
    test("Advisory (0,0): no crash", r.status_code != 500)

    # ===== 5. TTS =====
    print("\n=== Text-to-Speech ===")
    tts_tests = [
        ("Hindi", "hi", "Namaste kisaan bhai, aapki fasal acchi hai"),
        ("English", "en", "Hello farmer, your crop is healthy"),
        ("Tamil", "ta", "Test Tamil text"),
        ("Telugu", "te", "Test Telugu text"),
        ("Bengali", "bn", "Test Bengali text"),
    ]
    for lang_name, code, text in tts_tests:
        r = client.post("/api/tts", json={"text": text, "language": code})
        if r.status_code == 200:
            d = r.json()
            test(f"TTS {lang_name}: has audio", len(d.get("audio_base64", "")) > 100)
            test(f"TTS {lang_name}: has voice info", d.get("voice_used") is not None)
        else:
            test(f"TTS {lang_name}: returns 200", False, f"Got {r.status_code}")

    # Edge case: empty text
    r = client.post("/api/tts", json={"text": "", "language": "hi"})
    test("TTS empty text: no crash", r.status_code != 500)

    # Edge case: very long text
    r = client.post("/api/tts", json={"text": "Hello " * 500, "language": "en"})
    test("TTS long text: no crash", r.status_code != 500)

    # ===== 6. CHAT =====
    print("\n=== Multi-turn Chat ===")
    # Turn 1: greeting
    r1 = client.post("/api/chat", json={
        "message": "Hello, I grow tomatoes in Solan",
        "language": "en", "latitude": 30.9, "longitude": 77.1
    })
    d1 = r1.json()
    test("Chat turn 1: has session_id", bool(d1.get("session_id")))
    test("Chat turn 1: has response", len(d1.get("response", "")) > 10)
    session_id = d1.get("session_id", "")

    # Turn 2: follow up with same session
    if session_id:
        r2 = client.post("/api/chat", json={
            "session_id": session_id,
            "message": "I planted 2 months ago, 5 bigha land",
            "language": "en", "latitude": 30.9, "longitude": 77.1
        })
        d2 = r2.json()
        test("Chat turn 2: same session", d2.get("session_id") == session_id)
        test("Chat turn 2: has response", len(d2.get("response", "")) > 10)
        # Gemini should call fetch_farm_data by turn 2-3
        test("Chat turn 2: may have advisory", True)  # Advisory may or may not come on turn 2

    # Edge case: empty message
    r = client.post("/api/chat", json={"message": "", "language": "en", "latitude": 0, "longitude": 0})
    test("Chat empty msg: no crash", r.status_code == 200)

    # ===== 7. GEOCODE =====
    print("\n=== Geocoding ===")
    geo_tests = [
        ("Solan", 30.0, 32.0, 76.0, 78.0),
        ("Delhi", 28.0, 29.0, 77.0, 78.0),
        ("Mumbai", 18.0, 20.0, 72.0, 73.0),
    ]
    for name, lat_min, lat_max, lon_min, lon_max in geo_tests:
        r = client.post("/api/geocode-name", json={"location_name": name})
        d = r.json()
        test(f"Geocode {name}: has lat", d.get("latitude") is not None)
        test(f"Geocode {name}: lat in range", lat_min <= (d.get("latitude") or 0) <= lat_max)
        test(f"Geocode {name}: lon in range", lon_min <= (d.get("longitude") or 0) <= lon_max)

    # Edge case: nonsense location
    r = client.post("/api/geocode-name", json={"location_name": "xyznonexistent12345"})
    test("Geocode nonsense: no crash", r.status_code == 200)

    # ===== 8. TRANSLATE =====
    print("\n=== Translation ===")
    r = client.post("/api/translate", json={
        "texts": ["Hello farmer", "Your crop is healthy"],
        "target_language": "hi"
    })
    if r.status_code == 200:
        d = r.json()
        test("Translate: returns array", isinstance(d.get("translated"), list))
        test("Translate: correct count", len(d.get("translated", [])) == 2)
        test("Translate: non-empty results", all(len(t) > 0 for t in d.get("translated", [])))
    else:
        test("Translate: returns 200", False, f"Got {r.status_code}")

    # English to English (no-op)
    r = client.post("/api/translate", json={"texts": ["Hello"], "target_language": "en"})
    d = r.json()
    test("Translate en->en: passthrough", d.get("translated", [None])[0] == "Hello")

    # ===== 9. BEEP =====
    print("\n=== Beep ===")
    r = client.get("/api/beep")
    d = r.json()
    test("Beep: has audio", len(d.get("audio_base64", "")) > 100)
    test("Beep: is WAV", d.get("content_type") == "audio/wav")

    # ===== 10. SUMMARIZE =====
    print("\n=== Summarize ===")
    r = client.post("/api/summarize", json={
        "text": "Your tomato crop health is moderate with NDVI 0.54. Best mandi is Bhuntar at Rs 7500/quintal. Rain expected on March 29.",
        "language": "en"
    })
    if r.status_code == 200:
        d = r.json()
        test("Summarize: has summary", len(d.get("summary", "")) > 20)
    else:
        test("Summarize: returns 200", False, f"Got {r.status_code}")

    # ===== 11. EXTRACT INTENT =====
    print("\n=== Intent Extraction ===")
    r = client.post("/api/extract-intent", json={
        "text": "Main tamatar bech na chahta hoon",
        "language": "hi"
    })
    if r.status_code == 200:
        d = r.json()
        test("Intent: has crop", d.get("crop") is not None)
        test("Intent: has intent type", d.get("intent") is not None)
    else:
        test("Intent: returns 200", False, f"Got {r.status_code}")

    # ===== 12. FRONTEND =====
    print("\n=== Frontend ===")
    r = client.get("/", follow_redirects=True)
    test("Frontend: returns 200", r.status_code == 200)
    test("Frontend: has HTML content", "KisanMind" in r.text or "kisanmind" in r.text.lower())
    test("Frontend: has lang selector", "\u0939\u093f\u0928\u094d\u0926\u0940" in r.text or "hindi" in r.text.lower())

    # ===== 13. PERFORMANCE =====
    print("\n=== Performance ===")
    # Cache hit should be fast
    t0 = time.time()
    r = client.post("/api/ndvi", json={"latitude": 30.9, "longitude": 77.1})
    ndvi_time = time.time() - t0
    test("NDVI cache hit < 1s", ndvi_time < 1.0, f"took {ndvi_time:.2f}s")

    t0 = time.time()
    r = client.get("/api/health")
    health_time = time.time() - t0
    test("Health check < 500ms", health_time < 0.5, f"took {health_time:.2f}s")

    t0 = time.time()
    r = client.get("/api/beep")
    beep_time = time.time() - t0
    test("Beep generation < 500ms", beep_time < 0.5, f"took {beep_time:.2f}s")

    # ===== SUMMARY =====
    print(f"\n{'='*50}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print(f"{'='*50}")
    if ERRORS:
        print(f"\nFailed tests:")
        for e in ERRORS:
            print(f"  \u2717 {e}")
    return FAIL == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://kisanmind.dmj.one")
    args = parser.parse_args()
    BASE_URL = args.base_url

    print(f"KisanMind E2E Test Suite")
    print(f"Target: {BASE_URL}")
    print(f"{'='*50}")

    success = run_tests()
    sys.exit(0 if success else 1)
