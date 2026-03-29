# Gemini Live Conversational Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-turn STT→Gemini→TTS pipeline with a multi-turn Gemini 3.1 Flash Live conversational engine where Gemini drives the entire farmer interaction — greeting, information extraction, and personalized advisory delivery — all through native voice with function calling for live data.

**Architecture:** Frontend opens a WebSocket to the backend. Backend maintains a Gemini Live session (`gemini-3.1-flash-live-preview`) per call. Farmer's audio streams in → Gemini processes natively → Gemini responds in voice → Gemini calls backend functions (fetch_mandi_data, fetch_satellite_data, fetch_weather_data, generate_advisory) when it has enough info → final advisory spoken to farmer. All text displayed on screen comes from Gemini's built-in transcription, translated via Google Translate API. Zero static strings.

**Tech Stack:** Gemini 3.1 Flash Live (WebSocket), google-genai Python SDK, FastAPI WebSocket endpoint, Next.js WebSocket client, Google Translate API for display text.

---

## File Structure

### Backend (new/modified)
- **Create:** `backend/gemini_live.py` — Gemini Live session manager: WebSocket proxy, function calling handlers, session state, transcription relay
- **Modify:** `backend/main.py` — Add WebSocket endpoint `/ws/chat`, add function declarations for Gemini tools, add `farmer_context` to advisory prompt, keep existing `/api/advisory` as internal function (called by Gemini via function calling)
- **Delete logic:** Remove static `TWILIO_WELCOME_*`, `TWILIO_FOLLOWUP`, `TWILIO_RETRY`, `TWILIO_GOODBYE` dicts (Gemini generates all text)

### Frontend (modified)
- **Modify:** `frontend/app/talk/page.tsx` — Replace entire audio pipeline (MediaRecorder → STT → advisory → TTS) with WebSocket connection that streams raw PCM audio to backend and plays PCM audio from Gemini. Remove ALL static strings (`getGreeting`, `FACTS`, `retryText`, `byeText`, `goodbyeText`). Display transcriptions from Gemini.

---

## Task 1: Backend — Gemini Live Session Manager

**Files:**
- Create: `backend/gemini_live.py`

This is the core engine. It manages a Gemini Live WebSocket session, handles function calls, and relays audio/transcriptions.

- [ ] **Step 1: Create `backend/gemini_live.py` with session manager class**

```python
"""
Gemini Live session manager for KisanMind.

Manages a persistent Gemini 3.1 Flash Live WebSocket session per farmer call.
Gemini handles: greeting, conversation, information extraction, advisory delivery.
Backend provides: function calling tools for live data (mandi, satellite, weather).
"""

import asyncio
import json
import logging
import time
from typing import Optional, Callable, Awaitable

from google import genai
from google.genai import types

log = logging.getLogger("kisanmind.gemini_live")

# ---------------------------------------------------------------------------
# Tool declarations — Gemini calls these to fetch real data
# ---------------------------------------------------------------------------
KISANMIND_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "fetch_farm_data",
                "description": (
                    "Fetch comprehensive farm data including mandi prices, satellite crop health, "
                    "weather forecast, growth stage, and nearest KVK for a farmer. "
                    "Call this ONLY when you have gathered enough information from the farmer "
                    "(at minimum: crop name). The more fields you provide, the better the advisory."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "crop": {
                            "type": "string",
                            "description": "Crop name in English (e.g., 'Okra', 'Tomato', 'Wheat')"
                        },
                        "sowing_date": {
                            "type": "string",
                            "description": "Sowing date in YYYY-MM-DD format, or empty if unknown"
                        },
                        "land_area_bigha": {
                            "type": "number",
                            "description": "Land area in bigha (1 bigha ≈ 0.25 hectare). 0 if unknown."
                        },
                        "problems": {
                            "type": "string",
                            "description": "Farmer-reported problems: pests, disease, yellowing, wilting, spots, etc. Empty if none reported."
                        },
                        "irrigation_type": {
                            "type": "string",
                            "description": "Irrigation method: borwell, canal, rain-fed, drip, sprinkler. Empty if unknown."
                        },
                        "recent_activities": {
                            "type": "string",
                            "description": "Recent farming activities: spraying, fertilizer, weeding, harvesting. Empty if none mentioned."
                        },
                        "quantity_quintals": {
                            "type": "number",
                            "description": "Expected or harvested quantity in quintals. 0 if unknown."
                        },
                        "selling_timeline": {
                            "type": "string",
                            "description": "When farmer wants to sell: 'now', 'this week', 'can wait', etc. Empty if unknown."
                        },
                        "soil_type": {
                            "type": "string",
                            "description": "Soil type if farmer mentioned: clay, sandy, loamy, black, red. Empty if unknown."
                        },
                        "extra_observations": {
                            "type": "string",
                            "description": "Any other observations the farmer shared that could be useful for the advisory."
                        },
                    },
                    "required": ["crop"],
                },
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# System instruction for Gemini Live
# ---------------------------------------------------------------------------
def build_system_instruction(language_code: str, has_gps: bool, lat: float = 0, lon: float = 0) -> str:
    """Build the system instruction that defines Gemini's personality and task."""
    location_context = ""
    if has_gps:
        location_context = f"The farmer's GPS location has been detected: ({lat}, {lon}). You do NOT need to ask for location."
    else:
        location_context = "The farmer's GPS location is NOT available. You will need to ask where they are farming."

    return f"""You are KisanMind — a wise, warm, knowledgeable farming neighbor who helps Indian farmers using real satellite data, mandi prices, and weather forecasts.

PERSONALITY:
- Talk like a caring elder neighbor, NOT a government officer or computer
- Be warm, encouraging, and practical
- React to what the farmer says — show you're listening by acknowledging their specific situation
- Add short relevant insights between questions to keep conversation interesting
- NEVER use technical jargon (no NDVI, EVI, API, satellite index)
- You speak {language_code} naturally

CONVERSATION LANGUAGE:
- You MUST speak in English only. Your responses will be translated to the farmer's language automatically.
- Keep sentences simple and short for accurate translation.

LOCATION: {location_context}

YOUR TASK:
You are having a voice conversation with a farmer. Your goal is to:
1. Greet them warmly
2. Gather information about their farm through NATURAL conversation (not interrogation)
3. Once you have enough information, call the fetch_farm_data function to get real data
4. Deliver a personalized advisory based on the data AND what the farmer told you

INFORMATION TO GATHER (through natural conversation, not a checklist):
- Crop name (REQUIRED — you cannot proceed without this)
- When they sowed / crop age (ask naturally: "when did you plant it?")
- Land area (ask naturally: "how much land do you have under this crop?")
- Current problems — pests, disease, yellowing, wilting, spots (ask: "is everything looking healthy, or are you seeing any issues?")
- Irrigation method — borwell/canal/rain-fed (ask: "how are you watering your crop?")
- Recent activities — spraying, fertilizer, weeding (ask: "have you done any spraying or added fertilizer recently?")
- Quantity expected (ask if relevant: "roughly how much are you expecting to harvest?")
- Selling plans (ask: "are you looking to sell soon or can you wait?")
- Any other observations the farmer shares — USE ALL OF IT

CONVERSATION FLOW:
- Ask 2-3 related things per turn, not one at a time (respects farmer's time)
- After farmer answers, ACKNOWLEDGE what they said with a short relevant insight, then ask the next questions
- Example: Farmer says "bhindi 2 mahine pehle lagayi" → You say: "2 months of okra — it should be fruiting nicely by now! Are you seeing good flower and fruit set, or any issues like yellowing or pests? And how are you watering — borwell or canal?"
- Do NOT ask more than 3 turns of questions. After 2-3 exchanges, call fetch_farm_data with whatever you have.
- If farmer gives everything in one message, go straight to fetch_farm_data

AFTER RECEIVING DATA (from fetch_farm_data function response):
- Deliver a PERSONALIZED advisory that DIRECTLY addresses the farmer's specific problems
- Reference what the farmer told you: "You mentioned yellowing leaves — the satellite data shows..."
- Include: crop health from satellite, weather actions with specific dates, best mandi with price/distance/net profit
- If farmer mentioned pests/disease → refer to nearest KVK with contact info
- Keep advisory under 150 words — farmer is in a field
- End with: "This is based on today's data. The final decision is yours."
- After advisory, ask if they have any other questions

SAFETY RULES:
- NEVER recommend pesticide or chemical brand names
- NEVER give loan, credit, or insurance advice
- For pest/disease → refer to KVK only
- NEVER guarantee yields, prices, or outcomes
- Always say "based on today's data"

WHAT TO DO IF FARMER PROVIDES EXTRA INFORMATION:
- If farmer mentions family situation, financial stress, previous crop failures — be empathetic
- Use ALL information to make the advisory more relevant
- Extra context about soil conditions, local market dynamics, neighboring farm issues — pass everything to fetch_farm_data via extra_observations
"""


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------
class GeminiLiveSession:
    """Manages a single Gemini Live session for one farmer call."""

    def __init__(
        self,
        api_key: str,
        language_code: str,
        has_gps: bool,
        latitude: float = 0,
        longitude: float = 0,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_tool_call: Optional[Callable[[str, dict], Awaitable[dict]]] = None,
        on_turn_complete: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.client = genai.Client(api_key=api_key)
        self.language_code = language_code
        self.has_gps = has_gps
        self.latitude = latitude
        self.longitude = longitude

        # Callbacks
        self.on_audio = on_audio              # Called with PCM audio chunks to send to farmer
        self.on_transcript = on_transcript    # Called with (speaker, text) for display
        self.on_tool_call = on_tool_call      # Called to execute function calls
        self.on_turn_complete = on_turn_complete

        self.session = None
        self._running = False
        self._receive_task = None
        self.created_at = time.time()

    async def start(self):
        """Open the Gemini Live session."""
        system_instruction = build_system_instruction(
            self.language_code, self.has_gps, self.latitude, self.longitude
        )

        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instruction,
            "tools": KISANMIND_TOOLS,
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Sulafat"  # Warm voice — good for farmer advisory
                    )
                ),
                language_code=self.language_code,
            ),
            "input_audio_transcription": types.AudioTranscriptionConfig(),
            "output_audio_transcription": types.AudioTranscriptionConfig(),
        }

        self.session = await self.client.aio.live.connect(
            model="gemini-3.1-flash-live-preview",
            config=config,
        )
        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        log.info(f"Gemini Live session started (lang={self.language_code}, gps={self.has_gps})")

    async def send_audio(self, pcm_data: bytes):
        """Stream PCM audio from farmer's mic to Gemini."""
        if self.session and self._running:
            await self.session.send_realtime_input(
                audio=types.Blob(data=pcm_data, mime_type="audio/pcm;rate=16000")
            )

    async def send_text(self, text: str):
        """Send text input (for testing or Twilio STT fallback)."""
        if self.session and self._running:
            await self.session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part(text=text)])]
            )

    async def _receive_loop(self):
        """Process all messages from Gemini Live."""
        try:
            async for response in self.session.receive():
                if not self._running:
                    break

                # Handle audio output
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            if self.on_audio:
                                await self.on_audio(part.inline_data.data)

                # Handle transcriptions
                if response.server_content:
                    content = response.server_content
                    if content.input_transcription and content.input_transcription.text:
                        if self.on_transcript:
                            await self.on_transcript("farmer", content.input_transcription.text)
                    if content.output_transcription and content.output_transcription.text:
                        if self.on_transcript:
                            await self.on_transcript("kisanmind", content.output_transcription.text)

                    # Turn complete signal
                    if content.turn_complete:
                        if self.on_turn_complete:
                            await self.on_turn_complete()

                # Handle function calls
                if response.tool_call:
                    function_responses = []
                    for fc in response.tool_call.function_calls:
                        log.info(f"Gemini tool call: {fc.name}({json.dumps(fc.args, ensure_ascii=False)[:200]})")
                        if self.on_tool_call:
                            result = await self.on_tool_call(fc.name, fc.args)
                        else:
                            result = {"error": "No tool handler configured"}
                        function_responses.append(
                            types.FunctionResponse(
                                name=fc.name,
                                id=fc.id,
                                response={"result": result},
                            )
                        )
                    await self.session.send_tool_response(function_responses=function_responses)

        except Exception as e:
            log.error(f"Gemini Live receive loop error: {e}")
        finally:
            self._running = False

    async def close(self):
        """Close the Gemini Live session."""
        self._running = False
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        if self._receive_task:
            self._receive_task.cancel()
        log.info("Gemini Live session closed")

    @property
    def is_active(self) -> bool:
        return self._running and self.session is not None
```

- [ ] **Step 2: Verify the file was created correctly**

Run: `python3 -c "import ast; ast.parse(open('backend/gemini_live.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/gemini_live.py
git commit -m "feat: add Gemini Live session manager with function calling for farmer conversations"
```

---

## Task 2: Backend — WebSocket Endpoint and Tool Handlers

**Files:**
- Modify: `backend/main.py` — Add WebSocket `/ws/chat` endpoint, add tool call handler that calls existing `_run_advisory()`, add farmer context to advisory prompt

- [ ] **Step 1: Add WebSocket imports and session store to `main.py`**

At the top of `main.py`, after existing imports, add:

```python
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import uuid

try:
    from backend.gemini_live import GeminiLiveSession, KISANMIND_TOOLS
except ImportError:
    from gemini_live import GeminiLiveSession, KISANMIND_TOOLS
```

Add session store after the `_sat_cache` initialization:

```python
# ---------------------------------------------------------------------------
# Gemini Live sessions (one per active call)
# ---------------------------------------------------------------------------
_live_sessions: dict[str, GeminiLiveSession] = {}  # session_id -> GeminiLiveSession
_SESSION_TTL = 600  # 10 minutes max per session
```

- [ ] **Step 2: Add the tool call handler function**

This function is called when Gemini invokes `fetch_farm_data`. It runs the existing advisory pipeline and returns structured data for Gemini to speak.

```python
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

        # Build the advisory request using existing pipeline
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

        # Build a farmer context string for Gemini to personalize the advisory
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

        # Extract key data for Gemini to speak
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

        # Build structured response for Gemini
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
            "satellite_health": sat.get("health", "Not available") if sat else "Not available",
            "satellite_ndvi": sat.get("ndvi", None) if sat else None,
            "satellite_image_date": sat.get("image_date", "?") if sat else "?",
            "growth_stage": growth.get("stage", "unknown") if growth else "unknown",
            "growth_detail": growth.get("detail", "") if growth else "",
            "price_trend": trend.get("trend", "stable") if trend else "stable",
            "price_trend_percent": trend.get("trend_percent", 0) if trend else 0,
            "nearest_kvk": {
                "name": kvk.get("name", "?") if kvk else "?",
                "distance_km": kvk.get("distance_km", "?") if kvk else "?",
                "phone": kvk.get("phone", "1800-180-1551") if kvk else "1800-180-1551",
            },
            "soil_moisture": extras.get("sar", {}).get("moisture_class", "unknown") if extras else "unknown",
            "heat_stress": extras.get("lst", {}).get("heat_stress", "none") if extras else "none",
            "cross_validation_warnings": [cv.get("finding", "") for cv in cross_val] if cross_val else [],
            "instructions": (
                "Now deliver a PERSONALIZED advisory to the farmer. "
                "DIRECTLY ADDRESS their reported problems using the satellite and weather data. "
                "Mention specific dates for weather actions. "
                "Give mandi recommendation with price, distance, and net profit. "
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
```

- [ ] **Step 3: Add the WebSocket endpoint**

```python
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for Gemini Live farmer conversations.

    Protocol:
    - Client sends: {"type": "config", "language": "hi", "latitude": 30.9, "longitude": 77.1}
    - Client sends: {"type": "audio", "data": "<base64 PCM 16kHz mono>"} (continuous stream)
    - Server sends: {"type": "audio", "data": "<base64 PCM 24kHz mono>"} (Gemini voice)
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
                # Initialize Gemini Live session
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
                        # Translate transcript for display if not English
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

                await ws.send_json({
                    "type": "session_started",
                    "session_id": session_id,
                })

            elif msg_type == "audio" and session:
                # Stream PCM audio to Gemini
                import base64 as b64
                pcm_data = b64.b64decode(msg["data"])
                await session.send_audio(pcm_data)

            elif msg_type == "text" and session:
                # Text input fallback (for testing)
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
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/main.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add WebSocket /ws/chat endpoint with Gemini Live function calling"
```

---

## Task 3: Frontend — Replace Audio Pipeline with WebSocket

**Files:**
- Modify: `frontend/app/talk/page.tsx`

Replace the entire audio pipeline (MediaRecorder → STT → advisory fetch → TTS playback) with a WebSocket connection that streams raw PCM to the backend and plays PCM audio from Gemini. Remove ALL static strings.

- [ ] **Step 1: Replace the audio pipeline and conversation logic**

The key changes:
1. Remove: `startMic`, `stopMic`, `listenOnce`, `processOneTurn`, `playTTS`, `waitForAudioEnd`, `getGreeting`, `FACTS`, all static text strings
2. Add: WebSocket connection, AudioContext for PCM capture/playback, ScriptProcessorNode for real-time audio streaming
3. Remove: `callState` states "greeting"/"processing"/"speaking" — replace with simpler "in-call"/"ended" since Gemini handles all turn management
4. Transcriptions from Gemini populate the chat messages (already translated to farmer's language)

Replace the entire component with:

```tsx
"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, Phone, PhoneOff, Sun, CloudRain, Cloud, Leaf, Volume2, TrendingUp, MapPin, Thermometer, CheckCircle, Droplets, AlertTriangle, Sprout, Shield, Satellite } from "lucide-react";
import Link from "next/link";
import useGeolocation from "../hooks/useGeolocation";

/* ------------------------------------------------------------------ */
/*  Languages                                                          */
/* ------------------------------------------------------------------ */
const LANGUAGES = [
  { code: "hi", label: "हिन्दी" }, { code: "en", label: "English" },
  { code: "ta", label: "தமிழ்" }, { code: "te", label: "తెలుగు" },
  { code: "bn", label: "বাংলা" }, { code: "mr", label: "मराठी" },
  { code: "gu", label: "ગુજરાતી" }, { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" }, { code: "pa", label: "ਪੰਜਾਬੀ" },
  { code: "or", label: "ଓଡ଼ିଆ" }, { code: "as", label: "অসমীয়া" },
  { code: "mai", label: "मैथिली" }, { code: "sa", label: "संस्कृतम्" },
  { code: "ne", label: "नेपाली" }, { code: "sd", label: "سنڌي" },
  { code: "doi", label: "डोगरी" }, { code: "ks", label: "كٲشُر" },
  { code: "kok", label: "कोंकणी" }, { code: "sat", label: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { code: "brx", label: "বোড়ো" }, { code: "mni", label: "मणिपुरी" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ChatMessage {
  type: "farmer" | "kisanmind";
  text: string;
  timestamp: Date;
  kind?: "conversation" | "advisory" | "status";
}

type CallState = "pre-call" | "connecting" | "in-call" | "ended";

/* ------------------------------------------------------------------ */
/*  PCM Audio Helpers                                                  */
/* ------------------------------------------------------------------ */

/** Convert Float32Array (Web Audio API) to Int16 PCM bytes */
function float32ToInt16(float32: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

/** Downsample from source sample rate to 16kHz */
function downsample(buffer: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const idx = Math.round(i * ratio);
    result[i] = buffer[Math.min(idx, buffer.length - 1)];
  }
  return result;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function TalkPage() {
  const [language, setLanguageRaw] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("kisanmind_lang") || "hi";
    }
    return "hi";
  });
  const setLanguage = (lang: string) => {
    setLanguageRaw(lang);
    if (typeof window !== "undefined") localStorage.setItem("kisanmind_lang", lang);
  };

  const [callState, setCallState] = useState<CallState>("pre-call");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [statusText, setStatusText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playBufferRef = useRef<Float32Array[]>([]);
  const isPlayingRef = useRef(false);
  const callActiveRef = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const geo = useGeolocation();

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = useCallback((type: "farmer" | "kisanmind", text: string, kind?: "conversation" | "advisory" | "status") => {
    setMessages((prev) => [...prev, { type, text, timestamp: new Date(), kind }]);
  }, []);

  /* ---- PCM playback: queue Gemini's audio chunks and play sequentially ---- */
  const playPcmChunk = useCallback(async (base64Pcm: string) => {
    const ctx = audioContextRef.current;
    if (!ctx) return;

    // Decode base64 to Int16 PCM (24kHz from Gemini)
    const raw = atob(base64Pcm);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const int16 = new Int16Array(bytes.buffer);

    // Convert Int16 to Float32 for Web Audio API
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 0x7fff;

    // Create AudioBuffer at 24kHz (Gemini output rate)
    const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    // Queue and play
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.start();
  }, []);

  /* ---- Start call: open WebSocket, start mic streaming ---- */
  const startCall = useCallback(async () => {
    callActiveRef.current = true;
    setMessages([]);
    setCallState("connecting");
    setStatusText("");

    try {
      // Set up AudioContext
      const ctx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = ctx;

      // Open WebSocket
      const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/chat";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        // Send config
        ws.send(JSON.stringify({
          type: "config",
          language,
          latitude: geo.latitude || 0,
          longitude: geo.longitude || 0,
        }));
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "session_started":
            setCallState("in-call");
            setStatusText("");
            break;

          case "audio":
            // Play Gemini's voice
            playPcmChunk(msg.data);
            break;

          case "transcript":
            // Display translated text in chat
            addMessage(
              msg.speaker === "farmer" ? "farmer" : "kisanmind",
              msg.text,
              "conversation"
            );
            break;

          case "status":
            if (msg.status === "fetching_data") {
              setStatusText("🔍");
            } else {
              setStatusText("");
            }
            break;

          case "turn_complete":
            // Gemini finished speaking — could update UI if needed
            break;
        }
      };

      ws.onerror = () => {
        setCallState("ended");
        setStatusText("");
      };

      ws.onclose = () => {
        if (callActiveRef.current) {
          callActiveRef.current = false;
          setCallState("ended");
        }
      };

      // Start mic and stream PCM
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      streamRef.current = stream;

      const source = ctx.createMediaStreamSource(stream);
      // ScriptProcessorNode: captures raw audio samples
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (!callActiveRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const downsampled = downsample(input, ctx.sampleRate, 16000);
        const pcmBytes = float32ToInt16(downsampled);
        const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmBytes)));
        wsRef.current.send(JSON.stringify({ type: "audio", data: base64 }));
      };

      source.connect(processor);
      processor.connect(ctx.destination); // Required for ScriptProcessor to work

    } catch (err) {
      console.error("Failed to start call:", err);
      setCallState("ended");
    }
  }, [language, geo.latitude, geo.longitude, addMessage, playPcmChunk]);

  /* ---- End call ---- */
  const endCall = useCallback(() => {
    callActiveRef.current = false;

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
      wsRef.current.close();
      wsRef.current = null;
    }

    // Stop mic
    processorRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    // Close audio context
    audioContextRef.current?.close();
    audioContextRef.current = null;

    setCallState("ended");
    setStatusText("");
  }, []);

  /* ---- UI ---- */
  const isInCall = callState === "in-call" || callState === "connecting";
  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0a0f14] text-white">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0d1117]/90 border-b border-white/5">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl">🌾</span>
          <span className="text-base font-bold gradient-text">KisanMind</span>
        </Link>

        {!isInCall && callState !== "ended" && (
          <button
            onClick={() => setShowLangPicker(!showLangPicker)}
            className="flex items-center gap-1.5 rounded-full bg-white/10 px-4 py-2 text-sm font-medium hover:bg-white/15"
          >
            <Volume2 size={14} />
            {currentLang.label}
          </button>
        )}

        {isInCall && (
          <div className="flex items-center gap-2 text-sm">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-white/60">{currentLang.label}</span>
            {statusText && <span className="text-white/40 text-xs">{statusText}</span>}
          </div>
        )}

        <Link href="/" className="rounded-lg bg-white/5 px-3 py-2 text-xs text-white/60 hover:bg-white/10">
          Dashboard
        </Link>
      </div>

      {/* Language picker */}
      {showLangPicker && !isInCall && callState !== "ended" && (
        <div className="absolute top-14 left-0 right-0 z-50 bg-[#0d1117] border-b border-white/10 px-4 py-4 shadow-2xl">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-w-2xl mx-auto">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => { setLanguage(lang.code); setShowLangPicker(false); }}
                className={`rounded-xl px-3 py-3 text-sm font-medium min-h-[52px] ${
                  language === lang.code
                    ? "bg-healthy/20 text-healthy border-2 border-healthy/40"
                    : "bg-white/5 text-white/70 border-2 border-transparent hover:bg-white/10"
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {callState === "pre-call" && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-50">
            <Leaf size={48} className="mb-4" />
            <p className="text-lg">🌾 KisanMind</p>
            <p className="text-sm mt-2 text-white/40">Tap the green button to start</p>
          </div>
        )}

        {callState === "connecting" && (
          <div className="flex justify-center mt-8">
            <div className="bg-emerald-600/10 border border-emerald-500/20 rounded-2xl px-6 py-4">
              <div className="flex gap-1.5 justify-center">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:150ms]" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
              msg.type === "farmer"
                ? "bg-blue-600/20 border border-blue-500/20 text-white/90 text-sm"
                : msg.kind === "status"
                ? "bg-white/5 border border-white/10 text-white/60 text-xs italic"
                : "bg-emerald-600/10 border border-emerald-500/20 text-white/90 text-sm"
            }`}>
              <div className="text-[10px] text-white/30 mb-1">
                {msg.type === "farmer" ? "You" : "KisanMind"} · {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              {msg.text}
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      {/* Call controls */}
      <div className="flex flex-col items-center gap-4 px-4 py-6 bg-[#0d1117]/80 border-t border-white/5">
        {callState === "pre-call" && (
          <button
            onClick={startCall}
            className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-lg shadow-emerald-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <Phone size={32} className="text-white" />
          </button>
        )}

        {isInCall && (
          <button
            onClick={endCall}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-red-500 to-red-700 shadow-lg shadow-red-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <PhoneOff size={28} className="text-white" />
          </button>
        )}

        {callState === "ended" && (
          <button
            onClick={() => { setCallState("pre-call"); setMessages([]); }}
            className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-lg shadow-emerald-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <Phone size={32} className="text-white" />
          </button>
        )}

        {isInCall && (
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-white/40">Live</span>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/app/talk/page.tsx
git commit -m "feat: replace STT/TTS pipeline with Gemini Live WebSocket — zero static strings"
```

---

## Task 4: Backend — Update Twilio Voice to Use Gemini Live Chat

**Files:**
- Modify: `backend/main.py` — Update Twilio endpoints to use the new conversational engine

Since Twilio uses TwiML `<Gather>` (which returns text from speech), Twilio calls go through a thin adapter that:
1. On incoming call: creates a session, sends greeting via Gemini, and returns TwiML with the audio
2. On each farmer speech: sends text to the Gemini session, gets response, returns TwiML

- [ ] **Step 1: Add a text-based chat endpoint for Twilio (since Twilio provides text, not raw audio)**

```python
class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    language: str = "hi"
    latitude: float = 0
    longitude: float = 0


# In-memory text chat sessions (for Twilio and fallback)
_text_sessions: dict[str, dict] = {}  # session_id -> {history, extracted, ...}

CHAT_SYSTEM_PROMPT = """You are KisanMind — a wise, warm, knowledgeable farming neighbor.

You are having a text conversation with an Indian farmer. Your task:
1. Greet them warmly
2. Gather farm information through natural conversation
3. When you have enough info, call fetch_farm_data
4. Deliver a personalized advisory

CONVERSATION LANGUAGE: Respond in English only. Translation happens automatically.

INFORMATION TO GATHER (naturally, not as interrogation):
- Crop name (REQUIRED)
- Sowing date / crop age
- Land area
- Problems: pests, disease, yellowing, wilting
- Irrigation type
- Recent activities: spraying, fertilizer
- Quantity expected
- Selling timeline
- Any other observations

RULES:
- Ask 2-3 related things per turn
- Acknowledge farmer's answer with a short relevant insight before next question
- After 2-3 exchanges, call fetch_farm_data with whatever you have
- Keep responses under 50 words (these get spoken via TTS)
- NEVER recommend pesticide brands, NEVER give loan advice
- For pests/disease → refer to KVK
"""


@app.post("/api/chat")
async def text_chat(req: ChatRequest):
    """Text-based chat endpoint — used by Twilio and as fallback.
    Gemini manages the conversation, extracts info, calls fetch_farm_data when ready."""

    session_id = req.session_id or str(uuid.uuid4())

    # Get or create session
    if session_id not in _text_sessions:
        _text_sessions[session_id] = {
            "history": [],
            "language": req.language,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "created_at": time.time(),
        }

    session = _text_sessions[session_id]
    session["history"].append({"role": "user", "parts": [{"text": req.message}]})

    has_gps = req.latitude != 0 and req.longitude != 0
    location_note = f"Farmer's GPS: ({req.latitude}, {req.longitude})" if has_gps else "No GPS available."

    # Build Gemini contents with full history
    contents = []
    for turn in session["history"]:
        contents.append(types.Content(
            role=turn["role"],
            parts=[types.Part(text=p["text"]) for p in turn["parts"]],
        ))

    # Call Gemini with function calling
    tool_declarations = types.Tool(function_declarations=[
        fd for tool in KISANMIND_TOOLS for fd in tool["function_declarations"]
    ])

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT + f"\n\n{location_note}",
                    tools=[tool_declarations],
                ),
            ),
        )

        # Check if Gemini wants to call a function
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    # Execute the function
                    tool_result = await _handle_tool_call(
                        fc.name, dict(fc.args),
                        req.latitude, req.longitude, req.language
                    )

                    # Send function result back to Gemini for final response
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
                                    name=p["function_call"]["name"],
                                    args=p["function_call"]["args"],
                                )))
                            elif "function_response" in p:
                                parts.append(types.Part(function_response=types.FunctionResponse(
                                    name=p["function_response"]["name"],
                                    response=p["function_response"]["response"],
                                )))
                        contents2.append(types.Content(role=turn["role"], parts=parts))

                    response2 = await loop.run_in_executor(
                        None,
                        lambda: gemini_client.models.generate_content(
                            model="gemini-3-flash-preview",
                            contents=contents2,
                            config=types.GenerateContentConfig(
                                system_instruction=CHAT_SYSTEM_PROMPT + f"\n\n{location_note}",
                            ),
                        ),
                    )
                    response_text = response2.text.strip()
                    session["history"].append({"role": "model", "parts": [{"text": response_text}]})

                    # Translate
                    display_text = response_text
                    if req.language != "en":
                        try:
                            tc = translate.Client()
                            tr = tc.translate(response_text, target_language=req.language, source_language="en")
                            import html
                            display_text = html.unescape(tr["translatedText"])
                        except Exception:
                            pass

                    return {
                        "session_id": session_id,
                        "response": display_text,
                        "response_en": response_text,
                        "has_advisory": True,
                    }

        # Regular text response (no function call)
        response_text = response.text.strip()
        session["history"].append({"role": "model", "parts": [{"text": response_text}]})

        # Translate
        display_text = response_text
        if req.language != "en":
            try:
                tc = translate.Client()
                tr = tc.translate(response_text, target_language=req.language, source_language="en")
                import html
                display_text = html.unescape(tr["translatedText"])
            except Exception:
                pass

        return {
            "session_id": session_id,
            "response": display_text,
            "response_en": response_text,
            "has_advisory": False,
        }

    except Exception as e:
        log.exception(f"Chat error: {e}")
        return {
            "session_id": session_id,
            "response": "Technical issue. Please try again.",
            "response_en": "Technical issue. Please try again.",
            "has_advisory": False,
        }
```

- [ ] **Step 2: Update Twilio endpoints to use `/api/chat`**

Replace the existing `twilio_incoming_call` and `twilio_process_speech` with versions that use the new chat engine:

```python
@app.post("/api/voice/incoming")
async def twilio_incoming_call(request: Request):
    """Twilio webhook: farmer calls. Start a Gemini-powered conversation."""
    form = await request.form()
    caller = form.get("From", "unknown")
    log.info(f"Incoming call from {caller}")

    # Create a chat session for this caller
    session_id = f"twilio_{caller}_{int(time.time())}"

    # Check if returning caller
    old_session = _call_sessions.get(caller)
    is_returning = old_session and (time.time() - old_session.get("timestamp", 0)) < _CALL_SESSION_TTL

    # Send initial greeting through Gemini
    greeting_msg = "Hello, I am calling for farming advice."
    if is_returning:
        crop = old_session.get("crop", "")
        loc = old_session.get("location_name", "")
        greeting_msg = f"I called before about {crop} from {loc}. I want today's update."

    lat = old_session.get("lat", 0) if old_session else 0
    lon = old_session.get("lon", 0) if old_session else 0

    chat_req = ChatRequest(
        session_id=session_id,
        message=greeting_msg,
        language="hi",
        latitude=lat,
        longitude=lon,
    )
    chat_resp = await text_chat(chat_req)
    greeting_text = chat_resp["response"]

    # Store session mapping
    _call_sessions[caller] = {
        "chat_session_id": session_id,
        "timestamp": time.time(),
        "language": "hi",
        "lat": lat,
        "lon": lon,
    }

    safe_greeting = greeting_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        {safe_greeting}
    </Say>
    <Gather input="speech" language="hi-IN" speechTimeout="4" timeout="12"
            action="{BASE_URL}/api/voice/process" method="POST">
        <Say voice="Polly.Aditi" language="hi-IN">
            </Say>
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
        # No speech detected — ask to repeat
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
            session_id=chat_session_id,
            message=speech_result,
            language=lang, latitude=lat, longitude=lon,
        )
        resp = await text_chat(chat_req)
        response_text = resp["response"]

        safe_text = response_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if resp.get("has_advisory"):
            # Advisory delivered — offer follow-up then goodbye
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="{locale}">{safe_text}</Say>
    <Pause length="1"/>
    <Gather input="speech" language="{locale}" speechTimeout="4" timeout="10"
            action="{BASE_URL}/api/voice/process" method="POST">
    </Gather>
</Response>"""
        else:
            # Conversation continues
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
        भाई माफ कीजिए, थोड़ी तकनीकी दिक्कत आ गई। एक बार फिर से कॉल कर लीजिए।
    </Say>
</Response>"""
        return Response(content=twiml, media_type="application/xml")
```

- [ ] **Step 3: Remove old static string dictionaries**

Delete these from `main.py`:
- `TWILIO_WELCOME_NEW`
- `TWILIO_WELCOME_RETURNING`
- `TWILIO_FOLLOWUP`
- `TWILIO_GOODBYE`
- `TWILIO_RETRY`

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/main.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: update Twilio voice to use Gemini conversational engine — no static strings"
```

---

## Task 5: Backend — Remove Old Single-Turn Crop Extraction

**Files:**
- Modify: `backend/main.py` — Clean up the old crop auto-detection logic in `_run_advisory()` since crop is now always provided by Gemini

- [ ] **Step 1: Simplify `_run_advisory` crop handling**

The old 3-step crop extraction (normalise_crop → Gemini extraction → "Unknown" fallback) is no longer needed because Gemini Live extracts the crop during conversation and passes it via `fetch_farm_data`. Replace lines 2133-2176 with:

```python
async def _run_advisory(req: AdvisoryRequest):
    crop = req.crop
    if not crop or crop.lower() in ("auto", "unknown"):
        crop = "Unknown"
    log.info(f"Advisory for crop: {crop}")
```

- [ ] **Step 2: Remove the old `normalise_crop` import**

The import `from agents.vaani_setu.intent_extractor import normalise_crop, CROP_NAME_MAP` and the sys.path manipulation are no longer needed since Gemini handles crop extraction. Remove them.

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/main.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "refactor: simplify _run_advisory crop handling — Gemini extracts crop during conversation"
```

---

## Task 6: Backend — Add Farmer Context to Advisory Prompt

**Files:**
- Modify: `backend/main.py` — Pass farmer-reported problems, irrigation, activities to `generate_advisory_with_gemini` so the advisory is personalized

- [ ] **Step 1: Add `farmer_context` parameter to `generate_advisory_with_gemini`**

Update the function signature:

```python
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
    farmer_context: str = "",  # NEW: farmer-reported problems, observations
) -> str:
```

- [ ] **Step 2: Add farmer context to the prompt**

After the `{kvk_section}` in the prompt (around line 1198), add:

```python
    farmer_problems_section = ""
    if farmer_context:
        farmer_problems_section = f"""
FARMER'S OWN OBSERVATIONS (MUST address these specifically):
{farmer_context}
IMPORTANT: Cross-reference these observations with satellite and weather data.
If farmer reports yellowing → check satellite health and soil moisture data.
If farmer reports pests → refer to KVK, do NOT guess treatment.
If farmer reports recent spraying → note that satellite data may not reflect this yet.
"""
```

Insert `{farmer_problems_section}` into the prompt between the weather section and the KVK section.

- [ ] **Step 3: Update the OUTPUT FORMAT in the prompt**

Change the output format from 5 sections to 6:

```python
OUTPUT FORMAT (exactly 6 short sections, in this order):
1. Crop health — satellite data + farmer's observations cross-referenced (1-2 sentences)
2. Farmer's problem response — directly address what they reported (1-3 sentences)
3. Weather action (1-2 sentences, specific DO or DON'T with date)
4. Best mandi recommendation (price, distance, net profit)
5. Sell timing advice (based on price trend, hedge if low confidence)
6. KVK info + disclaimer
```

If farmer_context is empty, keep original 5-section format.

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('backend/main.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add farmer_context to advisory prompt for personalized problem-specific advice"
```

---

## Task 7: Integration Testing

- [ ] **Step 1: Test the WebSocket endpoint manually**

Run the backend:
```bash
cd /mnt/experiments/et-genai-hackathon-phase-2
PYTHONPATH=. python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Test WebSocket with a simple script:
```python
import asyncio
import json
import websockets

async def test():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        # Send config
        await ws.send(json.dumps({
            "type": "config",
            "language": "hi",
            "latitude": 30.9,
            "longitude": 77.1,
        }))

        # Wait for session_started
        msg = await ws.recv()
        data = json.loads(msg)
        print(f"Session: {data}")
        assert data["type"] == "session_started"

        # Send text message (test mode)
        await ws.send(json.dumps({
            "type": "text",
            "text": "Main bhindi uga raha hoon, 2 mahine ho gaye",
        }))

        # Receive responses
        for _ in range(20):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(msg)
                print(f"[{data['type']}] {data.get('text', data.get('status', ''))[:100]}")
            except asyncio.TimeoutError:
                break

asyncio.run(test())
```

Expected: Session starts, Gemini responds with follow-up questions, eventually calls fetch_farm_data, delivers advisory.

- [ ] **Step 2: Test the text chat endpoint**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "main bhindi uga raha hoon", "language": "hi", "latitude": 30.9, "longitude": 77.1}'
```

Expected: JSON response with Gemini's follow-up question in Hindi.

- [ ] **Step 3: Test the frontend**

```bash
cd frontend && npm run dev
```

Open browser, click the green phone button, speak "main bhindi uga raha hoon". Verify:
- Gemini responds in voice (Hindi)
- Transcriptions appear in chat (in Hindi)
- After 2-3 exchanges, advisory is delivered
- No static strings visible anywhere

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Gemini Live conversational engine — end-to-end integration"
```
