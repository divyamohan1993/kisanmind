"""
Intent and entity extraction for VaaniSetu.

Uses Gemini 2.5 Flash to quickly parse a farmer's transcript and extract
structured intent, location, crop, and language information.
"""

import enum
import logging
from typing import Optional

import google.generativeai as genai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & models
# ---------------------------------------------------------------------------


class FarmerIntent(str, enum.Enum):
    """Recognised intents from a farmer's voice query."""
    CROP_HEALTH_CHECK = "crop_health_check"
    WHERE_TO_SELL = "where_to_sell"
    WEATHER_ADVISORY = "weather_advisory"
    WHAT_TO_PLANT = "what_to_plant"
    FULL_ADVISORY = "full_advisory"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    """Structured extraction from a farmer's transcript."""
    intent: FarmerIntent = Field(
        FarmerIntent.UNKNOWN,
        description="The primary intent detected in the transcript",
    )
    crop: Optional[str] = Field(
        None,
        description="English-normalised crop name (e.g. 'tomato', 'wheat')",
    )
    location: Optional[str] = Field(
        None,
        description="Location mentioned (district, village, or state)",
    )
    language: str = Field(
        "hi-IN",
        description="BCP-47 language code detected in the transcript",
    )
    raw_crop: Optional[str] = Field(
        None,
        description="Original crop name as spoken by the farmer",
    )
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score",
    )


# ---------------------------------------------------------------------------
# Crop-name normalisation (Hindi / regional -> English)
# ---------------------------------------------------------------------------

CROP_NAME_MAP: dict[str, str] = {
    # Hindi
    "tamatar": "tomato",
    "tamaatar": "tomato",
    "gehun": "wheat",
    "gehu": "wheat",
    "chawal": "rice",
    "dhaan": "rice",
    "seb": "apple",
    "coffee": "coffee",
    "chai": "tea",
    "aloo": "potato",
    "aaloo": "potato",
    "pyaaz": "onion",
    "pyaj": "onion",
    "mirch": "chilli",
    "mirchi": "chilli",
    "kapas": "cotton",
    "ganna": "sugarcane",
    "sarson": "mustard",
    "chana": "chickpea",
    "dal": "lentil",
    "daal": "lentil",
    "makka": "maize",
    "makkai": "maize",
    "jowar": "sorghum",
    "bajra": "pearl millet",
    "moong": "mung bean",
    "urad": "black gram",
    "til": "sesame",
    "soyabean": "soybean",
    "aam": "mango",
    "kela": "banana",
    "nimbu": "lemon",
    "bhindi": "okra",
    "baingan": "eggplant",
    "gobhi": "cauliflower",
    "palak": "spinach",
    "matar": "peas",
    # Tamil
    "thakkali": "tomato",
    "nel": "rice",
    # Telugu
    "tomato": "tomato",
    "godhuma": "wheat",
    # Already English
    "wheat": "wheat",
    "rice": "rice",
    "apple": "apple",
    "tomato": "tomato",
    "potato": "potato",
    "onion": "onion",
    "cotton": "cotton",
    "sugarcane": "sugarcane",
    "maize": "maize",
    "sorghum": "sorghum",
    "mango": "mango",
}


def normalise_crop(name: Optional[str]) -> Optional[str]:
    """Map a crop name (any language) to its English equivalent."""
    if not name:
        return None
    key = name.strip().lower()
    return CROP_NAME_MAP.get(key, key)


# ---------------------------------------------------------------------------
# Gemini-based extraction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an intent extraction engine for an Indian agricultural advisory system
called KisanMind.  Given a farmer's transcript (possibly in Hindi, Tamil, Telugu,
Bengali, Kannada, Malayalam, Marathi, Gujarati, or English), extract:

1. **intent** — one of: crop_health_check, where_to_sell, weather_advisory,
   what_to_plant, full_advisory, unknown
2. **crop** — the crop name as spoken (original language)
3. **location** — village, district, or state mentioned
4. **language** — the BCP-47 code of the transcript language
   (hi-IN, ta-IN, te-IN, bn-IN, kn-IN, ml-IN, mr-IN, gu-IN, en-IN)
5. **confidence** — 0.0 to 1.0, how sure you are about the extraction

Respond ONLY with valid JSON, no markdown fences:
{"intent": "...", "crop": "...", "location": "...", "language": "...", "confidence": 0.9}

If a field is not found, set it to null.  Always include all five keys.
"""

_model: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    """Lazy-initialise the Gemini model."""
    global _model
    if _model is None:
        _model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_SYSTEM_PROMPT,
        )
    return _model


def extract_intent(transcript: str) -> IntentResult:
    """
    Extract intent and entities from a farmer's voice transcript.

    Uses Gemini 2.5 Flash for fast, multilingual understanding.  Falls back
    to a basic UNKNOWN result if the API call fails.
    """
    if not transcript or not transcript.strip():
        logger.warning("Empty transcript received")
        return IntentResult()

    try:
        model = _get_model()
        response = model.generate_content(
            f"Farmer said: \"{transcript}\"",
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        import json
        raw = response.text.strip()
        # Strip markdown fences if model includes them despite instructions
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)

        raw_crop = data.get("crop")
        english_crop = normalise_crop(raw_crop)

        intent_str = data.get("intent", "unknown")
        try:
            intent = FarmerIntent(intent_str)
        except ValueError:
            intent = FarmerIntent.UNKNOWN

        return IntentResult(
            intent=intent,
            crop=english_crop,
            raw_crop=raw_crop,
            location=data.get("location"),
            language=data.get("language", "hi-IN"),
            confidence=float(data.get("confidence", 0.5)),
        )

    except Exception as exc:
        logger.error("Intent extraction failed: %s", exc, exc_info=True)
        # Return a safe fallback so the caller can still function
        return IntentResult(
            intent=FarmerIntent.UNKNOWN,
            language="hi-IN",
            confidence=0.0,
        )
