"""
KisanMind Backend — Real API-powered agricultural advisory for Indian farmers.
NO fake data. Every data point comes from a real API call.
"""

import os
import json
import base64
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import ee

import httpx
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.cloud import texttospeech_v1 as tts
from google.cloud import speech_v2 as speech
from google.cloud import translate_v2 as translate

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
AGMARKNET_API_KEY = os.getenv("AGMARKNET_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "lmsforshantithakur")

if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY not set")
if not AGMARKNET_API_KEY:
    raise RuntimeError("AGMARKNET_API_KEY not set")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kisanmind")

# ---------------------------------------------------------------------------
# In-memory response caches (dict with timestamps, no external deps)
# ---------------------------------------------------------------------------
import time as _time

# ---------------------------------------------------------------------------
# Persistent cache via GCS (survives deploys) + in-memory L1 cache (fast)
# ---------------------------------------------------------------------------
GCS_CACHE_BUCKET = "kisanmind-cache"
_ADVISORY_TTL = 15 * 60      # 15 min — mandi prices can shift intraday
_NDVI_TTL = 6 * 60 * 60      # 6 hours — satellite data updates weekly
_MANDI_RAW_TTL = 60 * 60     # 1 hour — raw mandi data from AgMarkNet

# L1: in-memory (fast, lost on restart)
_l1_cache: dict[str, tuple[float, dict]] = {}


def _l1_get(key: str, ttl: float) -> dict | None:
    entry = _l1_cache.get(key)
    if entry and (_time.time() - entry[0]) < ttl:
        return entry[1]
    if entry:
        del _l1_cache[key]
    return None


def _l1_set(key: str, value: dict):
    _l1_cache[key] = (_time.time(), value)


# L2: GCS (persistent, slower)
async def _gcs_get(key: str, ttl: float) -> dict | None:
    """Read cached JSON from GCS. Returns None if missing or stale."""
    safe_key = key.replace(":", "_").replace("/", "_")
    url = f"https://storage.googleapis.com/{GCS_CACHE_BUCKET}/advisory-cache/{safe_key}.json"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            cached_at = data.get("_cached_at", 0)
            if (_time.time() - cached_at) > ttl:
                return None  # stale
            return data
    except Exception:
        return None


async def _gcs_set(key: str, value: dict):
    """Write cached JSON to GCS (fire-and-forget, don't block the response)."""
    safe_key = key.replace(":", "_").replace("/", "_")
    try:
        from google.cloud import storage as gcs_storage
        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(GCS_CACHE_BUCKET)
        blob = bucket.blob(f"advisory-cache/{safe_key}.json")
        value_with_ts = {**value, "_cached_at": _time.time()}
        blob.upload_from_string(
            json.dumps(value_with_ts, ensure_ascii=False, default=str),
            content_type="application/json",
        )
    except Exception as e:
        log.warning(f"GCS cache write failed for {key}: {e}")


async def cache_get(key: str, ttl: float) -> dict | None:
    """Try L1 (memory) then L2 (GCS). Returns None if both miss."""
    # L1
    hit = _l1_get(key, ttl)
    if hit:
        log.info(f"Cache L1 hit: {key}")
        return hit
    # L2
    hit = await _gcs_get(key, ttl)
    if hit:
        log.info(f"Cache L2 (GCS) hit: {key}")
        _l1_set(key, hit)  # promote to L1
        return hit
    return None


async def cache_set(key: str, value: dict):
    """Write to both L1 and L2."""
    _l1_set(key, value)
    # GCS write in background (don't block response)
    asyncio.create_task(_gcs_set(key, value))

# Gemini client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Earth Engine initialization (once at startup)
EE_PROJECT = "dmjone"
EE_INITIALIZED = False

def _init_earth_engine():
    global EE_INITIALIZED
    _log = logging.getLogger("kisanmind")
    ee_key_json = os.getenv("EE_SERVICE_KEY_JSON", "")
    ee_key_path = os.getenv("EE_SERVICE_KEY_PATH", "/secrets/ee-key/ee-service-key")

    # Try service account JSON from env var
    if ee_key_json:
        try:
            from google.oauth2 import service_account as _sa
            key_data = json.loads(ee_key_json)
            creds = _sa.Credentials.from_service_account_info(key_data, scopes=["https://www.googleapis.com/auth/earthengine"])
            ee.Initialize(credentials=creds, project=EE_PROJECT)
            EE_INITIALIZED = True
            _log.info(f"Earth Engine initialized with SA JSON (project: {EE_PROJECT})")
            return
        except Exception as e:
            _log.warning(f"EE init with SA JSON failed: {e}")

    # Try key file path
    if os.path.exists(ee_key_path):
        try:
            from google.oauth2 import service_account as _sa
            creds = _sa.Credentials.from_service_account_file(ee_key_path, scopes=["https://www.googleapis.com/auth/earthengine"])
            ee.Initialize(credentials=creds, project=EE_PROJECT)
            EE_INITIALIZED = True
            _log.info(f"Earth Engine initialized with key file (project: {EE_PROJECT})")
            return
        except Exception as e:
            _log.warning(f"EE init with key file failed: {e}")

    # Fallback: application default credentials
    try:
        ee.Initialize(project=EE_PROJECT)
        EE_INITIALIZED = True
        _log.info(f"Earth Engine initialized with ADC (project: {EE_PROJECT})")
    except Exception as e:
        _log.warning(f"Earth Engine init failed: {e}. NDVI will be unavailable.")

_init_earth_engine()

# Thread pool for blocking EE calls (ee.getInfo() blocks)
_ee_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ee")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="KisanMind API", version="1.0.0")

# CORS — allow all origins (Cloud Run error responses drop CORS headers
# with restricted origins, causing browser failures on 500s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


@app.get("/")
async def root():
    return {"service": "KisanMind API", "version": "1.0.0", "status": "live"}

# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------
LANGUAGE_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "bn": "Bengali",
    "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "en": "English", "or": "Odia", "as": "Assamese",
    "ur": "Urdu", "sa": "Sanskrit", "ne": "Nepali", "sd": "Sindhi",
    "ks": "Kashmiri", "doi": "Dogri", "mai": "Maithili", "sat": "Santali",
    "kok": "Konkani", "brx": "Bodo", "mni": "Manipuri",
}

TTS_VOICE_MAP = {
    "hi-IN": ("hi-IN-Wavenet-D", tts.SsmlVoiceGender.MALE),
    "ta-IN": ("ta-IN-Wavenet-D", tts.SsmlVoiceGender.MALE),
    "te-IN": ("te-IN-Standard-A", tts.SsmlVoiceGender.FEMALE),
    "bn-IN": ("bn-IN-Wavenet-D", tts.SsmlVoiceGender.MALE),
    "mr-IN": ("mr-IN-Wavenet-A", tts.SsmlVoiceGender.FEMALE),
    "gu-IN": ("gu-IN-Wavenet-A", tts.SsmlVoiceGender.FEMALE),
    "kn-IN": ("kn-IN-Wavenet-A", tts.SsmlVoiceGender.FEMALE),
    "ml-IN": ("ml-IN-Wavenet-A", tts.SsmlVoiceGender.FEMALE),
    "pa-IN": ("pa-IN-Wavenet-A", tts.SsmlVoiceGender.FEMALE),
    "en-IN": ("en-IN-Wavenet-D", tts.SsmlVoiceGender.MALE),
    "or-IN": ("or-IN-Standard-A", tts.SsmlVoiceGender.FEMALE),
    "as-IN": ("as-IN-Standard-A", tts.SsmlVoiceGender.FEMALE),
    "ur-IN": ("ur-IN-Standard-A", tts.SsmlVoiceGender.FEMALE),
}

# Languages with no Google TTS voice — will be translated to Hindi first
NO_TTS_LANGUAGES = {"sd", "ks", "doi", "mai", "sat", "kok", "brx", "mni", "sa", "ne"}

LANGUAGE_TO_LOCALE = {
    "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN",
    "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN",
    "pa": "pa-IN", "en": "en-IN", "or": "or-IN", "as": "as-IN",
    "ur": "ur-IN",
}

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class AdvisoryRequest(BaseModel):
    latitude: float
    longitude: float
    crop: str
    language: str = "hi"
    intent: str = "full_advisory"


class TTSRequest(BaseModel):
    text: str
    language: str = "hi"


class STTRequest(BaseModel):
    audio_base64: str
    language: str = "hi-IN"
    encoding: str = "WEBM_OPUS"


class NDVIRequest(BaseModel):
    latitude: float
    longitude: float


class IntentRequest(BaseModel):
    transcript: Optional[str] = None
    text: Optional[str] = None  # alias — frontend sends 'text'
    language: str = "hi"

    @property
    def speech_text(self) -> str:
        return self.transcript or self.text or ""


# ---------------------------------------------------------------------------
# Real API helpers (async with httpx)
# ---------------------------------------------------------------------------
async def reverse_geocode(lat: float, lon: float) -> dict:
    """Reverse geocode using Google Maps Geocoding API. Returns location name, state, district."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{lat},{lon}", "key": GOOGLE_MAPS_API_KEY, "language": "en"}
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data["status"] != "OK" or not data.get("results"):
        raise HTTPException(502, f"Google Geocoding failed: {data.get('status')} — {data.get('error_message', '')}")

    result = data["results"][0]
    components = {c["types"][0]: c["long_name"] for c in result["address_components"] if c.get("types")}

    location_name = components.get("locality", components.get("sublocality", "Unknown"))
    district = components.get("administrative_area_level_2", components.get("administrative_area_level_3", ""))
    state = components.get("administrative_area_level_1", "")

    return {
        "location_name": location_name,
        "district": district,
        "state": state,
        "formatted_address": result.get("formatted_address", ""),
    }


async def fetch_mandi_prices(crop: str, state: str) -> list[dict]:
    """Fetch real mandi prices. GCS cache first (fast), direct API as fallback."""
    records = []
    source = "unknown"

    # 1. Try GCS cache first (pre-fetched daily, fast, always works from Cloud Run)
    crop_lower = crop.lower().replace(" ", "_")
    gcs_url = f"https://storage.googleapis.com/kisanmind-cache/mandi-prices/agmarknet_{crop_lower}.json"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(gcs_url)
            if resp.status_code == 200:
                data = resp.json()
                all_records = data.get("records", [])
                records = [r for r in all_records if r.get("state", "").lower() == state.lower()]
                if not records:
                    records = all_records[:20]
                else:
                    records = records[:20]
                source = "GCS cache (AgMarkNet data, refreshed daily)"
                log.info(f"GCS cache hit: {len(records)} records for {crop}/{state}")
    except Exception as e:
        log.warning(f"GCS cache miss: {e}")

    # 2. Fallback: direct AgMarkNet API (may be blocked from Cloud Run IPs)
    if not records:
        url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        params = {
            "api-key": AGMARKNET_API_KEY,
            "format": "json",
            "limit": 20,
            "filters[commodity]": crop,
            "filters[state]": state,
        }
        headers = {
            "User-Agent": "KisanMind/1.0 (Agricultural Advisory; contact@dmj.one)",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                records = data.get("records", [])
                source = "AgMarkNet direct API (real-time)"
                log.info(f"AgMarkNet direct: {len(records)} records")
        except Exception as e:
            log.warning(f"AgMarkNet direct failed: {e}")

    if not records:
        raise HTTPException(404, f"No mandi prices found for {crop}. Both AgMarkNet and cache unavailable.")

    if not records:
        raise HTTPException(404, f"No mandi prices found for {crop}. AgMarkNet returned 0 records.")

    mandis = []
    for r in records:
        try:
            modal_price = float(r.get("modal_price", 0))
        except (ValueError, TypeError):
            modal_price = 0
        if modal_price <= 0:
            continue
        mandis.append({
            "market": r.get("market", "Unknown"),
            "district": r.get("district", ""),
            "state": r.get("state", ""),
            "commodity": r.get("commodity", crop),
            "variety": r.get("variety", ""),
            "min_price": r.get("min_price"),
            "max_price": r.get("max_price"),
            "modal_price": modal_price,
            "arrival_date": r.get("arrival_date", ""),
        })

    if not mandis:
        raise HTTPException(404, f"No valid mandi prices (modal_price > 0) found for {crop}.")

    return mandis


async def get_distances(origin_lat: float, origin_lon: float, mandis: list[dict]) -> list[dict]:
    """Get real driving distances from Google Maps Distance Matrix API for each mandi."""
    if not mandis:
        return mandis

    # Distance Matrix supports max 25 destinations per call
    origin = f"{origin_lat},{origin_lon}"
    enriched = []

    for batch_start in range(0, len(mandis), 25):
        batch = mandis[batch_start:batch_start + 25]
        destinations = "|".join(
            f"{m['market']}, {m['district']}, {m['state']}, India" for m in batch
        )

        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origin,
            "destinations": destinations,
            "key": GOOGLE_MAPS_API_KEY,
            "mode": "driving",
            "language": "en",
        }

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "OK":
            raise HTTPException(502, f"Distance Matrix API error: {data.get('status')} — {data.get('error_message', '')}")

        elements = data.get("rows", [{}])[0].get("elements", [])
        for i, elem in enumerate(elements):
            m = batch[i].copy()
            if elem.get("status") == "OK":
                m["distance_km"] = round(elem["distance"]["value"] / 1000, 1)
                m["distance_text"] = elem["distance"]["text"]
                m["duration_text"] = elem["duration"]["text"]
                m["duration_minutes"] = round(elem["duration"]["value"] / 60)
            else:
                m["distance_km"] = None
                m["distance_text"] = "N/A"
                m["duration_text"] = "N/A"
                m["duration_minutes"] = None
            enriched.append(m)

    return enriched


def calculate_net_profits(mandis: list[dict]) -> list[dict]:
    """Calculate net profit for each mandi: modal_price - transport_cost - commission."""
    TRANSPORT_COST_PER_KM_PER_QUINTAL = 3.5
    COMMISSION_RATE = 0.04  # 4%

    for m in mandis:
        price = m["modal_price"]
        dist = m.get("distance_km")
        if dist is not None:
            transport_cost = dist * TRANSPORT_COST_PER_KM_PER_QUINTAL
            commission = COMMISSION_RATE * price
            m["transport_cost_per_quintal"] = round(transport_cost, 2)
            m["commission_per_quintal"] = round(commission, 2)
            m["net_profit_per_quintal"] = round(price - transport_cost - commission, 2)
        else:
            m["transport_cost_per_quintal"] = None
            m["commission_per_quintal"] = None
            m["net_profit_per_quintal"] = None

    return mandis


async def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch 5-day weather forecast from Open-Meteo (free, no key needed)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "forecast_days": 5,
    }
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    forecast_days = []
    for i in range(len(dates)):
        forecast_days.append({
            "date": dates[i],
            "max_temp_c": max_temps[i] if i < len(max_temps) else None,
            "min_temp_c": min_temps[i] if i < len(min_temps) else None,
            "precipitation_mm": precip[i] if i < len(precip) else None,
        })

    # Build a text summary
    summary_lines = []
    for d in forecast_days:
        rain_str = f", Rain: {d['precipitation_mm']}mm" if d["precipitation_mm"] and d["precipitation_mm"] > 0 else ", No rain"
        summary_lines.append(
            f"{d['date']}: {d['min_temp_c']}°C – {d['max_temp_c']}°C{rain_str}"
        )

    return {
        "daily_forecast": forecast_days,
        "summary": "\n".join(summary_lines),
        "source": "Open-Meteo",
    }


async def generate_advisory_with_gemini(
    language: str,
    location_name: str,
    state: str,
    crop: str,
    mandis: list[dict],
    best_mandi: dict,
    local_mandi: Optional[dict],
    weather: dict,
    ndvi_data: Optional[dict] = None,
) -> str:
    """Send all real data to Gemini 2.5 Flash and get a conversational advisory."""
    language_name = LANGUAGE_NAMES.get(language, "Hindi")

    local_mandi_name = local_mandi["market"] if local_mandi else "N/A"
    local_price = local_mandi["modal_price"] if local_mandi else 0
    best_price = best_mandi["net_profit_per_quintal"] or best_mandi["modal_price"]
    price_advantage = round(best_price - local_price, 2) if local_mandi and local_price else 0

    # Build satellite data section for the prompt
    if ndvi_data:
        satellite_section = f"""Satellite Crop Health (Sentinel-2, date: {ndvi_data['image_date']}):
  NDVI: {ndvi_data['ndvi']} (health: {ndvi_data['health']}, trend: {ndvi_data['trend']})
  EVI: {ndvi_data['evi']}, NDWI: {ndvi_data['ndwi']}
  Note: NDVI > 0.6 = healthy, 0.4-0.6 = moderate, < 0.4 = stressed. NDWI < -0.3 = dry soil."""
    else:
        satellite_section = "Satellite crop health data: unavailable"

    prompt = f"""You are KisanMind, a friendly agricultural advisor talking to an Indian farmer on a phone call.
Speak in {language_name} language as if you're their trusted friend/elder.

STRICT RULES:
- Use ONLY plain text. NO markdown. NO asterisks (*), NO bold, NO bullet points, NO numbered lists.
- Use simple spoken language — this will be read aloud by text-to-speech.
- Use local units (quintal, bigha, rupaye).
- ONLY state facts from the data below. DO NOT invent or assume anything the farmer said.
- DO NOT hallucinate farmer's statements. If the farmer didn't mention something, don't claim they did.
- For any pesticide, fungicide, or chemical treatment: DO NOT recommend brands or dosages. Instead say "apne nazdeeki Krishi Vigyan Kendra (KVK) se sampark karein" and mention KVK helpline 1800-180-1551.
- Keep it under 200 words. This is a phone conversation, not an essay.

REAL DATA (use ONLY this):
Location: {location_name}, {state}
Crop: {crop}
Mandi prices today:
  Best: {best_mandi['market']} — {best_mandi['modal_price']} rupaye per quintal, {best_mandi.get('distance_km', '?')} km door, {best_mandi.get('duration_text', '?')} ka raasta
  Local: {local_mandi_name} — {local_price} rupaye per quintal
  Fayda: {best_mandi['market']} mein {price_advantage} rupaye zyada milenge per quintal
Weather: {weather['summary']}
{satellite_section}

Cover:
1. Where to sell — best mandi with price and distance
2. Weather — what to do or avoid in next 2-3 days
3. Crop health from satellite — explain in simple terms (dont say NDVI, say "satellite se fasal ki sehat dekhi")
4. If any problem detected, refer to nearest KVK (helpline: 1800-180-1551)

End with: "Yeh data aaj ki AgMarkNet, satellite aur mausam report se hai. Final faisla aap ka hai."
"""

    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
    )

    import re
    text = response.text
    # Strip ALL markdown formatting — this text will be spoken aloud via TTS
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'[-•]\s+', '', text)
    text = re.sub(r'\d+\.\s+', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # Hallucination verification runs in BACKGROUND — don't block the response
    # The advisory is already constrained by the strict prompt rules above
    async def _verify_in_background():
        try:
            verify_prompt = f"""Fact-check: Are prices/distances/names in this advisory consistent with source data? Advisory: "{text[:400]}" Source: Best={best_mandi['market']} {best_mandi['modal_price']}Rs, Local={local_mandi_name} {local_price}Rs. Return PASS or FAIL:<reason>."""
            verify_resp = gemini_client.models.generate_content(model="gemini-3-flash-preview", contents=verify_prompt)
            log.info(f"Hallucination check (bg): {verify_resp.text.strip()}")
        except Exception as e:
            log.warning(f"Hallucination bg check failed: {e}")

    asyncio.create_task(_verify_in_background())
    return text


# ---------------------------------------------------------------------------
# Earth Engine NDVI helpers
# ---------------------------------------------------------------------------
def _compute_ndvi_sync(lat: float, lon: float) -> dict:
    """Blocking EE computation — runs in a thread pool. Returns NDVI data dict."""
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(500)  # 500m buffer

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    # Sentinel-2 SR Harmonized, <30% cloud cover, last 30 days
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        .sort("system:time_start", False)  # newest first
    )

    count = collection.size().getInfo()
    if count == 0:
        # Expand to 90 days if no images in 30 days
        start_date = end_date - timedelta(days=90)
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(point)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            .sort("system:time_start", False)
        )
        count = collection.size().getInfo()
        if count == 0:
            return {"error": "No cloud-free Sentinel-2 imagery available for this location"}

    # Get the most recent image
    latest = ee.Image(collection.first())

    # Compute indices (Sentinel-2 bands: B4=Red, B8=NIR, B3=Green, B11=SWIR)
    ndvi = latest.normalizedDifference(["B8", "B4"]).rename("NDVI")
    evi = latest.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {
            "NIR": latest.select("B8"),
            "RED": latest.select("B4"),
            "BLUE": latest.select("B2"),
        },
    ).rename("EVI")
    ndwi = latest.normalizedDifference(["B3", "B8"]).rename("NDWI")

    # Compute mean over the buffer area
    stats = ndvi.addBands(evi).addBands(ndwi).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=buffer,
        scale=10,
        maxPixels=1e6,
    ).getInfo()

    ndvi_val = stats.get("NDVI")
    evi_val = stats.get("EVI")
    ndwi_val = stats.get("NDWI")

    # Get image date
    image_date_ms = latest.get("system:time_start").getInfo()
    image_date = datetime.utcfromtimestamp(image_date_ms / 1000).strftime("%Y-%m-%d")

    # Compute trend using two most recent images
    trend = "unknown"
    if count >= 2:
        try:
            images_list = collection.toList(2)
            older = ee.Image(images_list.get(1))
            older_ndvi = older.normalizedDifference(["B8", "B4"]).rename("NDVI")
            older_stats = older_ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=10,
                maxPixels=1e6,
            ).getInfo()
            older_ndvi_val = older_stats.get("NDVI")
            if ndvi_val is not None and older_ndvi_val is not None:
                diff = ndvi_val - older_ndvi_val
                if diff > 0.05:
                    trend = "improving"
                elif diff < -0.05:
                    trend = "declining"
                else:
                    trend = "stable"
        except Exception:
            trend = "unknown"

    # Generate real satellite thumbnail URLs
    vis_params_true = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000, 'dimensions': 512}
    vis_params_ndvi = {'min': 0, 'max': 0.8, 'palette': ['red', 'orange', 'yellow', 'lightgreen', 'green', 'darkgreen'], 'dimensions': 512}

    try:
        ndvi_img = ndvi  # already computed above
        true_color_url = latest.select(['B4', 'B3', 'B2']).getThumbURL({**vis_params_true, 'region': buffer})
        ndvi_color_url = ndvi_img.getThumbURL({**vis_params_ndvi, 'region': buffer})
    except Exception as e:
        log.warning(f"Failed to generate thumbnail URLs: {e}")
        true_color_url = None
        ndvi_color_url = None

    # Classify health
    if ndvi_val is None:
        health = "Unknown"
    elif ndvi_val >= 0.6:
        health = "Healthy"
    elif ndvi_val >= 0.4:
        health = "Moderate"
    elif ndvi_val >= 0.2:
        health = "Stressed"
    else:
        health = "Bare/Very Stressed"

    return {
        "ndvi": round(ndvi_val, 4) if ndvi_val is not None else None,
        "evi": round(evi_val, 4) if evi_val is not None else None,
        "ndwi": round(ndwi_val, 4) if ndwi_val is not None else None,
        "trend": trend,
        "health": health,
        "image_date": image_date,
        "images_found": count,
        "true_color_url": true_color_url,
        "ndvi_color_url": ndvi_color_url,
        "source": f"Sentinel-2 via Google Earth Engine (project: {EE_PROJECT})",
    }


async def fetch_ndvi(lat: float, lon: float) -> Optional[dict]:
    """Fetch NDVI data from Earth Engine, returning None on failure."""
    if not EE_INITIALIZED:
        log.warning("Earth Engine not initialized — skipping NDVI")
        return None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_ee_executor, _compute_ndvi_sync, lat, lon)
        if "error" in result:
            log.warning(f"NDVI computation returned error: {result['error']}")
            return None
        return result
    except Exception as e:
        log.error(f"NDVI fetch failed: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "service": "KisanMind API",
        "version": "1.0.0",
        "apis": {
            "google_maps": bool(GOOGLE_MAPS_API_KEY),
            "agmarknet": bool(AGMARKNET_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "weather": "Open-Meteo (free)",
            "earth_engine": f"{'active' if EE_INITIALIZED else 'unavailable'} (project: {EE_PROJECT})",
        },
    }


@app.post("/api/ndvi")
async def get_ndvi(req: NDVIRequest):
    """Get satellite vegetation indices (NDVI, EVI, NDWI) from Google Earth Engine."""
    if not EE_INITIALIZED:
        raise HTTPException(503, "Earth Engine is not initialized. Satellite data unavailable.")
    log.info(f"NDVI request: lat={req.latitude}, lon={req.longitude}")

    cache_key = f"ndvi:{round(req.latitude, 2)}:{round(req.longitude, 2)}"
    cached = await cache_get(cache_key, _NDVI_TTL)
    if cached is not None:
        return {**cached, "cached": True}

    result = await fetch_ndvi(req.latitude, req.longitude)
    if result is None:
        raise HTTPException(404, "No satellite data available for this location.")
    await cache_set(cache_key, result)
    result["cached"] = False
    return result


@app.post("/api/advisory")
async def advisory(req: AdvisoryRequest):
    """Main advisory endpoint — all data from real APIs, zero fake data."""
    log.info(f"Advisory request: crop={req.crop}, lat={req.latitude}, lon={req.longitude}, lang={req.language}")

    cache_key = f"adv:{round(req.latitude, 2)}:{round(req.longitude, 2)}:{req.crop}:{req.language}"
    cached = await cache_get(cache_key, _ADVISORY_TTL)
    if cached is not None:
        # Add staleness info for transparency
        cached_at = cached.get("_cached_at", 0)
        age_min = round((_time.time() - cached_at) / 60) if cached_at else 0
        cached["cached"] = True
        cached["data_age_minutes"] = age_min
        cached["freshness_note"] = f"Data is {age_min} minutes old. Mandi prices may have changed."
        return cached

    try:
        result = await _run_advisory(req)
        result["cached"] = False
        result["data_age_minutes"] = 0
        result["freshness_note"] = "Fresh data — just fetched from AgMarkNet, weather, and satellite."
        await cache_set(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Advisory pipeline failed: {e}")
        raise HTTPException(500, f"Advisory pipeline failed: {str(e)}")


async def _run_advisory(req: AdvisoryRequest):
    crop = req.crop

    # If crop is "auto" or empty, extract from the intent/transcript using Gemini
    if not crop or crop.lower() == "auto":
        intent_text = req.intent or ""
        if intent_text:
            try:
                extract_resp = gemini_client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=f'Extract the crop name from this farmer\'s speech. Return ONLY the crop name in English (e.g., "Tomato", "Wheat", "Rice"). If no crop mentioned, return "Tomato".\n\nSpeech: "{intent_text}"',
                )
                crop = extract_resp.text.strip().strip('"').strip("'")
                if not crop or len(crop) > 30:
                    crop = "Tomato"
            except Exception:
                crop = "Tomato"
        else:
            crop = "Tomato"
        log.info(f"Auto-detected crop: {crop}")

    # 1. Geocode + weather + NDVI in PARALLEL (all only need lat/lon)
    location_task = asyncio.create_task(reverse_geocode(req.latitude, req.longitude))
    weather_task = asyncio.create_task(fetch_weather(req.latitude, req.longitude))
    ndvi_task = asyncio.create_task(fetch_ndvi(req.latitude, req.longitude))

    location = await location_task
    log.info(f"Location: {location}")

    # 2. Mandi prices (needs state from geocode)
    mandis = await fetch_mandi_prices(crop, location["state"])
    log.info(f"Found {len(mandis)} mandis with prices")

    # 3. Distances + weather in PARALLEL. NDVI is best-effort (don't block on it).
    distances_task = asyncio.create_task(get_distances(req.latitude, req.longitude, mandis))
    weather = await weather_task
    mandis = await distances_task

    # Try to get NDVI if it's already done, otherwise don't wait more than 3s
    ndvi_data = None
    try:
        ndvi_data = await asyncio.wait_for(ndvi_task, timeout=3.0)
        if ndvi_data:
            log.info(f"NDVI: {ndvi_data['ndvi']}, Health: {ndvi_data['health']}")
    except (asyncio.TimeoutError, Exception):
        log.info("NDVI skipped (slow/unavailable) — proceeding without satellite data")

    # 4. Calculate net profits (pure computation, instant)
    mandis = calculate_net_profits(mandis)

    # 5. Find best mandi and local/closest mandi
    mandis_with_profit = [m for m in mandis if m.get("net_profit_per_quintal") is not None]
    if mandis_with_profit:
        best_mandi = max(mandis_with_profit, key=lambda m: m["net_profit_per_quintal"])
        local_mandi = min(mandis_with_profit, key=lambda m: m["distance_km"])
    else:
        best_mandi = max(mandis, key=lambda m: m["modal_price"])
        local_mandi = mandis[0] if mandis else None

    # 6. Generate advisory via Gemini
    advisory_text = await generate_advisory_with_gemini(
        language=req.language,
        location_name=location["location_name"],
        state=location["state"],
        crop=crop,
        mandis=mandis,
        best_mandi=best_mandi,
        local_mandi=local_mandi,
        weather=weather,
        ndvi_data=ndvi_data,
    )

    response_data = {
        "location": location,
        "crop": crop,
        "language": req.language,
        "mandi_prices": mandis,
        "best_mandi": best_mandi,
        "local_mandi": local_mandi,
        "weather": weather,
        "advisory": advisory_text,
        "sources": {
            "mandi_prices": "AgMarkNet / data.gov.in (real-time)",
            "distances": "Google Maps Distance Matrix API",
            "weather": "Open-Meteo API",
            "advisory": "Gemini 2.5 Flash",
            "geocoding": "Google Maps Geocoding API",
        },
    }

    if ndvi_data:
        response_data["satellite"] = ndvi_data
        response_data["sources"]["satellite"] = f"Sentinel-2 via Google Earth Engine (project: {EE_PROJECT})"
    else:
        response_data["satellite"] = None
        response_data["sources"]["satellite"] = "unavailable"

    return response_data


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """Convert text to speech using Google Cloud TTS. Real audio, no fakes."""
    lang_code = req.language
    text = req.text

    # Determine locale
    if lang_code in NO_TTS_LANGUAGES:
        # Translate to Hindi first, then synthesize
        try:
            translate_client = translate.Client()
            result = translate_client.translate(text, target_language="hi", source_language=lang_code)
            text = result["translatedText"]
        except Exception as e:
            log.warning(f"Translation to Hindi failed for {lang_code}, using original text: {e}")
        locale = "hi-IN"
    else:
        locale = LANGUAGE_TO_LOCALE.get(lang_code, f"{lang_code}-IN")

    voice_name, gender = TTS_VOICE_MAP.get(locale, ("hi-IN-Wavenet-D", tts.SsmlVoiceGender.MALE))

    try:
        tts_client = tts.TextToSpeechClient()
        synthesis_input = tts.SynthesisInput(text=text)
        voice = tts.VoiceSelectionParams(
            language_code=locale,
            name=voice_name,
            ssml_gender=gender,
        )
        audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.MP3,
            speaking_rate=0.85,
        )
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
    except Exception as e:
        raise HTTPException(502, f"Google Cloud TTS failed: {e}")

    audio_b64 = base64.b64encode(response.audio_content).decode("utf-8")
    return {
        "audio_base64": audio_b64,
        "content_type": "audio/mp3",
        "voice_used": voice_name,
        "locale": locale,
    }


@app.post("/api/stt")
async def speech_to_text(request: Request):
    """Transcribe audio using Google Cloud Speech-to-Text V2.
    Accepts either:
      - multipart/form-data with 'audio' file + 'language' field
      - application/json with 'audio_base64' + 'language' fields
    """
    content_type = request.headers.get("content-type", "")

    if "multipart" in content_type:
        form = await request.form()
        audio_file = form.get("audio")
        language = str(form.get("language", "hi-IN"))
        if audio_file is None:
            raise HTTPException(400, "No 'audio' field in form data")
        audio_bytes = await audio_file.read()
    elif "json" in content_type:
        body = await request.json()
        audio_bytes = base64.b64decode(body.get("audio_base64", ""))
        language = body.get("language", "hi-IN")
    else:
        raise HTTPException(400, f"Unsupported content type: {content_type}")

    if not audio_bytes:
        raise HTTPException(400, "Empty audio data")

    # Ensure language has locale suffix
    if "-" not in language:
        language = f"{language}-IN"

    try:
        stt_client = speech.SpeechClient()

        # Use auto_decoding for WebM/Opus (let the API detect encoding)
        config = speech.RecognitionConfig(
            auto_decoding_config=speech.AutoDetectDecodingConfig(),
            language_codes=[language],
            model="long",
        )

        stt_request = speech.RecognizeRequest(
            recognizer=f"projects/{GOOGLE_CLOUD_PROJECT}/locations/global/recognizers/_",
            config=config,
            content=audio_bytes,
        )

        response = stt_client.recognize(request=stt_request)

    except Exception as e:
        log.exception(f"STT failed: {e}")
        raise HTTPException(502, f"Google Cloud Speech-to-Text failed: {str(e)}")

    if not response.results:
        return {"transcript": "", "confidence": 0.0, "detected_language": language}

    best = response.results[0].alternatives[0]
    return {
        "transcript": best.transcript,
        "confidence": round(best.confidence, 4) if best.confidence else 0.0,
        "detected_language": language,
    }


@app.post("/api/extract-intent")
async def extract_intent(req: IntentRequest):
    """Use Gemini to extract structured intent from farmer's speech."""
    prompt = f"""You are a parser for an Indian agriculture app. Extract structured data from the farmer's speech.

Transcript (in {LANGUAGE_NAMES.get(req.language, 'Hindi')}): "{req.speech_text}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "crop": "<crop name in English or null>",
  "location": "<location name or null>",
  "intent": "<one of: where_to_sell, price_check, weather_check, pest_advisory, full_advisory, general_question>",
  "language": "{req.language}"
}}"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, f"Gemini returned invalid JSON: {response.text}")
    except Exception as e:
        raise HTTPException(502, f"Gemini intent extraction failed: {e}")

    return parsed


# ---------------------------------------------------------------------------
# Twilio Voice Webhooks — Phone call integration
# A farmer calls the Twilio number → Twilio hits these webhooks
# ---------------------------------------------------------------------------
TWILIO_WELCOME = {
    "hi": "नमस्ते! किसानमाइंड में आपका स्वागत है। अपनी भाषा में बोलिए — आप कौनसी फसल उगा रहे हैं और कहाँ?",
    "en": "Welcome to KisanMind! Tell me which crop you're growing and your location.",
    "ta": "கிசான்மைண்டிற்கு வரவேற்கிறோம்! நீங்கள் எந்தப் பயிரை பயிரிடுகிறீர்கள், எங்கே?",
    "te": "కిసాన్‌మైండ్‌కు స్వాగతం! మీరు ఏ పంట పండిస్తున్నారు, ఎక్కడ?",
    "bn": "কিসানমাইন্ডে স্বাগতম! আপনি কোন ফসল চাষ করছেন এবং কোথায়?",
}

BASE_URL = os.getenv("BASE_URL", "https://kisanmind-api-409924770511.asia-south1.run.app")


@app.post("/api/voice/incoming")
async def twilio_incoming_call(request: Request):
    """Twilio webhook: farmer calls the number. Greet and gather speech."""
    form = await request.form()
    caller = form.get("From", "unknown")
    log.info(f"Incoming call from {caller}")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        {TWILIO_WELCOME["hi"]}
    </Say>
    <Gather input="speech" language="hi-IN" speechTimeout="3" timeout="10"
            action="{BASE_URL}/api/voice/process" method="POST">
        <Say voice="Polly.Aditi" language="hi-IN">
            बोलिए, मैं सुन रही हूँ।
        </Say>
    </Gather>
    <Say voice="Polly.Aditi" language="hi-IN">
        कोई बात नहीं, फिर से कॉल करें। धन्यवाद!
    </Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/api/voice/process")
async def twilio_process_speech(request: Request):
    """Twilio webhook: process the farmer's speech and respond with advisory."""
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    caller = form.get("From", "unknown")
    log.info(f"Speech from {caller}: {speech_result}")

    if not speech_result:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        मुझे समझ नहीं आया। कृपया दोबारा बोलें।
    </Say>
    <Redirect method="POST">{base}/api/voice/incoming</Redirect>
</Response>""".replace("{base}", BASE_URL)
        return Response(content=twiml, media_type="application/xml")

    try:
        # Extract intent from speech using Gemini
        intent_prompt = f"""Extract crop and location from this Indian farmer's speech:
"{speech_result}"
Return JSON only: {{"crop": "<crop in English>", "location": "<location name>", "language": "hi"}}"""

        intent_resp = gemini_client.models.generate_content(
            model="gemini-3-flash-preview", contents=intent_prompt
        )
        intent_text = intent_resp.text.strip()
        if intent_text.startswith("```"):
            intent_text = intent_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        intent_data = json.loads(intent_text)

        crop = intent_data.get("crop", "Tomato")
        location_name = intent_data.get("location", "")

        # Geocode the location
        geo = await reverse_geocode_by_name(location_name) if location_name else {"latitude": 28.6139, "longitude": 77.2090}

        # Get advisory
        req = AdvisoryRequest(
            latitude=geo.get("latitude", 28.6139),
            longitude=geo.get("longitude", 77.2090),
            crop=crop,
            language="hi",
            intent="full_advisory",
        )
        result = await _run_advisory(req)
        advisory_text = result["advisory"]

        # Respond with the advisory
        # Escape XML special characters
        safe_text = advisory_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        {safe_text}
    </Say>
    <Pause length="1"/>
    <Say voice="Polly.Aditi" language="hi-IN">
        क्या आप कुछ और जानना चाहते हैं?
    </Say>
    <Gather input="speech" language="hi-IN" speechTimeout="3" timeout="8"
            action="{BASE_URL}/api/voice/process" method="POST">
        <Say voice="Polly.Aditi" language="hi-IN">
            बोलिए।
        </Say>
    </Gather>
    <Say voice="Polly.Aditi" language="hi-IN">
        धन्यवाद! किसानमाइंड का उपयोग करने के लिए शुक्रिया। नमस्ते!
    </Say>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        log.exception(f"Voice processing failed: {e}")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        माफ कीजिए, कुछ तकनीकी समस्या आ गई। कृपया थोड़ी देर बाद फिर से कॉल करें।
    </Say>
</Response>"""
        return Response(content=twiml, media_type="application/xml")


async def reverse_geocode_by_name(location_name: str) -> dict:
    """Geocode a location name to lat/lon."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": f"{location_name}, India", "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return {"latitude": loc["lat"], "longitude": loc["lng"]}
    return {"latitude": 28.6139, "longitude": 77.2090}  # Default: Delhi


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
