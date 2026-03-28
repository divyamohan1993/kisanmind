"""
VaaniSetu (Voice Bridge) — ADK Agent for KisanMind.

Handles the full voice pipeline for Indian farmers:
  1. Speech-to-Text (multi-language)
  2. Intent & entity extraction (Gemini Flash)
  3. Routing to specialist agents
  4. Farmer-friendly response generation
  5. Text-to-Speech in the detected language

Guardrails:
  - Simple language, no technical jargon
  - Local units (quintal, bigha, acre)
  - Prices always in INR (rupaye)
  - Short, actionable sentences
"""

import base64
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from pydantic import BaseModel, Field

from agents.vaani_setu.intent_extractor import (
    FarmerIntent,
    IntentResult,
    extract_intent,
)
from agents.vaani_setu.stt_handler import STTResult, recognise_speech
from agents.vaani_setu.tts_handler import TTSResult, synthesise_speech

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class VoiceResponse(BaseModel):
    """End-to-end response for a farmer's voice query."""
    transcript: str = Field("", description="What the farmer said (text)")
    language: str = Field("hi-IN", description="Detected language")
    intent: str = Field("unknown", description="Detected intent")
    crop: Optional[str] = Field(None, description="Crop mentioned")
    location: Optional[str] = Field(None, description="Location mentioned")
    advisory_text: str = Field("", description="Farmer-friendly advisory")
    audio_base64: str = Field(
        "", description="Base64-encoded audio response"
    )
    audio_content_type: str = Field("audio/wav")
    needs_retry: bool = Field(False)
    retry_prompt: Optional[str] = Field(None)


# ---------------------------------------------------------------------------
# Agent guardrails (system instruction)
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
You are VaaniSetu, the voice interface of KisanMind, an agricultural advisory
system for Indian farmers.  You speak to farmers in their own language.

RULES — follow these strictly:
1. Use SIMPLE language a farmer with basic education can understand.
2. Use LOCAL UNITS: quintal (not tonnes), bigha or acre (not hectares),
   rupaye (not INR).
3. NEVER use English jargon like "NDVI", "spectral index", "regression model".
   Instead say "satellite se fasal ki haalat" or equivalent in their language.
4. Keep responses SHORT — 3 to 5 sentences maximum for a voice answer.
5. Always include ONE clear action the farmer should take.
6. When quoting prices, say "per quintal" and mention the mandi name.
7. Be respectful — address as "kisan bhai" / "kisan behan" or equivalent.
8. If you are unsure, say so honestly and suggest visiting the local KVK
   (Krishi Vigyan Kendra).
"""

# ---------------------------------------------------------------------------
# Tool functions (exposed to the ADK agent)
# ---------------------------------------------------------------------------


def process_voice_input(audio_base64: str) -> dict[str, Any]:
    """
    Process a farmer's voice input end-to-end.

    Decodes the base64 audio, runs speech-to-text, extracts intent and
    entities, and returns a structured result for the agent to act on.

    Args:
        audio_base64: Base64-encoded audio bytes from the client.

    Returns:
        Dictionary with transcript, intent, crop, location, language,
        and whether a retry is needed.
    """
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception:
        return {
            "error": "Invalid base64 audio",
            "needs_retry": True,
            "retry_prompt": "Audio not received properly. Please try again.",
        }

    # Step 1: Speech-to-Text
    stt_result: STTResult = recognise_speech(audio_bytes)

    if stt_result.needs_retry:
        return {
            "transcript": stt_result.transcript,
            "needs_retry": True,
            "retry_prompt": stt_result.retry_prompt,
            "language": stt_result.language_code,
        }

    # Step 2: Intent extraction
    intent_result: IntentResult = extract_intent(stt_result.transcript)

    return {
        "transcript": stt_result.transcript,
        "language": intent_result.language or stt_result.language_code,
        "intent": intent_result.intent.value,
        "crop": intent_result.crop,
        "raw_crop": intent_result.raw_crop,
        "location": intent_result.location,
        "confidence": intent_result.confidence,
        "needs_retry": False,
    }


def process_text_input(text: str, language: str = "hi-IN") -> dict[str, Any]:
    """
    Process a text transcript directly (skipping STT).

    Useful for chat/web interfaces where the farmer types or where
    STT was already performed upstream.

    Args:
        text: The farmer's query in any supported language.
        language: BCP-47 language hint (default hi-IN).

    Returns:
        Dictionary with intent, crop, location, language.
    """
    if not text or not text.strip():
        return {
            "transcript": "",
            "needs_retry": True,
            "retry_prompt": "Please tell us your question.",
            "language": language,
        }

    intent_result: IntentResult = extract_intent(text)

    return {
        "transcript": text,
        "language": intent_result.language or language,
        "intent": intent_result.intent.value,
        "crop": intent_result.crop,
        "raw_crop": intent_result.raw_crop,
        "location": intent_result.location,
        "confidence": intent_result.confidence,
        "needs_retry": False,
    }


def generate_voice_response(
    text: str,
    language: str = "hi-IN",
    output_format: str = "linear16",
    prices: Optional[list[str]] = None,
    action_items: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Convert an advisory text response into speech audio.

    Args:
        text: The farmer-friendly advisory text.
        language: BCP-47 language code for the voice.
        output_format: "linear16" for telephony, "mp3" for web.
        prices: Price strings to emphasise in speech.
        action_items: Action strings to emphasise in speech.

    Returns:
        Dictionary with base64 audio, content type, and metadata.
    """
    tts_result: TTSResult = synthesise_speech(
        text=text,
        language_code=language,
        output_format=output_format,
        prices=prices,
        action_items=action_items,
    )

    audio_b64 = ""
    if tts_result.audio_bytes:
        audio_b64 = base64.b64encode(tts_result.audio_bytes).decode("ascii")

    return {
        "audio_base64": audio_b64,
        "content_type": tts_result.content_type,
        "language": tts_result.language_code,
        "voice": tts_result.voice_name,
        "is_mock": tts_result.is_mock,
    }


def get_routing_target(intent: str) -> dict[str, str]:
    """
    Determine which specialist agent should handle the farmer's query.

    Args:
        intent: One of the FarmerIntent values.

    Returns:
        Dictionary with agent_name and description.
    """
    routing: dict[str, dict[str, str]] = {
        FarmerIntent.CROP_HEALTH_CHECK.value: {
            "agent": "sat_drishti",
            "description": "Satellite-based crop health analysis using NDVI and EVI indices",
        },
        FarmerIntent.WHERE_TO_SELL.value: {
            "agent": "mandi_mitra",
            "description": "Mandi price comparison and best-sell recommendations",
        },
        FarmerIntent.WEATHER_ADVISORY.value: {
            "agent": "mausam_guru",
            "description": "Weather forecast and farming advisory",
        },
        FarmerIntent.WHAT_TO_PLANT.value: {
            "agent": "brain",
            "description": "Crop recommendation based on soil, weather, and market data",
        },
        FarmerIntent.FULL_ADVISORY.value: {
            "agent": "brain",
            "description": "Comprehensive advisory combining all data sources",
        },
    }

    target = routing.get(intent, {
        "agent": "brain",
        "description": "General agricultural advisory",
    })

    return target


# ---------------------------------------------------------------------------
# ADK Agent definition
# ---------------------------------------------------------------------------

vaani_setu_agent = Agent(
    model="gemini-2.5-flash",
    name="vaani_setu",
    description=(
        "VaaniSetu (Voice Bridge) — handles voice input/output for Indian "
        "farmers, detects language and intent, routes to specialist agents, "
        "and responds in the farmer's own language with simple, actionable advice."
    ),
    instruction=_SYSTEM_INSTRUCTION,
    tools=[
        FunctionTool(process_voice_input),
        FunctionTool(process_text_input),
        FunctionTool(generate_voice_response),
        FunctionTool(get_routing_target),
    ],
)

# Convenience alias for ADK runner discovery
root_agent = vaani_setu_agent
