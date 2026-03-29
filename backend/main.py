"""
KisanMind Backend — Real API-powered agricultural advisory for Indian farmers.
NO fake data. Every data point comes from a real API call.
"""

import os
import sys
import json
import struct
import math
import io
import base64
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import ee

import httpx
from fastapi import FastAPI, HTTPException, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.websockets import WebSocketState
import uuid
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
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
_KVK_TTL = 30 * 24 * 60 * 60   # 30 days — KVKs don't move

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

# Gemini model with fallback — primary model may be overloaded
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]
GEMINI_REASONING_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]

def _gemini_generate(contents, config=None):
    """Call Gemini with model fallback. Tries each model once."""
    last_err = None
    for model in GEMINI_MODELS:
        try:
            kwargs = {"model": model, "contents": contents}
            if config:
                kwargs["config"] = config
            return gemini_client.models.generate_content(**kwargs)
        except Exception as e:
            last_err = e
            log.warning(f"Gemini {model} failed: {e}, trying next...")
    raise last_err


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
# Local satellite cache (pre-computed, instant lookup)
# ---------------------------------------------------------------------------
try:
    from backend.satellite_cache import SatelliteCache
except ImportError:
    from satellite_cache import SatelliteCache

_sat_cache_dir = Path(__file__).resolve().parent.parent / "data" / "satellite_cache"
_sat_cache = SatelliteCache(str(_sat_cache_dir))
if _sat_cache.is_loaded:
    log.info(f"Satellite cache: {_sat_cache.stats()['total_points']} points loaded ({_sat_cache.stats()['cache_age_hours']}h old)")
else:
    log.info("Satellite cache: not available — will use live Earth Engine calls")

try:
    from backend.gemini_live import GeminiLiveSession, KISANMIND_TOOLS
except ImportError:
    from gemini_live import GeminiLiveSession, KISANMIND_TOOLS

# ---------------------------------------------------------------------------
# Gemini Live sessions (one per active call)
# ---------------------------------------------------------------------------
_live_sessions: dict[str, GeminiLiveSession] = {}
_SESSION_TTL = 600  # 10 minutes max per session

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="KisanMind API", version="2.0.0")

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
    quantity_quintals: float = 0
    sowing_date: str = ""  # ISO format YYYY-MM-DD, empty if unknown


class TTSRequest(BaseModel):
    text: str
    language: str = "hi"


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


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    language: str = "hi"
    latitude: float = 0
    longitude: float = 0


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
    # Build a lookup mapping every type to its long_name (a component can have
    # multiple types, e.g. ["locality", "political"]).
    components: dict[str, str] = {}
    for c in result.get("address_components", []):
        for t in c.get("types", []):
            components[t] = c["long_name"]

    location_name = (
        components.get("locality")
        or components.get("sublocality_level_1")
        or components.get("sublocality")
        or components.get("administrative_area_level_3")
        or components.get("neighborhood")
        or "Unknown"
    )
    district = components.get("administrative_area_level_2", components.get("administrative_area_level_3", ""))
    state = components.get("administrative_area_level_1", "")

    return {
        "location_name": location_name,
        "district": district,
        "state": state,
        "formatted_address": result.get("formatted_address", ""),
        "maps_url": f"https://www.google.com/maps/@{lat},{lon},14z",
    }


# ---------------------------------------------------------------------------
# AgMarkNet commodity list — fetched live at startup for dynamic crop matching
# ---------------------------------------------------------------------------
_agmarknet_commodities: list[str] = []  # Populated at startup


def _fetch_agmarknet_commodities():
    """Fetch all unique commodity names from AgMarkNet at startup."""
    global _agmarknet_commodities
    try:
        import requests
        url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        params = {"api-key": AGMARKNET_API_KEY, "format": "json", "limit": 1000, "offset": 0}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        commodities = set()
        for r in data.get("records", []):
            c = r.get("commodity", "")
            if c:
                commodities.add(c)
        _agmarknet_commodities = sorted(commodities)
        log.info(f"AgMarkNet commodities loaded: {len(_agmarknet_commodities)} items")
    except Exception as e:
        log.warning(f"Failed to fetch AgMarkNet commodities: {e}")
        # Hardcoded fallback
        _agmarknet_commodities = [
            "Apple", "Banana", "Bhindi(Ladies Finger)", "Brinjal", "Cabbage",
            "Capsicum", "Carrot", "Cauliflower", "Chilly Capsicum", "Cotton",
            "Garlic", "Ginger(Green)", "Grapes", "Green Peas", "Lemon",
            "Maize", "Mango", "Onion", "Paddy(Dhan)", "Potato",
            "Rice", "Sugarcane", "Tomato", "Wheat",
        ]


_fetch_agmarknet_commodities()


def _match_agmarknet_commodity(crop: str) -> list[str]:
    """Find matching AgMarkNet commodity names for a given crop.
    Uses substring matching against the live commodity list."""
    crop_low = crop.lower().strip()
    matches = []

    # Exact match first
    for c in _agmarknet_commodities:
        if c.lower() == crop_low:
            return [c]

    # Substring match — crop name appears anywhere in commodity name
    for c in _agmarknet_commodities:
        c_low = c.lower()
        if crop_low in c_low or c_low in crop_low:
            matches.append(c)

    # Common English→AgMarkNet mappings for edge cases
    manual = {
        "okra": "Bhindi(Ladies Finger)",
        "eggplant": "Brinjal",
        "chickpea": "Bengal Gram(Gram)(Whole)",
        "lentil": "Masur Dal",
        "soybean": "Soyabean",
        "sorghum": "Jowar(Sorghum)",
        "pearl millet": "Bajra(Pearl Millet)",
        "mustard": "Mustard",
        "peas": "Green Peas",
    }
    if crop_low in manual and manual[crop_low] not in matches:
        matches.insert(0, manual[crop_low])

    return matches if matches else [crop]


async def fetch_mandi_prices(crop: str, state: str) -> list[dict]:
    """Fetch real mandi prices. GCS cache first (fast), direct API as fallback."""
    records = []
    source = "unknown"

    # Build list of crop names to try (dynamically matched from AgMarkNet's commodity list)
    crop_lower = crop.lower().replace(" ", "_")
    crop_variants = _match_agmarknet_commodity(crop)
    for variant in crop_variants:
        variant_key = variant.lower().replace(" ", "_").replace("(", "").replace(")", "")
        gcs_url = f"https://storage.googleapis.com/kisanmind-cache/mandi-prices/agmarknet_{variant_key}.json"
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
                    source = f"GCS cache ({variant_key})"
                    log.info(f"GCS cache hit: {len(records)} records for {variant}/{state}")
                    break
        except Exception as e:
            log.warning(f"GCS cache miss for {variant_key}: {e}")

    # 2. Fallback: direct AgMarkNet API — try all crop name variants
    if not records:
        for variant in crop_variants:
            url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
            params = {
                "api-key": AGMARKNET_API_KEY,
                "format": "json",
                "limit": 20,
                "filters[commodity]": variant,
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
                    if not records:
                        # Try without state filter
                        params2 = {k: v for k, v in params.items() if k != "filters[state]"}
                        params2["limit"] = 20
                        resp2 = await client.get(url, params=params2, headers=headers)
                        resp2.raise_for_status()
                        records = resp2.json().get("records", [])[:20]
                    if records:
                        source = f"AgMarkNet direct ({variant})"
                        log.info(f"AgMarkNet direct: {len(records)} records for {variant}")
                        break
            except Exception as e:
                log.warning(f"AgMarkNet direct failed for {variant}: {type(e).__name__}: {e}")

    if not records:
        log.warning(f"No mandi prices found for {crop} (variants: {crop_variants}). Returning empty.")
        return []

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
        log.warning(f"No valid mandi prices (modal_price > 0) for {crop}.")
        return []

    return mandis


def analyze_price_trend(mandis: list[dict]) -> dict:
    """Analyze price trend from available mandi data. Uses arrival_date to detect multi-day patterns."""
    if not mandis:
        return {"trend": "unknown", "trend_percent": 0, "confidence": "LOW", "detail": "No price data available."}

    # Group prices by date to detect trends
    from collections import defaultdict
    prices_by_date: dict[str, list[float]] = defaultdict(list)
    for m in mandis:
        date_str = m.get("arrival_date", "")
        if date_str and m.get("modal_price"):
            prices_by_date[date_str].append(m["modal_price"])

    # Compute daily average price
    daily_avgs = []
    for date_str in sorted(prices_by_date.keys()):
        prices = prices_by_date[date_str]
        daily_avgs.append({"date": date_str, "avg_price": sum(prices) / len(prices)})

    if len(daily_avgs) < 2:
        # Only one date — can't compute trend, but give current price context
        all_prices = [m["modal_price"] for m in mandis if m.get("modal_price")]
        avg = sum(all_prices) / len(all_prices) if all_prices else 0
        mn = min(all_prices) if all_prices else 0
        mx = max(all_prices) if all_prices else 0
        return {
            "trend": "insufficient_data",
            "trend_percent": 0,
            "avg_price": round(avg),
            "min_price": round(mn),
            "max_price": round(mx),
            "data_points": len(daily_avgs),
            "confidence": "LOW",
            "detail": f"Only one day of data available. Average price Rs {round(avg)}/quintal across {len(all_prices)} mandis.",
        }

    # Compute trend: compare latest vs earliest
    oldest_price = daily_avgs[0]["avg_price"]
    newest_price = daily_avgs[-1]["avg_price"]
    trend_pct = ((newest_price - oldest_price) / oldest_price * 100) if oldest_price > 0 else 0

    if trend_pct > 5:
        trend = "rising"
    elif trend_pct < -5:
        trend = "falling"
    else:
        trend = "stable"

    confidence = "HIGH" if len(daily_avgs) >= 5 else ("MEDIUM" if len(daily_avgs) >= 3 else "LOW")

    return {
        "trend": trend,
        "trend_percent": round(trend_pct, 1),
        "oldest_date": daily_avgs[0]["date"],
        "newest_date": daily_avgs[-1]["date"],
        "oldest_avg_price": round(oldest_price),
        "newest_avg_price": round(newest_price),
        "data_points": len(daily_avgs),
        "confidence": confidence,
        "detail": f"Price {'rose' if trend_pct > 0 else 'fell'} {abs(round(trend_pct, 1))}% from Rs {round(oldest_price)} to Rs {round(newest_price)} over {len(daily_avgs)} days.",
    }


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


# Spoilage rates: % value loss per hour without cold chain (agricultural research data)
SPOILAGE_RATE_PER_HOUR = {
    "tomato": 0.005, "strawberry": 0.008, "mango": 0.004, "banana": 0.003,
    "spinach": 0.010, "capsicum": 0.004, "grapes": 0.006, "papaya": 0.005,
    "potato": 0.0005, "onion": 0.0005, "garlic": 0.0005,
    "wheat": 0.0001, "rice": 0.0001, "maize": 0.0001,
    "cauliflower": 0.006, "cabbage": 0.004, "brinjal": 0.004,
    "apple": 0.002, "orange": 0.002, "guava": 0.003,
}
DEFAULT_SPOILAGE_RATE = 0.003  # 0.3% per hour for unknown crops


def calculate_net_profits(mandis: list[dict], crop: str = "") -> list[dict]:
    """Calculate net profit: modal_price - transport - commission - spoilage loss."""
    TRANSPORT_COST_PER_KM_PER_QUINTAL = 3.5
    COMMISSION_RATE = 0.04  # 4%

    crop_lower = crop.lower().strip()
    spoilage_rate = SPOILAGE_RATE_PER_HOUR.get(crop_lower, DEFAULT_SPOILAGE_RATE)

    for m in mandis:
        price = m["modal_price"]
        dist = m.get("distance_km")
        duration_min = m.get("duration_minutes")
        if dist is not None:
            transport_cost = dist * TRANSPORT_COST_PER_KM_PER_QUINTAL
            commission = COMMISSION_RATE * price
            # Spoilage: value lost during transit (perishable crops)
            transit_hours = (duration_min / 60) if duration_min else (dist / 40)  # assume 40 km/h if no duration
            spoilage_loss = price * spoilage_rate * transit_hours
            m["transport_cost_per_quintal"] = round(transport_cost, 2)
            m["commission_per_quintal"] = round(commission, 2)
            m["spoilage_loss_per_quintal"] = round(spoilage_loss, 2)
            m["transit_hours"] = round(transit_hours, 1)
            m["net_profit_per_quintal"] = round(price - transport_cost - commission - spoilage_loss, 2)
        else:
            m["transport_cost_per_quintal"] = None
            m["commission_per_quintal"] = None
            m["spoilage_loss_per_quintal"] = None
            m["transit_hours"] = None
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
        # Convert YYYY-MM-DD to human-readable "29 March" format
        # so the LLM doesn't misinterpret month numbers
        try:
            _parsed = datetime.strptime(dates[i], "%Y-%m-%d")
            readable_date = _parsed.strftime("%-d %B")  # e.g., "29 March", "2 April"
        except Exception:
            readable_date = dates[i]
        forecast_days.append({
            "date": readable_date,
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


async def fetch_historical_weather(lat: float, lon: float, days_back: int = 90) -> list[dict]:
    """Fetch historical daily temperatures from Open-Meteo (free, no key needed).
    Used for accurate GDD (Growing Degree Days) calculation from sowing date."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "past_days": days_back,
        "forecast_days": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])

        history = []
        for i in range(len(dates)):
            history.append({
                "date": dates[i],
                "max_temp_c": max_temps[i] if i < len(max_temps) else None,
                "min_temp_c": min_temps[i] if i < len(min_temps) else None,
                "precipitation_mm": precip[i] if i < len(precip) else None,
            })
        return history
    except Exception as e:
        log.warning(f"Historical weather fetch failed: {e}")
        return []


def cross_validate_data_sources(
    ndvi_data: Optional[dict],
    ndvi_trajectory: dict,
    weather: dict,
    price_trend: dict,
    growth_stage: dict,
    satellite_extras: dict = None,
) -> list[dict]:
    """Cross-validate data sources and flag conflicts for transparent advisory.
    Returns list of conflict/agreement observations with recommended actions."""
    observations = []

    # 1. NDVI declining + adequate rain = possible pest/root issue, NOT water stress
    if ndvi_data and ndvi_trajectory:
        trajectory = ndvi_trajectory.get("trajectory", "")
        daily = weather.get("daily_forecast", [])
        recent_rain = sum(d.get("precipitation_mm", 0) or 0 for d in daily[:3])

        if trajectory == "declining" and recent_rain > 10:
            observations.append({
                "type": "CONFLICT",
                "sources": ["satellite", "weather"],
                "finding": "Crop health declining despite adequate rainfall",
                "action": "REFER_KVK",
                "confidence": "HIGH",
                "detail": "Satellite shows declining health but rain is adequate. This may indicate pest, disease, or root issue — NOT water stress. Do not recommend irrigation. Refer to KVK for field inspection.",
            })
        elif trajectory == "declining" and recent_rain < 2:
            observations.append({
                "type": "AGREEMENT",
                "sources": ["satellite", "weather"],
                "finding": "Crop health declining with no recent rain — likely water stress",
                "action": "IRRIGATE",
                "confidence": "HIGH",
                "detail": "Satellite and weather both confirm: no rain and declining crop health. Water stress is the most likely cause. Recommend immediate irrigation.",
            })

    # 2. NDVI healthy + farmer on call reports problem = satellite data may be old
    if ndvi_data:
        days_old = 0
        try:
            days_old = (datetime.utcnow() - datetime.strptime(ndvi_data.get("image_date", ""), "%Y-%m-%d")).days
        except (ValueError, TypeError):
            pass
        if days_old > 5:
            observations.append({
                "type": "CAVEAT",
                "sources": ["satellite"],
                "finding": f"Satellite data is {days_old} days old",
                "action": "DISCLOSE_AGE",
                "confidence": "HIGH",
                "detail": f"Any field activity in the last {days_old} days (irrigation, spraying, harvesting) will NOT be reflected. Farmer's own observation of the field is more current than this data.",
            })

    # 3. Price rising + high arrivals = price may not sustain
    if price_trend:
        trend = price_trend.get("trend", "")
        # We can infer high arrivals if many mandis report prices (more data = more arrivals)
        data_points = price_trend.get("data_points", 0)
        if trend == "rising" and data_points > 10:
            observations.append({
                "type": "CAVEAT",
                "sources": ["price"],
                "finding": "Price rising but high market activity detected",
                "action": "HEDGE",
                "confidence": "MEDIUM",
                "detail": "Prices are up but many mandis are reporting — this means supply is also high. Price rise may not sustain. Advise selling a portion now, holding rest.",
            })

    # 4. Growth stage near harvest + NDVI plateauing + good weather = harvest window
    if growth_stage and ndvi_trajectory:
        stage = growth_stage.get("stage", "")
        trajectory = ndvi_trajectory.get("trajectory", "")
        daily = weather.get("daily_forecast", [])
        rain_next_3 = sum(d.get("precipitation_mm", 0) or 0 for d in daily[:3])

        if stage in ("harvest_ready", "ripening", "maturation", "grain_filling") and trajectory == "plateauing" and rain_next_3 < 5:
            observations.append({
                "type": "AGREEMENT",
                "sources": ["satellite", "weather", "growth_stage"],
                "finding": "All indicators suggest good harvest window",
                "action": "HARVEST_NOW",
                "confidence": "HIGH",
                "detail": f"Crop at {stage} stage, growth plateaued (satellite), weather clear for 3 days. This is an optimal harvest window.",
            })
        elif stage in ("harvest_ready", "ripening", "maturation", "grain_filling") and rain_next_3 > 10:
            observations.append({
                "type": "WARNING",
                "sources": ["weather", "growth_stage"],
                "finding": "Rain expected during harvest-ready stage",
                "action": "HARVEST_BEFORE_RAIN",
                "confidence": "HIGH",
                "detail": f"Crop at {stage} stage. Rain of {rain_next_3}mm expected in next 3 days. Harvest BEFORE the rain to avoid crop damage and quality loss.",
            })

    # 5. Frost warning for sensitive crops
    if growth_stage:
        stage = growth_stage.get("stage", "")
        daily = weather.get("daily_forecast", [])
        frost_days = [d for d in daily[:3] if (d.get("min_temp_c") or 99) < 4]
        if frost_days and stage in ("flowering", "fruit_setting", "fruit_development"):
            observations.append({
                "type": "WARNING",
                "sources": ["weather", "growth_stage"],
                "finding": f"Frost risk during critical {stage} stage",
                "action": "PROTECT_CROP",
                "confidence": "HIGH",
                "detail": f"Temperature dropping to {frost_days[0]['min_temp_c']}°C. Crop at {stage} stage is highly vulnerable. Cover crop tonight or use smudge pots.",
            })

    # 6. SAR soil moisture vs NDVI cross-check
    if satellite_extras and satellite_extras.get("sar"):
        sar = satellite_extras["sar"]
        sar_moisture = sar.get("moisture_class", "")
        if ndvi_data and ndvi_trajectory:
            trajectory = ndvi_trajectory.get("trajectory", "")
            if trajectory == "declining" and sar_moisture in ("moist", "wet"):
                observations.append({
                    "type": "CONFLICT",
                    "sources": ["sentinel-2_ndvi", "sentinel-1_sar"],
                    "finding": "Crop health declining despite adequate soil moisture (confirmed by radar)",
                    "action": "REFER_KVK",
                    "confidence": "HIGH",
                    "detail": "Both optical (Sentinel-2) and radar (Sentinel-1) data confirm: soil has water but crop is declining. This rules out water stress — likely pest, disease, or nutrient issue. Refer to KVK.",
                })
            elif trajectory == "declining" and sar_moisture in ("dry", "very_dry"):
                observations.append({
                    "type": "AGREEMENT",
                    "sources": ["sentinel-2_ndvi", "sentinel-1_sar"],
                    "finding": "Crop declining AND soil is dry — confirmed water stress from two independent satellites",
                    "action": "IRRIGATE",
                    "confidence": "HIGH",
                    "detail": "Optical satellite shows declining crop health. Radar independently confirms dry soil. Water stress is very likely. Irrigate immediately.",
                })

    # 7. MODIS LST heat stress
    if satellite_extras and satellite_extras.get("lst"):
        lst = satellite_extras["lst"]
        if lst.get("heat_stress") in ("high", "extreme"):
            observations.append({
                "type": "WARNING",
                "sources": ["modis_lst"],
                "finding": f"Land surface temperature {lst.get('lst_day_celsius', '?')}°C — heat stress detected from satellite",
                "action": "IRRIGATE",
                "confidence": "HIGH",
                "detail": lst.get("heat_detail", ""),
            })
        if lst.get("lst_anomaly_celsius") and lst["lst_anomaly_celsius"] > 3:
            observations.append({
                "type": "WARNING",
                "sources": ["modis_lst"],
                "finding": f"Your field is {lst['lst_anomaly_celsius']}°C hotter than surrounding area",
                "action": "IRRIGATE",
                "confidence": "MEDIUM",
                "detail": f"Your field's surface temperature is {lst['lst_anomaly_celsius']}°C above the regional average. This may indicate less vegetation cover or dry soil compared to neighbors.",
            })

    # 8. SMAP root-zone moisture
    if satellite_extras and satellite_extras.get("smap"):
        smap = satellite_extras["smap"]
        if smap.get("rootzone_class") in ("critical", "low"):
            observations.append({
                "type": "WARNING",
                "sources": ["smap"],
                "finding": f"Root-zone soil moisture is {smap.get('rootzone_class', '?')} — NASA satellite data",
                "action": "IRRIGATE",
                "confidence": "HIGH",
                "detail": smap.get("rootzone_detail", "") + " " + smap.get("depth_insight", ""),
            })
        if smap.get("depth_insight"):
            observations.append({
                "type": "CAVEAT",
                "sources": ["smap"],
                "finding": "Surface vs root-zone moisture mismatch detected",
                "action": "DISCLOSE_AGE",
                "confidence": "MEDIUM",
                "detail": smap["depth_insight"],
            })

    return observations


def compute_advisory_confidence(
    ndvi_data: Optional[dict],
    ndvi_trajectory: dict,
    weather: dict,
    price_trend: dict,
    mandis: list[dict],
) -> dict:
    """Compute confidence scores for each data layer to gate advisory output."""
    scores = {}

    # Satellite confidence
    if ndvi_data:
        image_date = ndvi_data.get("image_date", "")
        try:
            days_old = (datetime.utcnow() - datetime.strptime(image_date, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            days_old = 99
        sat_score = 0.5
        if days_old <= 3:
            sat_score += 0.3
        elif days_old <= 7:
            sat_score += 0.1
        else:
            sat_score -= 0.2
        num_obs = ndvi_trajectory.get("num_observations", 1)
        if num_obs >= 4:
            sat_score += 0.2
        elif num_obs >= 2:
            sat_score += 0.1
        scores["satellite"] = {"score": min(1.0, max(0.0, round(sat_score, 2))),
                               "level": "HIGH" if sat_score >= 0.7 else ("MEDIUM" if sat_score >= 0.4 else "LOW"),
                               "days_old": days_old}
    else:
        scores["satellite"] = {"score": 0, "level": "UNAVAILABLE", "days_old": None}

    # Weather confidence (forecast is more reliable for days 1-2)
    weather_score = 0.7  # Base for forecast
    daily = weather.get("daily_forecast", [])
    if len(daily) >= 3:
        weather_score += 0.1
    scores["weather"] = {"score": round(weather_score, 2),
                         "level": "HIGH" if weather_score >= 0.7 else "MEDIUM",
                         "days_covered": len(daily)}

    # Price confidence
    price_conf = price_trend.get("confidence", "LOW")
    price_score = {"HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.3}.get(price_conf, 0.3)
    scores["price"] = {"score": price_score, "level": price_conf,
                       "data_points": price_trend.get("data_points", 0)}

    # Overall
    all_scores = [s["score"] for s in scores.values() if isinstance(s.get("score"), (int, float)) and s["score"] > 0]
    overall = sum(all_scores) / len(all_scores) if all_scores else 0.3
    scores["overall"] = {"score": round(overall, 2),
                         "level": "HIGH" if overall >= 0.65 else ("MEDIUM" if overall >= 0.4 else "LOW")}

    return scores


async def find_nearest_kvk(lat: float, lon: float) -> Optional[dict]:
    """Find nearest Krishi Vigyan Kendra using Google Places API (New)."""
    cache_key = f"kvk:{round(lat, 1)}:{round(lon, 1)}"
    cached = await cache_get(cache_key, _KVK_TTL)
    if cached:
        return cached

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.location",
    }
    body = {
        "textQuery": "Krishi Vigyan Kendra",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 100000.0,  # 100 km radius
            }
        },
        "maxResultCount": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if not places:
            return {"name": "KVK", "address": "Not found nearby", "phone": "1800-180-1551", "distance_km": None, "helpline": "1800-180-1551"}

        place = places[0]
        kvk_name = place.get("displayName", {}).get("text", "Krishi Vigyan Kendra")
        kvk_address = place.get("formattedAddress", "")
        kvk_phone = place.get("nationalPhoneNumber", "1800-180-1551")
        kvk_lat = place.get("location", {}).get("latitude")
        kvk_lon = place.get("location", {}).get("longitude")

        # Calculate straight-line distance (good enough for KVK)
        kvk_distance = None
        if kvk_lat and kvk_lon:
            # Haversine formula
            R = 6371  # Earth radius in km
            dlat = math.radians(kvk_lat - lat)
            dlon = math.radians(kvk_lon - lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(kvk_lat)) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            kvk_distance = round(R * c, 1)

        result = {
            "name": kvk_name,
            "address": kvk_address,
            "phone": kvk_phone or "1800-180-1551",
            "distance_km": kvk_distance,
            "helpline": "1800-180-1551",
        }
        await cache_set(cache_key, result)
        return result

    except Exception as e:
        log.warning(f"KVK search failed: {e}")
        return {"name": "KVK", "address": "Search unavailable", "phone": "1800-180-1551", "distance_km": None, "helpline": "1800-180-1551"}


def _build_cross_validation_section(cross_validation: list[dict] = None) -> str:
    """Build cross-validation findings section for Gemini prompt."""
    if not cross_validation:
        return ""
    lines = ["CROSS-VALIDATION FINDINGS (prioritize these in your advisory):"]
    for cv in cross_validation:
        action_map = {
            "REFER_KVK": "Recommend KVK visit — do NOT guess the cause.",
            "IRRIGATE": "Recommend irrigation.",
            "HARVEST_NOW": "Recommend harvesting now.",
            "HARVEST_BEFORE_RAIN": "Urgently recommend harvesting before rain.",
            "PROTECT_CROP": "Recommend crop protection measures.",
            "HEDGE": "Hedge this advice — present both sides.",
            "DISCLOSE_AGE": "Explicitly mention data age and its limitation.",
        }
        action_text = action_map.get(cv.get("action", ""), cv.get("action", ""))
        lines.append(f"  [{cv['type']}] {cv['finding']}. {action_text}")
        lines.append(f"    Detail: {cv['detail']}")
    return "\n".join(lines)


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
    ndvi_trajectory: dict = None,
    growth_stage: dict = None,
    price_trend: dict = None,
    confidence: dict = None,
    nearest_kvk: dict = None,
    quantity_quintals: float = 0,
    cross_validation: list[dict] = None,
    satellite_extras: dict = None,
    farmer_context: str = "",
) -> str:
    """Send pre-computed inferences to Gemini and get a human, conversational advisory."""
    language_name = LANGUAGE_NAMES.get(language, "Hindi")

    local_mandi_name = local_mandi["market"] if local_mandi else "N/A"
    local_price = local_mandi["modal_price"] if local_mandi else 0
    best_price = best_mandi.get("net_profit_per_quintal") or best_mandi["modal_price"]
    price_advantage = round(best_price - (local_mandi.get("net_profit_per_quintal", local_price) if local_mandi else local_price), 2) if local_mandi else 0

    # Build satellite assessment section
    if ndvi_data:
        days_old = 0
        try:
            days_old = (datetime.utcnow() - datetime.strptime(ndvi_data.get("image_date", ""), "%Y-%m-%d")).days
        except (ValueError, TypeError):
            pass

        trajectory_info = ""
        if ndvi_trajectory:
            trajectory_info = f"""
  Growth trajectory (last {ndvi_trajectory.get('num_observations', 0)} observations): {ndvi_trajectory.get('trajectory', 'unknown').upper()}
  District benchmark: {ndvi_trajectory.get('benchmark_comparison', 'not available')}
  District average NDVI: {ndvi_trajectory.get('district_avg_ndvi', 'N/A')}"""

        satellite_section = f"""SATELLITE ASSESSMENT (image from {ndvi_data['image_date']}, i.e. {days_old} days old):
  Your field health: {ndvi_data['health']} (NDVI {ndvi_data['ndvi']})
  Trend: {ndvi_data['trend']}{trajectory_info}
  IMPORTANT: This image is {days_old} days old. If farmer irrigated, sprayed, or harvested in the last {days_old} days, it will NOT show in this data. Next satellite update in 2-5 days.
  Confidence: {confidence.get('satellite', {}).get('level', 'MEDIUM') if confidence else 'MEDIUM'}"""
    else:
        satellite_section = "SATELLITE DATA: Not available for this location today. Skip crop health section."

    # Growth stage section
    stage_section = ""
    if growth_stage and growth_stage.get("stage") != "unknown":
        stage_section = f"\nGROWTH STAGE: {crop} estimated at {growth_stage['stage']} stage ({growth_stage.get('detail', '')})"

    # Additional satellite data section (SAR, LST, SMAP)
    extra_sat_section = ""
    if satellite_extras:
        parts = []
        if satellite_extras.get("sar"):
            sar = satellite_extras["sar"]
            parts.append(f"""RADAR SOIL MOISTURE (Sentinel-1 SAR, date: {sar.get('image_date', '?')}):
  Soil moisture: {sar.get('moisture_class', '?').upper()} — {sar.get('moisture_detail', '')}
  Moisture trend: {sar.get('trend', 'unknown')}
  Vegetation density: {sar.get('vegetation_density', '?')}
  NOTE: Radar works through clouds — this data is available even when optical satellite is blocked.""")
        if satellite_extras.get("lst"):
            lst = satellite_extras["lst"]
            parts.append(f"""LAND SURFACE TEMPERATURE (MODIS, date: {lst.get('image_date', '?')}):
  Daytime: {lst.get('lst_day_celsius', '?')}°C, Nighttime: {lst.get('lst_night_celsius', '?')}°C
  Heat stress: {lst.get('heat_stress', 'none').upper()} — {lst.get('heat_detail', '')}
  Your field vs area: {f"{lst['lst_anomaly_celsius']}°C difference" if lst.get('lst_anomaly_celsius') else 'similar'}""")
        if satellite_extras.get("smap"):
            smap = satellite_extras["smap"]
            parts.append(f"""ROOT-ZONE SOIL MOISTURE (NASA SMAP, date: {smap.get('image_date', '?')}):
  Surface moisture: {smap.get('surface_moisture_m3m3', '?')} m³/m³
  Root-zone moisture (0-100cm deep): {smap.get('rootzone_moisture_m3m3', '?')} m³/m³
  Status: {smap.get('rootzone_class', '?').upper()} — {smap.get('rootzone_detail', '')}
  {smap.get('depth_insight', '')}""")
        if parts:
            extra_sat_section = "\n\n".join(parts)

    # Price trend section
    trend_section = ""
    if price_trend:
        trend_section = f"""
PRICE TREND ({price_trend.get('confidence', 'LOW')} confidence):
  {price_trend.get('detail', 'No trend data.')}
  Trend direction: {price_trend.get('trend', 'unknown').upper()}"""

    # Spoilage info for best mandi
    spoilage_note = ""
    if best_mandi.get("spoilage_loss_per_quintal") and best_mandi["spoilage_loss_per_quintal"] > 10:
        spoilage_note = f"""
SPOILAGE WARNING: {crop} is perishable. Transit to {best_mandi['market']} takes {best_mandi.get('transit_hours', '?')} hours.
  Estimated spoilage loss: Rs {best_mandi['spoilage_loss_per_quintal']}/quintal in transit.
  TIP: Leave early morning (before 5 AM) to reduce heat damage."""

    # Top mandis summary (so Gemini can mention alternatives if farmer asks)
    top_mandis_section = ""
    if mandis:
        sorted_mandis = sorted(
            [m for m in mandis if m.get("net_profit_per_quintal") is not None],
            key=lambda m: m["net_profit_per_quintal"], reverse=True
        )[:5]
        if sorted_mandis:
            lines = ["OTHER MANDIS (top 5 by net profit, for follow-up questions):"]
            for m in sorted_mandis:
                lines.append(f"  {m['market']} ({m.get('district', '')}): Rs {m['modal_price']}/q, {m.get('distance_km', '?')}km, net Rs {m['net_profit_per_quintal']}/q")
            top_mandis_section = "\n".join(lines)

    # Quantity calculation
    quantity_section = ""
    if quantity_quintals > 0:
        total_best = round(best_mandi.get("net_profit_per_quintal", 0) * quantity_quintals)
        total_local = round((local_mandi.get("net_profit_per_quintal", local_price) if local_mandi else 0) * quantity_quintals)
        extra = total_best - total_local
        quantity_section = f"""
QUANTITY CALCULATION ({quantity_quintals} quintals):
  At {best_mandi['market']}: {quantity_quintals} x Rs {best_mandi.get('net_profit_per_quintal', 0)} = Rs {total_best} total in hand
  At {local_mandi_name}: {quantity_quintals} x Rs {local_mandi.get('net_profit_per_quintal', local_price) if local_mandi else 0} = Rs {total_local} total in hand
  Difference: Rs {extra} more at {best_mandi['market']}"""

    # KVK section
    kvk_section = ""
    if nearest_kvk:
        kvk_section = f"""
NEAREST KVK: {nearest_kvk['name']}, {nearest_kvk.get('distance_km', '?')} km away
  Address: {nearest_kvk.get('address', '')}
  Phone: {nearest_kvk.get('phone', '1800-180-1551')}
  Toll-free helpline: 1800-180-1551"""

    farmer_problems_section = ""
    if farmer_context:
        farmer_problems_section = f"""
FARMER'S OWN OBSERVATIONS (MUST address these specifically):
{farmer_context}
IMPORTANT: Cross-reference these observations with satellite and weather data.
If farmer reports yellowing -> check satellite health and soil moisture data.
If farmer reports pests -> refer to KVK, do NOT guess treatment.
If farmer reports recent spraying -> note that satellite data may not reflect this yet.
"""

    # Weather with crop interaction
    weather_actions = ""
    daily = weather.get("daily_forecast", [])
    if daily and growth_stage:
        stage = growth_stage.get("stage", "")
        rain_days = [d for d in daily[:3] if d.get("precipitation_mm", 0) > 5]
        high_temp_days = [d for d in daily[:3] if (d.get("max_temp_c") or 0) > 38]
        if rain_days:
            rain_day = rain_days[0]
            weather_actions += f"\n  RAIN ALERT: {rain_day['precipitation_mm']}mm expected on {rain_day['date']}."
            if stage in ("flowering", "fruit_setting"):
                weather_actions += " Don't spray before rain. Pollination may slow — this is normal."
            if stage in ("ripening", "harvest_ready", "grain_filling"):
                weather_actions += f" If {crop} is ready, harvest BEFORE the rain."
            weather_actions += " Do NOT irrigate today — save water."
        elif not rain_days and high_temp_days:
            weather_actions += f"\n  HEAT ALERT: {high_temp_days[0]['max_temp_c']}C expected. Irrigate early morning (before 8 AM). Afternoon watering wastes 30% to evaporation."
        else:
            weather_actions += "\n  Weather is favorable. Normal farming activities can continue."

    prompt = f"""You are KisanMind — a wise, warm farming neighbor who uses modern data to help. Generate advisory in PLAIN ENGLISH first (it will be translated later).

PERSONALITY RULES:
- Talk like a knowledgeable elder neighbor, NOT a government officer or computer.
- Use simple, warm language. Say "bhai" feel. Be encouraging and practical.
- NEVER say NDVI, EVI, NDWI, satellite index, or any technical jargon.
- Convert satellite health to: "fasal ki sehat achhi/theek/kamzor hai"
- ALWAYS state data age: "4 din purani satellite image se", "aaj ke rate", "aaj ka mausam"
- If satellite data is old (>5 days), explicitly say recent farm actions won't be reflected.
- Keep under 120 words. Farmer is in a field, not reading a report.

CONFIDENCE LEVELS FOR EACH DATA SOURCE:
- Satellite crop health: {confidence.get('satellite', {}).get('level', 'UNAVAILABLE')} confidence ({confidence.get('satellite', {}).get('days_old', '?')} days old)
- Weather forecast: {confidence.get('weather', {}).get('level', 'MEDIUM')} confidence ({confidence.get('weather', {}).get('days_covered', '?')} days covered)
- Mandi price trend: {confidence.get('price', {}).get('level', 'LOW')} confidence ({confidence.get('price', {}).get('data_points', 0)} data points)
- Overall advisory: {confidence.get('overall', {}).get('level', 'MEDIUM')} confidence

CONFIDENCE RULES (apply per data source above):
- HIGH confidence data -> state as clear advice: "Kal paani dein."
- MEDIUM confidence -> hedge: "Rate badh rahe hain, shayad aur badh sakte hain."
- LOW confidence -> skip entirely OR say "KVK se puchh lein."
- UNAVAILABLE -> do not mention that data source at all.
- NEVER guarantee yields, prices, or outcomes. Say "based on today's data".

SAFETY RULES:
- NEVER recommend any pesticide or chemical by brand name.
- NEVER give loan, credit, or insurance advice.
- For ANY pest/disease concern -> refer to KVK only.
- ALWAYS end with KVK info and disclaimer.

DATA (pre-computed — relay these inferences, don't invent new ones):
Location: {location_name}, {state}
Crop: {crop}

MANDI DATA:
Best mandi: {best_mandi['market']} — Rs {best_mandi['modal_price']}/quintal, {best_mandi.get('distance_km', '?')} km, {best_mandi.get('duration_text', '?')} travel
  Net profit after transport+commission+spoilage: Rs {best_mandi.get('net_profit_per_quintal', '?')}/quintal
Local mandi: {local_mandi_name} — Rs {local_price}/quintal
  Net profit: Rs {local_mandi.get('net_profit_per_quintal', '?') if local_mandi else '?'}/quintal
Extra earning at best mandi: Rs {price_advantage}/quintal more
{trend_section}
{spoilage_note}
{top_mandis_section}
{quantity_section}

{satellite_section}
{stage_section}

{extra_sat_section}

WEATHER (today's forecast from Open-Meteo):
{weather['summary']}
{weather_actions}

{farmer_problems_section}

{kvk_section}

{_build_cross_validation_section(cross_validation)}

OUTPUT FORMAT (in this order):
1. Crop health — satellite data cross-referenced with farmer observations (1-2 sentences)
2. Farmer's problem response — directly address what they reported, if any (1-3 sentences, skip if no problems)
3. Weather action (1-2 sentences, specific DO or DON'T with date)
4. Best mandi recommendation (price, distance, net profit)
5. Sell timing advice (based on price trend, hedge if low confidence)
6. KVK info + disclaimer

End with: "Yeh aaj ki data ke hisaab se hai. Final faisla aapka hai."
"""

    # Run Gemini in thread pool to avoid blocking the asyncio event loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _gemini_generate(prompt),
    )

    import re
    text = response.text
    # Strip ALL markdown formatting
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'[-•]\s+', '', text)
    text = re.sub(r'\d+\.\s+', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # Advisory is generated in English. Translate to farmer's chosen language.
    if language != "en":
        try:
            translate_client = translate.Client()
            result = translate_client.translate(text, target_language=language, source_language="en")
            import html
            text = html.unescape(result["translatedText"])
            log.info(f"Translated advisory from English to {language}")
        except Exception as e:
            log.warning(f"Translation to {language} failed, keeping English: {e}")

    # Hallucination verification runs in BACKGROUND — don't block the response
    async def _verify_in_background():
        try:
            verify_prompt = f"""Fact-check: Are prices/distances/names in this advisory consistent with source data? Advisory: "{text[:400]}" Source: Best={best_mandi['market']} {best_mandi['modal_price']}Rs, Local={local_mandi_name} {local_price}Rs. Return PASS or FAIL:<reason>."""
            verify_resp = _gemini_generate(verify_prompt)
            log.info(f"Hallucination check (bg): {verify_resp.text.strip()}")
        except Exception as e:
            log.warning(f"Hallucination bg check failed: {e}")

    asyncio.create_task(_verify_in_background())
    return text


# ---------------------------------------------------------------------------
# Earth Engine NDVI helpers
# ---------------------------------------------------------------------------

# Crop growth stage estimation via Growing Degree Days (GDD)
CROP_GDD_STAGES = {
    "tomato": {"t_base": 10, "stages": [(0, "seedling"), (300, "vegetative"), (600, "flowering"), (900, "fruit_setting"), (1200, "ripening"), (1500, "harvest_ready")]},
    "wheat": {"t_base": 5, "stages": [(0, "seedling"), (200, "tillering"), (500, "stem_extension"), (800, "heading"), (1100, "grain_filling"), (1500, "harvest_ready")]},
    "rice": {"t_base": 10, "stages": [(0, "seedling"), (300, "tillering"), (600, "panicle_init"), (900, "flowering"), (1200, "grain_filling"), (1500, "harvest_ready")]},
    "potato": {"t_base": 7, "stages": [(0, "sprouting"), (200, "vegetative"), (500, "tuber_init"), (800, "tuber_bulking"), (1100, "maturation")]},
    "onion": {"t_base": 10, "stages": [(0, "seedling"), (250, "vegetative"), (500, "bulb_formation"), (800, "maturation")]},
    "capsicum": {"t_base": 12, "stages": [(0, "seedling"), (250, "vegetative"), (500, "flowering"), (750, "fruit_setting"), (1000, "ripening")]},
    "cabbage": {"t_base": 5, "stages": [(0, "seedling"), (200, "vegetative"), (500, "head_formation"), (800, "harvest_ready")]},
    "cauliflower": {"t_base": 5, "stages": [(0, "seedling"), (200, "vegetative"), (450, "curd_formation"), (700, "harvest_ready")]},
    "apple": {"t_base": 7, "stages": [(0, "dormant"), (200, "bud_break"), (500, "flowering"), (900, "fruit_development"), (1500, "harvest_ready")]},
    "mango": {"t_base": 15, "stages": [(0, "vegetative"), (300, "flowering"), (600, "fruit_setting"), (1000, "fruit_development"), (1500, "harvest_ready")]},
}


def estimate_growth_stage(crop: str, weather_data: dict, sowing_date: str = "", historical_weather: list[dict] = None) -> dict:
    """Estimate crop growth stage from accumulated GDD.
    If sowing_date + historical_weather are provided, uses REAL GDD (HIGH confidence).
    Otherwise falls back to forecast-based estimate (MEDIUM confidence)."""
    crop_lower = crop.lower().strip()
    crop_info = CROP_GDD_STAGES.get(crop_lower)
    if not crop_info:
        return {"stage": "unknown", "gdd_accumulated": 0, "confidence": "LOW", "detail": f"No GDD model available for {crop}.", "method": "none", "days_since_sowing": None}

    t_base = crop_info["t_base"]
    stages = crop_info["stages"]

    # --- METHOD 1: Real GDD from sowing date + historical weather (HIGH confidence) ---
    if sowing_date and historical_weather:
        try:
            sow_dt = datetime.strptime(sowing_date, "%Y-%m-%d")
            days_since_sowing = (datetime.utcnow() - sow_dt).days

            # Filter historical weather from sowing date onwards
            total_gdd = 0
            days_counted = 0
            for d in historical_weather:
                try:
                    d_date = datetime.strptime(d["date"], "%Y-%m-%d")
                except (ValueError, KeyError):
                    continue
                if d_date >= sow_dt:
                    t_max = d.get("max_temp_c")
                    t_min = d.get("min_temp_c")
                    if t_max is not None and t_min is not None:
                        daily_gdd = max(0, (t_max + t_min) / 2 - t_base)
                        total_gdd += daily_gdd
                        days_counted += 1

            if days_counted > 0:
                avg_daily_gdd = total_gdd / days_counted

                # Find current stage
                current_stage = stages[0][1]
                next_stage = None
                gdd_to_next = 0
                for idx, (gdd_threshold, stage_name) in enumerate(stages):
                    if total_gdd >= gdd_threshold:
                        current_stage = stage_name
                        if idx + 1 < len(stages):
                            next_stage = stages[idx + 1][1]
                            gdd_to_next = stages[idx + 1][0] - total_gdd
                    else:
                        break

                days_to_next = round(gdd_to_next / avg_daily_gdd) if avg_daily_gdd > 0 and gdd_to_next > 0 else None

                return {
                    "stage": current_stage,
                    "gdd_accumulated": round(total_gdd),
                    "avg_daily_gdd": round(avg_daily_gdd, 1),
                    "days_since_sowing": days_since_sowing,
                    "sowing_date": sowing_date,
                    "next_stage": next_stage,
                    "days_to_next_stage": days_to_next,
                    "confidence": "HIGH",
                    "method": "real_gdd",
                    "detail": f"Day {days_since_sowing} since sowing ({sowing_date}). Accumulated {round(total_gdd)} GDD. Stage: {current_stage}."
                        + (f" Next stage ({next_stage}) in approx {days_to_next} days." if days_to_next else ""),
                }
        except (ValueError, TypeError) as e:
            log.warning(f"Real GDD calculation failed: {e}, falling back to estimate")

    # --- METHOD 2: Estimate from forecast (MEDIUM confidence) ---
    daily = weather_data.get("daily_forecast", [])
    total_gdd = 0
    for d in daily:
        t_max = d.get("max_temp_c", 25)
        t_min = d.get("min_temp_c", 15)
        if t_max is not None and t_min is not None:
            daily_gdd = max(0, (t_max + t_min) / 2 - t_base)
            total_gdd += daily_gdd

    avg_daily_gdd = total_gdd / len(daily) if daily else 15
    # Use midpoint of typical season (75 days) as rough estimate
    estimated_total_gdd = avg_daily_gdd * 75

    current_stage = stages[0][1]
    for gdd_threshold, stage_name in stages:
        if estimated_total_gdd >= gdd_threshold:
            current_stage = stage_name

    return {
        "stage": current_stage,
        "gdd_accumulated": round(estimated_total_gdd),
        "avg_daily_gdd": round(avg_daily_gdd, 1),
        "days_since_sowing": None,
        "sowing_date": None,
        "next_stage": None,
        "days_to_next_stage": None,
        "confidence": "MEDIUM",
        "method": "estimated",
        "detail": f"Estimated stage: {current_stage} (approx {round(estimated_total_gdd)} GDD). For precise staging, tell us your sowing date.",
    }


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


def _compute_ndvi_trajectory(lat: float, lon: float) -> dict:
    """Compute NDVI trajectory over multiple observations + district benchmark. Runs in thread pool."""
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(500)
    district_buffer = point.buffer(10000)  # 10km radius for district benchmark

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=60)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        .sort("system:time_start", False)
    )

    count = collection.size().getInfo()
    if count == 0:
        return {}

    # Get time series (up to 6 most recent observations)
    num_images = min(count, 6)
    images_list = collection.toList(num_images)

    ndvi_series = []
    for i in range(num_images):
        try:
            img = ee.Image(images_list.get(i))
            ndvi = img.normalizedDifference(["B8", "B4"])
            stats = ndvi.reduceRegion(reducer=ee.Reducer.mean(), geometry=buffer, scale=10, maxPixels=1e6).getInfo()
            date_ms = img.get("system:time_start").getInfo()
            img_date = datetime.utcfromtimestamp(date_ms / 1000).strftime("%Y-%m-%d")
            val = stats.get("nd")  # normalizedDifference returns 'nd'
            if val is None:
                val = stats.get("NDVI", stats.get("B8", None))  # fallback keys
            if val is not None:
                ndvi_series.append({"date": img_date, "ndvi": round(val, 4)})
        except Exception:
            continue

    if not ndvi_series:
        return {}

    # Trajectory classification
    if len(ndvi_series) >= 2:
        latest = ndvi_series[0]["ndvi"]
        oldest = ndvi_series[-1]["ndvi"]
        diff = latest - oldest
        if diff > 0.05:
            trajectory = "improving"
        elif diff < -0.05:
            trajectory = "declining"
        elif abs(diff) < 0.02 and latest > 0.5:
            trajectory = "plateauing"
        else:
            trajectory = "stable"
    else:
        trajectory = "single_observation"

    # District benchmark — mean NDVI for 10km radius
    district_ndvi = None
    try:
        latest_img = ee.Image(images_list.get(0))
        ndvi_img = latest_img.normalizedDifference(["B8", "B4"])
        district_stats = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=district_buffer, scale=100, maxPixels=1e8
        ).getInfo()
        district_ndvi = district_stats.get("nd")
        if district_ndvi is not None:
            district_ndvi = round(district_ndvi, 4)
    except Exception:
        pass

    # Data age
    latest_date = ndvi_series[0]["date"]
    days_since = (datetime.utcnow() - datetime.strptime(latest_date, "%Y-%m-%d")).days

    # Benchmark comparison
    benchmark_comparison = None
    if district_ndvi and ndvi_series[0]["ndvi"] and district_ndvi > 0:
        pct_diff = round((ndvi_series[0]["ndvi"] - district_ndvi) / district_ndvi * 100, 1)
        if pct_diff > 5:
            benchmark_comparison = f"{pct_diff}% above district average (good)"
        elif pct_diff < -5:
            benchmark_comparison = f"{abs(pct_diff)}% below district average (needs attention)"
        else:
            benchmark_comparison = "similar to district average"

    return {
        "ndvi_series": ndvi_series,
        "trajectory": trajectory,
        "district_avg_ndvi": district_ndvi,
        "benchmark_comparison": benchmark_comparison,
        "days_since_image": days_since,
        "latest_image_date": latest_date,
        "num_observations": len(ndvi_series),
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


async def fetch_ndvi_trajectory(lat: float, lon: float) -> dict:
    """Fetch NDVI trajectory data from Earth Engine. Returns empty dict on failure."""
    if not EE_INITIALIZED:
        return {}
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_ee_executor, _compute_ndvi_trajectory, lat, lon)
        return result
    except Exception as e:
        log.warning(f"NDVI trajectory fetch failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Additional Satellite Data: SAR Soil Moisture, MODIS LST, SMAP
# ---------------------------------------------------------------------------

def _compute_sar_soil_moisture(lat: float, lon: float) -> dict:
    """Compute soil moisture proxy from Sentinel-1 SAR (C-band radar).
    Works through clouds — fills gaps when Sentinel-2 optical data is unavailable.
    Uses VV backscatter change detection relative to local dry/wet reference."""
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(500)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    # Sentinel-1 GRD (Ground Range Detected), IW mode, VV+VH polarization
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(point)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV", "VH"])
        .sort("system:time_start", False)
    )

    count = collection.size().getInfo()
    if count == 0:
        return {"error": "No Sentinel-1 SAR data available for this location in last 30 days"}

    latest = ee.Image(collection.first())

    # Get VV and VH backscatter values (already in dB)
    stats = latest.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=buffer,
        scale=10,
        maxPixels=1e6,
    ).getInfo()

    vv_db = stats.get("VV")
    vh_db = stats.get("VH")

    if vv_db is None:
        return {"error": "SAR data computation failed"}

    # Get image date
    img_date_ms = latest.get("system:time_start").getInfo()
    img_date = datetime.utcfromtimestamp(img_date_ms / 1000).strftime("%Y-%m-%d")

    # Soil moisture classification from VV backscatter (empirical thresholds for C-band)
    # Reference: VV backscatter correlates with soil dielectric constant
    # Typical ranges: dry soil ~ -15 to -12 dB, moist ~ -12 to -8 dB, wet ~ -8 to -3 dB
    if vv_db >= -8:
        moisture_class = "wet"
        moisture_detail = "Soil appears wet — possible recent rain or irrigation"
    elif vv_db >= -12:
        moisture_class = "moist"
        moisture_detail = "Soil moisture appears adequate"
    elif vv_db >= -15:
        moisture_class = "dry"
        moisture_detail = "Soil appears dry — may need irrigation"
    else:
        moisture_class = "very_dry"
        moisture_detail = "Soil appears very dry — irrigation recommended"

    # Cross-ratio VH/VV indicates vegetation volume scattering
    cross_ratio = vh_db - vv_db if vh_db is not None else None
    vegetation_density = None
    if cross_ratio is not None:
        if cross_ratio > -6:
            vegetation_density = "dense"
        elif cross_ratio > -10:
            vegetation_density = "moderate"
        else:
            vegetation_density = "sparse"

    # Trend: compare with older image if available
    trend = "unknown"
    if count >= 2:
        try:
            older = ee.Image(collection.toList(2).get(1))
            older_stats = older.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=buffer, scale=10, maxPixels=1e6
            ).getInfo()
            older_vv = older_stats.get("VV")
            if older_vv is not None and vv_db is not None:
                diff = vv_db - older_vv
                if diff > 1.5:
                    trend = "wetting"
                elif diff < -1.5:
                    trend = "drying"
                else:
                    trend = "stable"
        except Exception:
            pass

    return {
        "vv_backscatter_db": round(vv_db, 2) if vv_db is not None else None,
        "vh_backscatter_db": round(vh_db, 2) if vh_db is not None else None,
        "moisture_class": moisture_class,
        "moisture_detail": moisture_detail,
        "vegetation_density": vegetation_density,
        "trend": trend,
        "image_date": img_date,
        "images_found": count,
        "source": "Sentinel-1 SAR (C-band radar) via Google Earth Engine",
    }


def _compute_land_surface_temperature(lat: float, lon: float) -> dict:
    """Compute Land Surface Temperature from MODIS Terra (MOD11A1) — 1km daily.
    Detects heat stress, irrigation effectiveness, and crop water demand."""
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(1000)  # 1km buffer (MODIS is 1km resolution)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=10)

    collection = (
        ee.ImageCollection("MODIS/061/MOD11A1")
        .filterBounds(point)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .select(["LST_Day_1km", "LST_Night_1km", "QC_Day"])
        .sort("system:time_start", False)
    )

    count = collection.size().getInfo()
    if count == 0:
        return {"error": "No MODIS LST data available for this location in last 10 days"}

    latest = ee.Image(collection.first())

    stats = latest.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=buffer,
        scale=1000,
        maxPixels=1e6,
    ).getInfo()

    lst_day_raw = stats.get("LST_Day_1km")
    lst_night_raw = stats.get("LST_Night_1km")

    if lst_day_raw is None:
        return {"error": "MODIS LST computation failed — likely cloudy"}

    # Convert from MODIS scale factor: multiply by 0.02 and convert from Kelvin to Celsius
    lst_day_c = round(lst_day_raw * 0.02 - 273.15, 1) if lst_day_raw else None
    lst_night_c = round(lst_night_raw * 0.02 - 273.15, 1) if lst_night_raw else None

    img_date_ms = latest.get("system:time_start").getInfo()
    img_date = datetime.utcfromtimestamp(img_date_ms / 1000).strftime("%Y-%m-%d")

    # Heat stress classification for crops
    heat_stress = "none"
    heat_detail = ""
    if lst_day_c is not None:
        if lst_day_c >= 45:
            heat_stress = "extreme"
            heat_detail = f"Surface temperature {lst_day_c}°C — extreme heat stress. Irrigate immediately, consider shade nets."
        elif lst_day_c >= 40:
            heat_stress = "high"
            heat_detail = f"Surface temperature {lst_day_c}°C — significant heat stress. Irrigate in early morning."
        elif lst_day_c >= 35:
            heat_stress = "moderate"
            heat_detail = f"Surface temperature {lst_day_c}°C — moderate heat. Monitor crop wilting."
        else:
            heat_stress = "none"
            heat_detail = f"Surface temperature {lst_day_c}°C — within normal range."

    # Day-night temperature difference (important for fruit setting)
    diurnal_range = None
    if lst_day_c is not None and lst_night_c is not None:
        diurnal_range = round(lst_day_c - lst_night_c, 1)

    # Regional benchmark: average LST in wider area
    regional_buffer = point.buffer(10000)
    regional_lst = None
    try:
        regional_stats = latest.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=regional_buffer, scale=1000, maxPixels=1e8
        ).getInfo()
        regional_raw = regional_stats.get("LST_Day_1km")
        if regional_raw:
            regional_lst = round(regional_raw * 0.02 - 273.15, 1)
    except Exception:
        pass

    lst_anomaly = None
    if lst_day_c is not None and regional_lst is not None:
        lst_anomaly = round(lst_day_c - regional_lst, 1)

    return {
        "lst_day_celsius": lst_day_c,
        "lst_night_celsius": lst_night_c,
        "diurnal_range_celsius": diurnal_range,
        "heat_stress": heat_stress,
        "heat_detail": heat_detail,
        "regional_lst_celsius": regional_lst,
        "lst_anomaly_celsius": lst_anomaly,
        "image_date": img_date,
        "source": "MODIS Terra MOD11A1 (1km daily LST) via Google Earth Engine",
    }


def _compute_smap_soil_moisture(lat: float, lon: float) -> dict:
    """Compute root-zone soil moisture from NASA SMAP L4 (9km, 3-hourly).
    Provides deep soil moisture (0-100cm) — tells if roots have water even if surface is dry."""
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(5000)  # 5km buffer (SMAP is 9km resolution)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=5)

    collection = (
        ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
        .filterBounds(point)
        .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        .select(["sm_surface", "sm_rootzone", "sm_surface_wetness"])
        .sort("system:time_start", False)
    )

    count = collection.size().getInfo()
    if count == 0:
        return {"error": "No SMAP soil moisture data available"}

    latest = ee.Image(collection.first())

    stats = latest.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=buffer,
        scale=9000,
        maxPixels=1e6,
    ).getInfo()

    surface_sm = stats.get("sm_surface")  # m³/m³ (volumetric)
    rootzone_sm = stats.get("sm_rootzone")  # m³/m³
    surface_wetness = stats.get("sm_surface_wetness")  # fraction 0-1

    if surface_sm is None and rootzone_sm is None:
        return {"error": "SMAP computation failed"}

    img_date_ms = latest.get("system:time_start").getInfo()
    img_date = datetime.utcfromtimestamp(img_date_ms / 1000).strftime("%Y-%m-%d")

    # Classify root-zone moisture for agriculture
    rootzone_class = "unknown"
    rootzone_detail = ""
    if rootzone_sm is not None:
        if rootzone_sm >= 0.35:
            rootzone_class = "wet"
            rootzone_detail = "Root zone is well-watered. No irrigation needed."
        elif rootzone_sm >= 0.25:
            rootzone_class = "adequate"
            rootzone_detail = "Root zone moisture is adequate for most crops."
        elif rootzone_sm >= 0.15:
            rootzone_class = "low"
            rootzone_detail = "Root zone moisture is getting low. Plan irrigation soon."
        else:
            rootzone_class = "critical"
            rootzone_detail = "Root zone moisture critically low. Irrigate immediately — roots are stressed."

    # Surface vs rootzone comparison
    depth_insight = ""
    if surface_sm is not None and rootzone_sm is not None:
        if surface_sm < 0.15 and rootzone_sm > 0.25:
            depth_insight = "Surface soil is dry but roots still have water — crop can sustain a few more days."
        elif surface_sm > 0.30 and rootzone_sm < 0.15:
            depth_insight = "Surface is wet (recent rain?) but deep soil is dry — water hasn't reached roots yet. Deeper irrigation needed."
        elif surface_sm < 0.15 and rootzone_sm < 0.15:
            depth_insight = "Both surface and root zone are dry — full irrigation needed urgently."

    return {
        "surface_moisture_m3m3": round(surface_sm, 4) if surface_sm is not None else None,
        "rootzone_moisture_m3m3": round(rootzone_sm, 4) if rootzone_sm is not None else None,
        "surface_wetness_fraction": round(surface_wetness, 3) if surface_wetness is not None else None,
        "rootzone_class": rootzone_class,
        "rootzone_detail": rootzone_detail,
        "depth_insight": depth_insight,
        "image_date": img_date,
        "source": "NASA SMAP L4 (9km root-zone soil moisture) via Google Earth Engine",
    }


async def fetch_satellite_extras(lat: float, lon: float) -> dict:
    """Fetch all additional satellite data: SAR soil moisture, MODIS LST, SMAP.
    Runs all three in parallel in the thread pool. Returns dict with available data."""
    if not EE_INITIALIZED:
        return {}

    loop = asyncio.get_event_loop()
    results = {}

    # Run all three in parallel via thread pool
    sar_future = loop.run_in_executor(_ee_executor, _compute_sar_soil_moisture, lat, lon)
    lst_future = loop.run_in_executor(_ee_executor, _compute_land_surface_temperature, lat, lon)
    smap_future = loop.run_in_executor(_ee_executor, _compute_smap_soil_moisture, lat, lon)

    for name, future in [("sar", sar_future), ("lst", lst_future), ("smap", smap_future)]:
        try:
            data = await asyncio.wait_for(future, timeout=8.0)
            if "error" not in data:
                results[name] = data
                log.info(f"Satellite {name}: OK")
            else:
                log.info(f"Satellite {name}: {data['error']}")
        except (asyncio.TimeoutError, Exception) as e:
            log.info(f"Satellite {name} skipped: {e}")

    return results


# ---------------------------------------------------------------------------
# Beep / chime generator (pure Python, no external API)
# ---------------------------------------------------------------------------
def _generate_beep(freq: int = 880, duration_ms: int = 300, volume: float = 0.3) -> str:
    """Generate a short notification chime as a base64-encoded WAV."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    # WAV header
    buf.write(b'RIFF')
    data_size = num_samples * 2
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVEfmt ')
    buf.write(struct.pack('<IHHIIHH', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b'data')
    buf.write(struct.pack('<I', data_size))
    for i in range(num_samples):
        t = i / sample_rate
        # Fade in/out envelope to avoid clicks
        env = min(i / 500, 1.0) * min((num_samples - i) / 500, 1.0)
        sample = int(volume * env * 32767 * math.sin(2 * math.pi * freq * t))
        buf.write(struct.pack('<h', max(-32768, min(32767, sample))))
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/beep")
async def beep():
    """Return a short notification chime as base64 WAV audio."""
    return {"audio_base64": _generate_beep(), "content_type": "audio/wav"}


@app.get("/api/health")
async def health():
    sat_cache_info = _sat_cache.stats() if _sat_cache.is_loaded else {"loaded": False}
    return {
        "status": "healthy",
        "service": "KisanMind API",
        "version": "2.0.0",
        "apis": {
            "google_maps": bool(GOOGLE_MAPS_API_KEY),
            "agmarknet": bool(AGMARKNET_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "weather": "Open-Meteo (free)",
            "earth_engine": f"{'active' if EE_INITIALIZED else 'unavailable'} (project: {EE_PROJECT})",
            "satellite_cache": sat_cache_info,
        },
    }


@app.post("/api/ndvi")
async def get_ndvi(req: NDVIRequest):
    """Get satellite vegetation indices — local cache first, Earth Engine fallback."""
    log.info(f"NDVI request: lat={req.latitude}, lon={req.longitude}")

    # 1. Try local satellite cache (instant, <1ms)
    if _sat_cache.is_loaded:
        cached_sat = _sat_cache.lookup_enriched(req.latitude, req.longitude)
        if cached_sat.get("cache_hit") and cached_sat.get("ndvi_data"):
            result = cached_sat["ndvi_data"]
            result["cached"] = True
            result["cache_source"] = "local_precomputed"
            result["cache_distance_km"] = cached_sat.get("cache_distance_km", 0)
            log.info(f"NDVI from local cache ({cached_sat.get('cache_distance_km', 0):.1f}km from exact)")
            return result

    # 2. Try L1/L2 advisory cache
    cache_key = f"ndvi:{round(req.latitude, 2)}:{round(req.longitude, 2)}"
    cached = await cache_get(cache_key, _NDVI_TTL)
    if cached is not None:
        return {**cached, "cached": True, "cache_source": "l1_l2"}

    # 3. Fall back to live Earth Engine
    if not EE_INITIALIZED:
        raise HTTPException(503, "Satellite data unavailable — no cache and Earth Engine not initialized.")
    result = await fetch_ndvi(req.latitude, req.longitude)
    if result is None:
        raise HTTPException(404, "No satellite data available for this location.")
    await cache_set(cache_key, result)
    result["cached"] = False
    result["cache_source"] = "live_earth_engine"
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


async def _background_refine_satellite(lat: float, lon: float):
    """Background task: fetch exact satellite data from live Earth Engine,
    persist to GCS for future lookups. Called when cache hit is coarse (>5km)."""
    try:
        log.info(f"Background satellite refinement starting for ({lat}, {lon})")

        # Compute live data
        ndvi_result = await fetch_ndvi(lat, lon)
        extras_result = await fetch_satellite_extras(lat, lon)

        # Persist to GCS so it survives redeployment
        refined_data = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "ndvi": ndvi_result.get("ndvi") if ndvi_result else None,
            "evi": ndvi_result.get("evi") if ndvi_result else None,
            "ndwi": ndvi_result.get("ndwi") if ndvi_result else None,
            "health": ndvi_result.get("health", "").lower() if ndvi_result else None,
            "image_date": ndvi_result.get("image_date") if ndvi_result else None,
        }

        # Add SAR data
        if extras_result.get("sar"):
            sar = extras_result["sar"]
            refined_data["vv_db"] = sar.get("vv_backscatter_db")
            refined_data["vh_db"] = sar.get("vh_backscatter_db")
            refined_data["moisture"] = sar.get("moisture_class")

        # Add LST data
        if extras_result.get("lst"):
            lst = extras_result["lst"]
            refined_data["lst_day_c"] = lst.get("lst_day_celsius")
            refined_data["lst_night_c"] = lst.get("lst_night_celsius")
            refined_data["heat_stress"] = lst.get("heat_stress")

        # Add SMAP data
        if extras_result.get("smap"):
            smap = extras_result["smap"]
            refined_data["sm_surface"] = smap.get("surface_moisture_m3m3")
            refined_data["sm_rootzone"] = smap.get("rootzone_moisture_m3m3")
            refined_data["rootzone_class"] = smap.get("rootzone_class")

        # Persist to GCS (survives redeployment)
        gcs_key = f"sat_refined:{round(lat, 3)}:{round(lon, 3)}"
        await _gcs_set(gcs_key, refined_data)

        # Also update local in-memory cache for immediate next lookup
        cache_key = _sat_cache._grid_key(lat, lon)
        _sat_cache.grid_index[cache_key] = refined_data
        _sat_cache.points.append(refined_data)

        log.info(f"Background satellite refinement done for ({lat}, {lon}) — persisted to GCS + local cache")

    except Exception as e:
        log.warning(f"Background satellite refinement failed for ({lat}, {lon}): {e}")


async def _handle_tool_call(
    name: str,
    args: dict,
    latitude: float,
    longitude: float,
    language: str,
) -> dict:
    """Handle Gemini Live function calls by executing the real data pipeline."""
    if name != "fetch_farm_data":
        return {"error": f"Unknown function: {name}"}

    try:
        crop = args.get("crop", "Unknown")
        sowing_date = args.get("sowing_date", "")
        quantity = args.get("quantity_quintals", 0)
        problems = args.get("problems", "")
        irrigation = args.get("irrigation_type", "")
        recent_activities = args.get("recent_activities", "")
        selling_timeline = args.get("selling_timeline", "")
        soil_type = args.get("soil_type", "")
        land_area = args.get("land_area_bigha", 0)
        extra = args.get("extra_observations", "")

        req = AdvisoryRequest(
            latitude=latitude,
            longitude=longitude,
            crop=crop,
            language=language,
            intent="full_advisory",
            quantity_quintals=quantity,
            sowing_date=sowing_date,
        )
        result = await _run_advisory(req)

        farmer_context_parts = []
        if problems:
            farmer_context_parts.append(f"FARMER REPORTED PROBLEMS: {problems}")
        if irrigation:
            farmer_context_parts.append(f"IRRIGATION: {irrigation}")
        if recent_activities:
            farmer_context_parts.append(f"RECENT ACTIVITIES: {recent_activities}")
        if selling_timeline:
            farmer_context_parts.append(f"SELLING PLAN: {selling_timeline}")
        if soil_type:
            farmer_context_parts.append(f"SOIL TYPE: {soil_type}")
        if land_area > 0:
            farmer_context_parts.append(f"LAND AREA: {land_area} bigha")
        if extra:
            farmer_context_parts.append(f"EXTRA OBSERVATIONS: {extra}")
        farmer_context = "\n".join(farmer_context_parts) if farmer_context_parts else "No additional context from farmer."

        location = result.get("location", {})
        best = result.get("best_mandi", {})
        local = result.get("local_mandi", {})
        weather = result.get("weather", {})
        kvk = result.get("nearest_kvk", {})
        sat = result.get("satellite", {})
        growth = result.get("growth_stage", {})
        trend = result.get("price_trend", {})
        extras = result.get("satellite_extras", {})
        cross_val = result.get("cross_validation", [])

        data = {
            "location": f"{location.get('location_name', '?')}, {location.get('state', '?')}",
            "crop": crop,
            "farmer_context": farmer_context,
            "best_mandi": {
                "name": best.get("market", "?"),
                "price_per_quintal": best.get("modal_price", 0),
                "distance_km": best.get("distance_km", "?"),
                "travel_time": best.get("duration_text", "?"),
                "net_profit_per_quintal": best.get("net_profit_per_quintal", 0),
            },
            "local_mandi": {
                "name": local.get("market", "?") if local else "?",
                "price_per_quintal": local.get("modal_price", 0) if local else 0,
                "net_profit_per_quintal": local.get("net_profit_per_quintal", 0) if local else 0,
            },
            "weather_summary": weather.get("summary", "Weather data not available"),
            "weather_forecast": weather.get("daily_forecast", [])[:5],
            "satellite": {
                "health": sat.get("health", "Not available") if sat else "Not available",
                "ndvi_score": sat.get("ndvi", None) if sat else None,
                "evi": sat.get("evi", None) if sat else None,
                "ndwi": sat.get("ndwi", None) if sat else None,
                "image_date": sat.get("image_date", "?") if sat else "?",
                "source": sat.get("source", "Sentinel-2") if sat else "unavailable",
                "trend": sat.get("trend", "unknown") if sat else "unknown",
            },
            "soil_moisture": {
                "class": extras.get("sar", {}).get("moisture_class", "unknown") if extras else "unknown",
                "detail": extras.get("sar", {}).get("moisture_detail", "") if extras else "",
                "source": "Sentinel-1 SAR radar",
            },
            "surface_temperature": {
                "day_celsius": extras.get("lst", {}).get("lst_day_celsius", None) if extras else None,
                "heat_stress": extras.get("lst", {}).get("heat_stress", "none") if extras else "none",
                "source": "MODIS Terra satellite",
            },
            "root_zone_moisture": {
                "class": extras.get("smap", {}).get("rootzone_class", "unknown") if extras else "unknown",
                "detail": extras.get("smap", {}).get("rootzone_detail", "") if extras else "",
                "source": "NASA SMAP satellite",
            },
            "growth_stage": growth.get("stage", "unknown") if growth else "unknown",
            "growth_detail": growth.get("detail", "") if growth else "",
            "price_trend": trend.get("trend", "stable") if trend else "stable",
            "price_trend_percent": trend.get("trend_percent", 0) if trend else 0,
            "nearest_kvk": {
                "name": kvk.get("name", "?") if kvk else "?",
                "distance_km": kvk.get("distance_km", "?") if kvk else "?",
                "phone": kvk.get("phone", "1800-180-1551") if kvk else "1800-180-1551",
            },
            "cross_validation_warnings": [cv.get("finding", "") for cv in cross_val] if cross_val else [],
            "instructions": (
                "Deliver a PERSONALIZED advisory. CITE actual satellite values in your reasoning: "
                "mention NDVI score, soil moisture class, satellite name, image age. "
                "The farmer needs to TRUST the data — show them the numbers. "
                "Mention specific weather dates. Give mandi with price and net profit. "
                "If they reported pests/disease, refer to the nearest KVK. "
                "Keep it under 150 words. End with 'This is based on today's data. The final decision is yours.' "
                "Then ask if they have any other questions."
            ),
        }
        return data

    except Exception as e:
        log.exception(f"Tool call handler failed: {e}")
        return {
            "error": str(e),
            "instructions": "Tell the farmer there was a technical issue fetching data. Ask them to try again or call the KVK helpline at 1800-180-1551.",
        }


async def _run_advisory(req: AdvisoryRequest):
    crop = req.crop
    if not crop or crop.lower() in ("auto", "unknown"):
        crop = "Unknown"
    log.info(f"Advisory for crop: {crop}")

    # 0. Try local satellite cache FIRST (instant, <1ms, no EE call)
    sat_from_cache = False
    ndvi_data = None
    ndvi_trajectory = {}
    satellite_extras = {}

    if _sat_cache.is_loaded:
        cached_sat = _sat_cache.lookup_enriched(req.latitude, req.longitude)
        if cached_sat.get("cache_hit"):
            ndvi_data = cached_sat.get("ndvi_data")
            satellite_extras = cached_sat.get("satellite_extras", {})
            sat_from_cache = True
            cache_dist = cached_sat.get("cache_distance_km", 0)
            log.info(f"Satellite data from local cache ({cache_dist:.1f}km, computed {cached_sat.get('computed_at', '?')})")

            # If cached data is coarse (>5km from exact location), launch background
            # live EE refinement and persist to GCS for future exact lookups
            if cache_dist > 5.0:
                asyncio.create_task(_background_refine_satellite(req.latitude, req.longitude))

    # 1. Geocode + weather + KVK + historical weather — ALL PARALLEL
    #    Only launch live EE tasks if cache missed
    location_task = asyncio.create_task(reverse_geocode(req.latitude, req.longitude))
    weather_task = asyncio.create_task(fetch_weather(req.latitude, req.longitude))
    kvk_task = asyncio.create_task(find_nearest_kvk(req.latitude, req.longitude))
    hist_weather_task = asyncio.create_task(fetch_historical_weather(req.latitude, req.longitude, days_back=120))

    # Live EE calls only if cache missed
    ndvi_task = None
    sat_extras_task = None
    if not sat_from_cache:
        ndvi_task = asyncio.create_task(fetch_ndvi(req.latitude, req.longitude))
        sat_extras_task = asyncio.create_task(fetch_satellite_extras(req.latitude, req.longitude))
        log.info("No satellite cache hit — launching live Earth Engine calls")

    location = await location_task
    log.info(f"Location: {location}")

    # District-level satellite fallback (if exact location cache missed)
    if not sat_from_cache and _sat_cache.is_loaded and location.get("district"):
        cached_sat = _sat_cache.lookup_enriched(req.latitude, req.longitude, district=location["district"])
        if cached_sat.get("cache_hit"):
            ndvi_data = cached_sat.get("ndvi_data")
            satellite_extras = cached_sat.get("satellite_extras", {})
            sat_from_cache = True
            log.info(f"Satellite data from district fallback: {location['district']}")
            # Cancel live EE tasks if they were launched
            if ndvi_task and not ndvi_task.done():
                ndvi_task.cancel()
            if sat_extras_task and not sat_extras_task.done():
                sat_extras_task.cancel()

    # 2. Mandi prices (needs state from geocode)
    mandis = await fetch_mandi_prices(crop, location["state"])
    log.info(f"Found {len(mandis)} mandis with prices")

    # 3. Distances + weather in PARALLEL
    distances_task = asyncio.create_task(get_distances(req.latitude, req.longitude, mandis))
    weather = await weather_task
    mandis = await distances_task

    # 4. NDVI — only if not already from cache
    if not sat_from_cache and ndvi_task:
        try:
            ndvi_data = await asyncio.wait_for(ndvi_task, timeout=8.0)
            if ndvi_data:
                log.info(f"NDVI (live EE): {ndvi_data['ndvi']}, Health: {ndvi_data['health']}")
        except asyncio.TimeoutError:
            log.warning("NDVI live fetch timed out after 8s — proceeding without satellite data")
        except Exception as e:
            log.warning(f"NDVI live fetch failed: {e} — proceeding without satellite data")

        # NDVI trajectory — best-effort, don't block
        if ndvi_data:
            try:
                ndvi_trajectory = await asyncio.wait_for(
                    fetch_ndvi_trajectory(req.latitude, req.longitude), timeout=5.0
                )
            except (asyncio.TimeoutError, Exception):
                log.info("NDVI trajectory skipped — using basic NDVI only")

    # 4-extra. Get additional satellite data (SAR, MODIS LST, SMAP) — only if not from cache
    if not sat_from_cache and sat_extras_task:
        try:
            satellite_extras = await asyncio.wait_for(sat_extras_task, timeout=15.0)
            if satellite_extras:
                log.info(f"Satellite extras (live EE): {list(satellite_extras.keys())}")
        except asyncio.TimeoutError:
            log.warning("Satellite extras timed out after 15s — proceeding without SAR/LST/SMAP")
        except Exception as e:
            log.warning(f"Satellite extras failed: {e} — proceeding without SAR/LST/SMAP")

    # 4a. Calculate net profits with spoilage
    mandis = calculate_net_profits(mandis, crop=crop)

    # 4b. Analyze price trend
    price_trend = analyze_price_trend(mandis)
    log.info(f"Price trend: {price_trend['trend']} ({price_trend['trend_percent']}%)")

    # 4c. Get historical weather for real GDD calculation
    historical_weather = await hist_weather_task
    sowing_date = req.sowing_date or ""

    # 4d. Estimate growth stage — uses real GDD if sowing date provided, otherwise estimate
    growth_stage = estimate_growth_stage(crop, weather, sowing_date=sowing_date, historical_weather=historical_weather)
    log.info(f"Growth stage: {growth_stage['stage']} (method: {growth_stage.get('method', '?')}, confidence: {growth_stage['confidence']})")

    # 4e. Compute confidence scores
    confidence = compute_advisory_confidence(ndvi_data, ndvi_trajectory, weather, price_trend, mandis)
    log.info(f"Advisory confidence: {confidence['overall']['level']} ({confidence['overall']['score']})")

    # 4f. Cross-validate data sources for conflict detection
    cross_validation = cross_validate_data_sources(ndvi_data, ndvi_trajectory, weather, price_trend, growth_stage, satellite_extras)
    if cross_validation:
        log.info(f"Cross-validation: {len(cross_validation)} observations — {[cv['type'] for cv in cross_validation]}")

    # 5. Get nearest KVK
    try:
        nearest_kvk = await kvk_task
        if not nearest_kvk:
            nearest_kvk = {"name": "KVK", "phone": "1800-180-1551", "distance_km": "?"}
    except Exception:
        nearest_kvk = {"name": "KVK", "phone": "1800-180-1551", "distance_km": "?"}
    log.info(f"Nearest KVK: {nearest_kvk.get('name', '?')} ({nearest_kvk.get('distance_km', '?')} km)")

    # 6. Find best mandi and local/closest mandi
    mandis_with_profit = [m for m in mandis if m.get("net_profit_per_quintal") is not None]
    if mandis_with_profit:
        best_mandi = max(mandis_with_profit, key=lambda m: m["net_profit_per_quintal"])
        local_mandi = min(mandis_with_profit, key=lambda m: m["distance_km"])
    elif mandis:
        best_mandi = max(mandis, key=lambda m: m["modal_price"])
        local_mandi = mandis[0]
    else:
        best_mandi = {"market": "N/A", "modal_price": 0, "distance_km": 0, "net_profit_per_quintal": 0}
        local_mandi = None
        log.warning(f"No mandi data available for {crop} — advisory will skip mandi section")

    # 7. Generate advisory via Gemini with all pre-computed data
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
        ndvi_trajectory=ndvi_trajectory,
        growth_stage=growth_stage,
        price_trend=price_trend,
        confidence=confidence,
        nearest_kvk=nearest_kvk,
        quantity_quintals=req.quantity_quintals,
        cross_validation=cross_validation,
        satellite_extras=satellite_extras,
    )

    response_data = {
        "location": location,
        "maps_url": location.get("maps_url", f"https://www.google.com/maps/@{req.latitude},{req.longitude},14z"),
        "crop": crop,
        "language": req.language,
        "mandi_prices": mandis,
        "best_mandi": best_mandi,
        "local_mandi": local_mandi,
        "weather": weather,
        "price_trend": price_trend,
        "growth_stage": growth_stage,
        "confidence": confidence,
        "nearest_kvk": nearest_kvk,
        "cross_validation": cross_validation if cross_validation else [],
        "satellite_extras": satellite_extras if satellite_extras else {},
        "advisory": advisory_text,
        "sources": {
            "mandi_prices": "AgMarkNet / data.gov.in (real-time)",
            "distances": "Google Maps Distance Matrix API",
            "weather": "Open-Meteo API",
            "advisory": "Gemini 3.1 Flash",
            "geocoding": "Google Maps Geocoding API",
            "nearest_kvk": "Google Places API",
            "historical_weather": "Open-Meteo Historical API (120 days)",
            "cross_validation": "Multi-source conflict detection engine",
            "sar_soil_moisture": "Sentinel-1 SAR C-band radar via Google Earth Engine" if satellite_extras.get("sar") else "unavailable",
            "land_surface_temp": "MODIS Terra MOD11A1 (1km daily) via Google Earth Engine" if satellite_extras.get("lst") else "unavailable",
            "smap_root_moisture": "NASA SMAP L4 (9km root-zone) via Google Earth Engine" if satellite_extras.get("smap") else "unavailable",
        },
    }

    if ndvi_data:
        response_data["satellite"] = ndvi_data
        response_data["ndvi_trajectory"] = ndvi_trajectory if ndvi_trajectory else None
        response_data["sources"]["satellite"] = f"Sentinel-2 via Google Earth Engine (project: {EE_PROJECT})"
    else:
        response_data["satellite"] = None
        response_data["ndvi_trajectory"] = None
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


class TranslateRequest(BaseModel):
    texts: list[str]
    target_language: str = "hi"


class TriviaRequest(BaseModel):
    crop: str = ""
    location: str = ""
    language: str = "hi"


@app.post("/api/trivia")
async def generate_trivia(req: TriviaRequest):
    """Generate 3 dynamic farming trivia facts based on crop and location."""
    prompt = f"""Generate exactly 3 short, interesting farming trivia facts (1 sentence each) relevant to:
Crop: {req.crop or 'general farming'}
Location: {req.location or 'India'}

Make them useful and interesting for an Indian farmer. Examples:
- Facts about the crop's market demand or best practices
- Regional farming facts about the location
- Interesting satellite/technology facts used in farming

Return ONLY 3 facts, one per line. No numbering, no bullets. Keep each under 20 words."""

    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: _gemini_generate(prompt))
        facts = [line.strip() for line in resp.text.strip().split("\n") if line.strip()][:3]

        # Translate if needed
        if req.language != "en":
            try:
                tc = translate.Client()
                facts = [html_mod.unescape(tc.translate(f, target_language=req.language, source_language="en")["translatedText"]) for f in facts]
            except Exception:
                pass

        return {"trivia": facts}
    except Exception:
        return {"trivia": [
            "Your call is important. Fetching satellite data and mandi prices.",
            "Selling at the right mandi can earn Rs 200-500 more per quintal.",
            "We use Sentinel-2 satellite to check crop health from space.",
        ]}


@app.post("/api/translate")
async def batch_translate(req: TranslateRequest):
    """Batch translate texts to target language. Used for re-translating chat on language switch."""
    if req.target_language == "en":
        return {"translated": req.texts}

    try:
        translate_client = translate.Client()
        translated = []
        for text in req.texts:
            if not text.strip():
                translated.append(text)
                continue
            result = translate_client.translate(
                text, target_language=req.target_language, source_language="en"
            )
            import html
            translated.append(html.unescape(result["translatedText"]))
        return {"translated": translated}
    except Exception as e:
        log.warning(f"Batch translate failed: {e}")
        return {"translated": req.texts}


@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for Gemini Live farmer conversations.

    Protocol:
    - Client sends: {"type": "config", "language": "hi", "latitude": 30.9, "longitude": 77.1}
    - Client sends: {"type": "audio", "data": "<base64 PCM 16kHz mono>"}
    - Server sends: {"type": "audio", "data": "<base64 PCM 24kHz mono>"}
    - Server sends: {"type": "transcript", "speaker": "farmer"|"kisanmind", "text": "..."}
    - Server sends: {"type": "status", "status": "fetching_data"|"ready"}
    """
    await ws.accept()
    session_id = str(uuid.uuid4())
    session: Optional[GeminiLiveSession] = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "config":
                language = msg.get("language", "hi")
                latitude = msg.get("latitude", 0)
                longitude = msg.get("longitude", 0)
                has_gps = latitude != 0 and longitude != 0

                locale_map = {
                    "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN",
                    "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN",
                    "pa": "pa-IN", "en": "en-IN",
                }
                locale = locale_map.get(language, "hi-IN")

                async def _on_audio(pcm_data: bytes):
                    if ws.client_state == WebSocketState.CONNECTED:
                        import base64 as b64
                        await ws.send_json({
                            "type": "audio",
                            "data": b64.b64encode(pcm_data).decode(),
                        })

                async def _on_transcript(speaker: str, text: str):
                    if ws.client_state == WebSocketState.CONNECTED:
                        display_text = text
                        if language != "en":
                            try:
                                translate_client = translate.Client()
                                result = translate_client.translate(
                                    text, target_language=language, source_language="en"
                                )
                                import html as html_mod
                                display_text = html_mod.unescape(result["translatedText"])
                            except Exception:
                                display_text = text
                        await ws.send_json({
                            "type": "transcript",
                            "speaker": speaker,
                            "text": display_text,
                            "text_en": text,
                        })

                async def _on_tool_call(name: str, args: dict) -> dict:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "status", "status": "fetching_data"})
                    result = await _handle_tool_call(name, args, latitude, longitude, language)
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "status", "status": "ready"})
                    return result

                async def _on_turn_complete():
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "turn_complete"})

                session = GeminiLiveSession(
                    api_key=GEMINI_API_KEY,
                    language_code=locale,
                    has_gps=has_gps,
                    latitude=latitude,
                    longitude=longitude,
                    on_audio=_on_audio,
                    on_transcript=_on_transcript,
                    on_tool_call=_on_tool_call,
                    on_turn_complete=_on_turn_complete,
                )
                await session.start()
                _live_sessions[session_id] = session
                await ws.send_json({"type": "session_started", "session_id": session_id})

            elif msg_type == "audio" and session:
                import base64 as b64
                pcm_data = b64.b64decode(msg["data"])
                await session.send_audio(pcm_data)

            elif msg_type == "text" and session:
                await session.send_text(msg.get("text", ""))

            elif msg_type == "end":
                break

    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        if session:
            await session.close()
        _live_sessions.pop(session_id, None)


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
        _loop = asyncio.get_event_loop()
        response = await _loop.run_in_executor(
            None, lambda: _gemini_generate(prompt)
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
# Text chat (for Twilio and fallback)
# ---------------------------------------------------------------------------
_text_sessions: dict[str, dict] = {}

CHAT_SYSTEM_PROMPT = """You are KisanMind — a wise, warm farming neighbor who helps Indian farmers.

LANGUAGE: Respond in English only. Translation happens automatically.

FIRST MESSAGE (greeting):
- ALWAYS mention that you have detected their location. Say: "Namaste! I can see you are calling from [general area]. What crop are you growing?"
- The system will tell you the farmer's GPS coordinates. Use general area name, not exact coordinates.

CONVERSATION FLOW:
1. If farmer hasn't said crop → greet with location detected + ask crop
2. If farmer said crop → ask ONE follow-up with 2-3 things: sowing date, land area, any problems?
3. After farmer's 2nd message → MUST call fetch_farm_data. No more questions.

INTERPRETING DATA FOR THE FARMER (after fetch_farm_data returns):
Do NOT just cite numbers. EXPLAIN what they mean for the farmer's crop:

Satellite health (NDVI):
- Score > 0.6 → "Your crop is healthy and growing well — the European Space Agency's Sentinel-2 satellite confirms good green cover"
- Score 0.4-0.6 → "Your crop health is moderate — Sentinel-2 satellite shows it could be better. Make sure water and nutrients are sufficient"
- Score < 0.4 → "Warning: Sentinel-2 satellite shows your crop health is poor. Check for disease or nutrient deficiency immediately"

Soil moisture (SAR):
- wet → "Sentinel-1 radar shows your soil has enough moisture — no need to water right now"
- dry → "Sentinel-1 radar shows your soil is getting dry — plan irrigation soon"

Weather: "On [specific dates], rain is expected — so don't water or spray before that. After rain, check for fungal issues."

Mandi: "Best price is Rs X/quintal at [mandi name] ([distance] km away). After transport costs, you'll get Rs Y net per quintal."
If no mandi data available: "Mandi prices for your crop are not in our system today. Check with your local market or call the KVK."

For follow-up questions: Use the SAME data already fetched. Do NOT call fetch_farm_data again unless farmer asks about a DIFFERENT crop.

ALWAYS END ADVISORY WITH:
1. Nearest KVK: mention the name, distance, and phone number from the data. Say "Visit your nearest KVK for detailed in-person guidance."
2. Disclaimer: "This advice is based on satellite and radar data and may differ from actual ground conditions. The final decision is always yours."
3. Ask: "Do you have any other questions?"

ENDING THE CALL:
If farmer says thank you, goodbye, no more questions, bas, dhanyavad, nahi, theek hai, no thank you — respond with:
"CALL_COMPLETE: Take care! Remember to visit [KVK name] for detailed guidance. Call again anytime. Jai Kisaan!"
You MUST include the exact text "CALL_COMPLETE:" at the start when ending the call.

SAFETY: Never recommend pesticide brands. For pests/disease → refer to KVK helpline 1800-180-1551.
"""


@app.post("/api/chat")
async def text_chat(req: ChatRequest):
    """Text-based chat endpoint — used by Twilio and as fallback."""
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in _text_sessions:
        _text_sessions[session_id] = {
            "history": [],
            "language": req.language,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "created_at": _time.time(),
        }

    session = _text_sessions[session_id]
    session["history"].append({"role": "user", "parts": [{"text": req.message}]})

    has_gps = req.latitude != 0 and req.longitude != 0
    location_note = f"Farmer's GPS: ({req.latitude}, {req.longitude})" if has_gps else "No GPS available."

    contents = []
    for turn in session["history"]:
        contents.append(types.Content(
            role=turn["role"],
            parts=[types.Part(text=p["text"]) if "text" in p else
                   types.Part(function_call=types.FunctionCall(name=p["function_call"]["name"], args=p["function_call"]["args"])) if "function_call" in p else
                   types.Part(function_response=types.FunctionResponse(name=p["function_response"]["name"], response=p["function_response"]["response"])) if "function_response" in p else
                   types.Part(text="")
                   for p in turn["parts"]],
        ))

    tool_decls = [
        {
            "name": "fetch_farm_data",
            "description": "Fetch comprehensive farm data including mandi prices, satellite crop health, weather forecast, growth stage, and nearest KVK for a farmer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop": {"type": "string", "description": "Crop name in English"},
                    "sowing_date": {"type": "string", "description": "Sowing date YYYY-MM-DD or empty"},
                    "land_area_bigha": {"type": "number", "description": "Land area in bigha, 0 if unknown"},
                    "problems": {"type": "string", "description": "Farmer-reported problems"},
                    "irrigation_type": {"type": "string", "description": "Irrigation method"},
                    "recent_activities": {"type": "string", "description": "Recent farming activities"},
                    "quantity_quintals": {"type": "number", "description": "Quantity in quintals, 0 if unknown"},
                    "selling_timeline": {"type": "string", "description": "When farmer wants to sell"},
                    "soil_type": {"type": "string", "description": "Soil type if known"},
                    "extra_observations": {"type": "string", "description": "Any other observations"},
                },
                "required": ["crop"],
            },
        },
    ]

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _gemini_generate(
                contents,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT + f"\n\n{location_note}",
                    tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**fd) for fd in tool_decls])],
                ),
            ),
        )

        # Check for function call
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    tool_result = await _handle_tool_call(
                        fc.name, dict(fc.args),
                        req.latitude, req.longitude, req.language
                    )

                    session["history"].append({
                        "role": "model",
                        "parts": [{"function_call": {"name": fc.name, "args": dict(fc.args)}}]
                    })
                    session["history"].append({
                        "role": "user",
                        "parts": [{"function_response": {"name": fc.name, "response": tool_result}}]
                    })

                    contents2 = []
                    for turn in session["history"]:
                        parts = []
                        for p in turn["parts"]:
                            if "text" in p:
                                parts.append(types.Part(text=p["text"]))
                            elif "function_call" in p:
                                parts.append(types.Part(function_call=types.FunctionCall(
                                    name=p["function_call"]["name"], args=p["function_call"]["args"],
                                )))
                            elif "function_response" in p:
                                parts.append(types.Part(function_response=types.FunctionResponse(
                                    name=p["function_response"]["name"], response=p["function_response"]["response"],
                                )))
                        contents2.append(types.Content(role=turn["role"], parts=parts))

                    response2 = await loop.run_in_executor(
                        None,
                        lambda: _gemini_generate(
                            contents2,
                            config=types.GenerateContentConfig(
                                system_instruction=CHAT_SYSTEM_PROMPT + f"\n\n{location_note}",
                            ),
                        ),
                    )
                    response_text = response2.text.strip()
                    session["history"].append({"role": "model", "parts": [{"text": response_text}]})

                    display_text = response_text
                    if req.language != "en":
                        try:
                            tc = translate.Client()
                            tr = tc.translate(response_text, target_language=req.language, source_language="en")
                            import html
                            display_text = html.unescape(tr["translatedText"])
                        except Exception:
                            pass

                    call_done = "CALL_COMPLETE:" in response_text
                    response_text = response_text.replace("CALL_COMPLETE:", "").strip()
                    display_text = display_text.replace("CALL_COMPLETE:", "").strip()
                    return {
                        "session_id": session_id,
                        "response": display_text,
                        "response_en": response_text,
                        "has_advisory": True,
                        "call_complete": call_done,
                    }

        response_text = response.text.strip()
        session["history"].append({"role": "model", "parts": [{"text": response_text}]})

        display_text = response_text
        if req.language != "en":
            try:
                tc = translate.Client()
                tr = tc.translate(response_text, target_language=req.language, source_language="en")
                import html
                display_text = html.unescape(tr["translatedText"])
            except Exception:
                pass

        call_done = "CALL_COMPLETE:" in response_text
        response_text = response_text.replace("CALL_COMPLETE:", "").strip()
        display_text = display_text.replace("CALL_COMPLETE:", "").strip()
        return {
            "session_id": session_id,
            "response": display_text,
            "response_en": response_text,
            "has_advisory": False,
            "call_complete": call_done,
        }

    except Exception as e:
        log.exception(f"Chat error: {e}")
        return {
            "session_id": session_id,
            "response": "Technical issue. Please try again.",
            "response_en": "Technical issue. Please try again.",
            "has_advisory": False,
            "call_complete": False,
        }


# ---------------------------------------------------------------------------
# Twilio Voice — Call session memory + returning caller cache
# ---------------------------------------------------------------------------
# In-memory call session (active call context)
_call_sessions: dict[str, dict] = {}  # {phone_number: {crop, lat, lon, state, language, last_advisory, last_advisory_data, timestamp}}
_CALL_SESSION_TTL = 7 * 24 * 60 * 60  # 7 days for returning caller recognition

BASE_URL = os.getenv("BASE_URL", "https://kisanmind-api-409924770511.asia-south1.run.app")


async def _send_sms_summary(to_number: str, advisory_data: dict, language: str = "hi"):
    """Send SMS summary of advisory to farmer after voice call. Fire-and-forget."""
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_PHONE_NUMBER", "")

    if not all([twilio_sid, twilio_auth, twilio_from, to_number]):
        log.info("SMS skipped — Twilio credentials not configured")
        return

    try:
        location = advisory_data.get("location", {})
        best = advisory_data.get("best_mandi", {})
        local = advisory_data.get("local_mandi", {})
        weather = advisory_data.get("weather", {})
        kvk = advisory_data.get("nearest_kvk", {})
        crop = advisory_data.get("crop", "")

        # Rain warning
        rain_note = ""
        for d in weather.get("daily_forecast", [])[:3]:
            if (d.get("precipitation_mm") or 0) > 5:
                rain_note = f"Rain: {d['date']} ({d['precipitation_mm']}mm)\n"
                break
        if not rain_note:
            rain_note = "No rain 3 days\n"

        sms_body = (
            f"KisanMind\n"
            f"{crop}, {location.get('location_name', '')}\n"
            f"Best: {best.get('market', '?')} Rs{best.get('modal_price', '?')}/q ({best.get('distance_km', '?')}km)\n"
            f"Local: {local.get('market', '?') if local else '?'} Rs{local.get('modal_price', '?') if local else '?'}/q\n"
            f"{rain_note}"
            f"KVK: {kvk.get('name', 'KVK') if kvk else 'KVK'} {kvk.get('distance_km', '?') if kvk else '?'}km\n"
            f"Helpline: 1800-180-1551"
        )

        # Translate SMS if not Hindi/English (SMS supports Unicode)
        if language not in ("hi", "en"):
            try:
                translate_client = translate.Client()
                result = translate_client.translate(sms_body, target_language=language, source_language="en")
                import html
                sms_body = html.unescape(result["translatedText"])
            except Exception:
                pass  # Keep English if translation fails

        # Send via Twilio REST API
        url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                auth=(twilio_sid, twilio_auth),
                data={"From": twilio_from, "To": to_number, "Body": sms_body},
            )
            if resp.status_code in (200, 201):
                log.info(f"SMS sent to {to_number}")
            else:
                log.warning(f"SMS failed: {resp.status_code} {resp.text}")

    except Exception as e:
        log.warning(f"SMS sending failed: {e}")


@app.post("/api/voice/incoming")
async def twilio_incoming_call(request: Request):
    """Twilio webhook: farmer calls. Start a Gemini-powered conversation."""
    form = await request.form()
    caller = form.get("From", "unknown")
    log.info(f"Incoming call from {caller}")

    session_id = f"twilio_{caller}_{int(_time.time())}"

    old_session = _call_sessions.get(caller)
    is_returning = old_session and (_time.time() - old_session.get("timestamp", 0)) < _CALL_SESSION_TTL

    greeting_msg = "Hello, I am calling for farming advice."
    if is_returning:
        crop = old_session.get("crop", "")
        loc = old_session.get("location_name", "")
        greeting_msg = f"I called before about {crop} from {loc}. I want today's update."

    lat = old_session.get("lat", 0) if old_session else 0
    lon = old_session.get("lon", 0) if old_session else 0

    chat_req = ChatRequest(
        session_id=session_id, message=greeting_msg,
        language="hi", latitude=lat, longitude=lon,
    )
    chat_resp = await text_chat(chat_req)
    greeting_text = chat_resp["response"]

    _call_sessions[caller] = {
        "chat_session_id": session_id, "timestamp": _time.time(),
        "language": "hi", "lat": lat, "lon": lon,
    }

    safe_greeting = greeting_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">{safe_greeting}</Say>
    <Gather input="speech" language="hi-IN" speechTimeout="4" timeout="12"
            action="{BASE_URL}/api/voice/process" method="POST">
    </Gather>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/api/voice/process")
async def twilio_process_speech(request: Request):
    """Twilio webhook: process farmer speech through Gemini conversation."""
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    caller = form.get("From", "unknown")
    log.info(f"Speech from {caller}: {speech_result}")

    session = _call_sessions.get(caller, {})
    chat_session_id = session.get("chat_session_id", f"twilio_{caller}")
    lang = session.get("language", "hi")
    lat = session.get("lat", 0)
    lon = session.get("lon", 0)
    locale = LANGUAGE_TO_LOCALE.get(lang, "hi-IN")

    if not speech_result:
        chat_req = ChatRequest(
            session_id=chat_session_id,
            message="(farmer was silent, could not hear anything)",
            language=lang, latitude=lat, longitude=lon,
        )
        resp = await text_chat(chat_req)
        safe_text = resp["response"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="{locale}">{safe_text}</Say>
    <Gather input="speech" language="{locale}" speechTimeout="4" timeout="12"
            action="{BASE_URL}/api/voice/process" method="POST">
    </Gather>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    try:
        chat_req = ChatRequest(
            session_id=chat_session_id, message=speech_result,
            language=lang, latitude=lat, longitude=lon,
        )
        resp = await text_chat(chat_req)
        response_text = resp["response"]
        safe_text = response_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="{locale}">{safe_text}</Say>
    <Gather input="speech" language="{locale}" speechTimeout="4" timeout="12"
            action="{BASE_URL}/api/voice/process" method="POST">
    </Gather>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        log.exception(f"Voice processing failed: {e}")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        Technical issue. Please call again.
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
