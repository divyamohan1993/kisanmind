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
                            "description": "Land area in bigha (1 bigha = 0.25 hectare). 0 if unknown."
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
        self.on_audio = on_audio
        self.on_transcript = on_transcript
        self.on_tool_call = on_tool_call
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
                        voice_name="Sulafat"
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
