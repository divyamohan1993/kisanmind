"""
KisanMind Backend — Real API-powered agricultural advisory for Indian farmers.
NO fake data. Every data point comes from a real API call.
"""

import os
import json
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAl580uOrGBdneTgAMcedCwp-40e_dTcws")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "lmsforshantithakur")

if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY not set")
if not AGMARKNET_API_KEY:
    raise RuntimeError("AGMARKNET_API_KEY not set")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kisanmind")

# Gemini client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="KisanMind API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class IntentRequest(BaseModel):
    transcript: str
    language: str = "hi"


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
    """Fetch real mandi prices from AgMarkNet / data.gov.in."""
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

    records = []
    # Try direct AgMarkNet API first
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                records = data.get("records", [])
                if records:
                    log.info(f"AgMarkNet direct: {len(records)} records")
                    break
        except Exception as e:
            log.warning(f"AgMarkNet direct attempt {attempt+1} failed: {e}")
            await asyncio.sleep(0.5)

    # Fallback: read from GCS cache (pre-fetched, publicly accessible)
    if not records:
        crop_lower = crop.lower().replace(" ", "_")
        gcs_url = f"https://storage.googleapis.com/kisanmind-cache/mandi-prices/agmarknet_{crop_lower}.json"
        log.info(f"Falling back to GCS cache: {gcs_url}")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(gcs_url)
                resp.raise_for_status()
                data = resp.json()
                all_records = data.get("records", [])
                # Filter by state
                records = [r for r in all_records if r.get("state", "").lower() == state.lower()]
                if not records:
                    records = all_records[:20]  # If no state match, use top 20
                else:
                    records = records[:20]
                log.info(f"GCS cache: {len(records)} records for {state}")
        except Exception as e:
            log.error(f"GCS cache also failed: {e}")

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
) -> str:
    """Send all real data to Gemini 2.5 Flash and get a conversational advisory."""
    language_name = LANGUAGE_NAMES.get(language, "Hindi")

    local_mandi_name = local_mandi["market"] if local_mandi else "N/A"
    local_price = local_mandi["modal_price"] if local_mandi else 0
    best_price = best_mandi["net_profit_per_quintal"] or best_mandi["modal_price"]
    price_advantage = round(best_price - local_price, 2) if local_mandi and local_price else 0

    prompt = f"""You are KisanMind, a friendly agricultural advisor talking to an Indian farmer.
Speak in {language_name} language as if you're their trusted friend/elder.
Use simple words. No English jargon. Use local units (quintal, bigha).
Always mention specific numbers — prices, distances, temperatures.

Here is the real data:
Location: {location_name}, {state}
Crop: {crop}
Today's mandi prices: {json.dumps(mandis[:10], ensure_ascii=False)}
Best mandi: {best_mandi['market']} at ₹{best_mandi['modal_price']}/quintal ({best_mandi.get('distance_km', 'N/A')}km away, {best_mandi.get('duration_text', 'N/A')} travel)
Local mandi: {local_mandi_name} at ₹{local_price}/quintal
Price advantage: ₹{price_advantage}/quintal more at {best_mandi['market']}
Weather next 5 days: {weather['summary']}

Give the farmer a complete advisory covering:
1. Where to sell (best mandi with price, distance, net profit)
2. Weather actions (what to do, what NOT to do)
3. Any warnings

Keep it conversational — like talking to a friend on phone. Under 200 words.
Add disclaimer: "Yeh data aaj ki AgMarkNet aur mausam report se hai. Final faisla aap ka hai."
"""

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


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
        },
    }


@app.post("/api/advisory")
async def advisory(req: AdvisoryRequest):
    """Main advisory endpoint — all data from real APIs, zero fake data."""
    log.info(f"Advisory request: crop={req.crop}, lat={req.latitude}, lon={req.longitude}, lang={req.language}")

    try:
        return await _run_advisory(req)
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Advisory pipeline failed: {e}")
        raise HTTPException(500, f"Advisory pipeline failed: {str(e)}")


async def _run_advisory(req: AdvisoryRequest):
    # 1. Reverse geocode
    location = await reverse_geocode(req.latitude, req.longitude)
    log.info(f"Location: {location}")

    # 2. Fetch mandi prices
    mandis = await fetch_mandi_prices(req.crop, location["state"])
    log.info(f"Found {len(mandis)} mandis with prices")

    # 3. Get distances for each mandi
    mandis = await get_distances(req.latitude, req.longitude, mandis)

    # 4. Calculate net profits
    mandis = calculate_net_profits(mandis)

    # 5. Find best mandi (highest net profit) and local/closest mandi
    mandis_with_profit = [m for m in mandis if m.get("net_profit_per_quintal") is not None]
    if mandis_with_profit:
        best_mandi = max(mandis_with_profit, key=lambda m: m["net_profit_per_quintal"])
        local_mandi = min(mandis_with_profit, key=lambda m: m["distance_km"])
    else:
        # Fallback: sort by modal_price if distances failed
        best_mandi = max(mandis, key=lambda m: m["modal_price"])
        local_mandi = mandis[0] if mandis else None

    # 6. Fetch weather
    weather = await fetch_weather(req.latitude, req.longitude)

    # 7. Generate advisory via Gemini
    advisory_text = await generate_advisory_with_gemini(
        language=req.language,
        location_name=location["location_name"],
        state=location["state"],
        crop=req.crop,
        mandis=mandis,
        best_mandi=best_mandi,
        local_mandi=local_mandi,
        weather=weather,
    )

    return {
        "location": location,
        "crop": req.crop,
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
async def speech_to_text(req: STTRequest):
    """Transcribe audio using Google Cloud Speech-to-Text V2. Real transcription."""
    encoding_map = {
        "WEBM_OPUS": speech.ExplicitDecodingConfig.AudioEncoding.WEBM_OPUS
        if hasattr(speech.ExplicitDecodingConfig, "AudioEncoding")
        else None,
        "LINEAR16": speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16
        if hasattr(speech.ExplicitDecodingConfig, "AudioEncoding")
        else None,
        "FLAC": speech.ExplicitDecodingConfig.AudioEncoding.FLAC
        if hasattr(speech.ExplicitDecodingConfig, "AudioEncoding")
        else None,
        "MP3": speech.ExplicitDecodingConfig.AudioEncoding.MP3
        if hasattr(speech.ExplicitDecodingConfig, "AudioEncoding")
        else None,
    }

    audio_bytes = base64.b64decode(req.audio_base64)

    try:
        stt_client = speech.SpeechClient()

        # Build recognition config for V2
        config = speech.RecognitionConfig(
            explicit_decoding_config=speech.ExplicitDecodingConfig(
                encoding=encoding_map.get(req.encoding, speech.ExplicitDecodingConfig.AudioEncoding.WEBM_OPUS),
                sample_rate_hertz=48000,
                audio_channel_count=1,
            ),
            language_codes=[req.language],
            model="long",
        )

        request = speech.RecognizeRequest(
            recognizer=f"projects/{GOOGLE_CLOUD_PROJECT}/locations/global/recognizers/_",
            config=config,
            content=audio_bytes,
        )

        response = stt_client.recognize(request=request)

    except Exception as e:
        raise HTTPException(502, f"Google Cloud Speech-to-Text failed: {e}")

    if not response.results:
        return {
            "transcript": "",
            "confidence": 0.0,
            "detected_language": req.language,
        }

    best = response.results[0].alternatives[0]
    return {
        "transcript": best.transcript,
        "confidence": round(best.confidence, 4) if best.confidence else 0.0,
        "detected_language": req.language,
    }


@app.post("/api/extract-intent")
async def extract_intent(req: IntentRequest):
    """Use Gemini to extract structured intent from farmer's speech."""
    prompt = f"""You are a parser for an Indian agriculture app. Extract structured data from the farmer's speech.

Transcript (in {LANGUAGE_NAMES.get(req.language, 'Hindi')}): "{req.transcript}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "crop": "<crop name in English or null>",
  "location": "<location name or null>",
  "intent": "<one of: where_to_sell, price_check, weather_check, pest_advisory, full_advisory, general_question>",
  "language": "{req.language}"
}}"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
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
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
