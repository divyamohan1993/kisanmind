"""
Speech-to-Text handler for VaaniSetu.

Uses Google Cloud Speech-to-Text V2 configured for Indian-language
telephony audio.  Raises an error when cloud
credentials are unavailable (local development).
"""

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class STTResult(BaseModel):
    """Result from a speech-to-text recognition attempt."""
    transcript: str = Field("", description="Recognised text")
    language_code: str = Field(
        "hi-IN", description="Detected language (BCP-47)"
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    needs_retry: bool = Field(
        False,
        description="True when confidence is too low and the caller should "
        "ask the farmer to repeat",
    )
    retry_prompt: Optional[str] = Field(
        None,
        description="Localised prompt asking the farmer to repeat",
    )


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: list[str] = [
    "hi-IN",  # Hindi
    "ta-IN",  # Tamil
    "te-IN",  # Telugu
    "bn-IN",  # Bengali
    "kn-IN",  # Kannada
    "ml-IN",  # Malayalam
    "mr-IN",  # Marathi
    "gu-IN",  # Gujarati
    "en-IN",  # Indian English
]

CONFIDENCE_THRESHOLD = 0.6

# Retry prompts per language (farmer-friendly)
_RETRY_PROMPTS: dict[str, str] = {
    "hi-IN": "Maaf kijiye, aapki baat samajh nahi aayi. Kripya dobara bataiye.",
    "ta-IN": "Mannikavum, puriyavillai. Thayavu seidhu meendum sollunga.",
    "te-IN": "Kshaminchanḍi, artham kaaledu. Dayachesi malli cheppandi.",
    "bn-IN": "Dukkhito, bujhte parlam na. Dayakore abar bolun.",
    "kn-IN": "Kshamisi, arthaagalilla. Dayavittu matte heli.",
    "ml-IN": "Kshamikkuka, manasilaayilla. Dayavayi veendum parayuka.",
    "mr-IN": "Maaf kara, samajla nahi. Krupaya punha sangaa.",
    "gu-IN": "Maaf karjo, samajayun nathi. Maherbani kari farthi kaheju.",
    "en-IN": "Sorry, I could not understand. Could you please repeat?",
}


# ---------------------------------------------------------------------------
# Cloud STT V2 implementation
# ---------------------------------------------------------------------------


def _recognise_cloud(audio_bytes: bytes) -> STTResult:
    """
    Run recognition using Google Cloud Speech-to-Text V2.

    Configures the telephony model with automatic language detection
    across all supported Indian languages.
    """
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "dmjone")
    location = os.environ.get("STT_LOCATION", "global")

    client = SpeechClient()
    parent = f"projects/{project_id}/locations/{location}"

    # Build recogniser config for Indian telephony
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=SUPPORTED_LANGUAGES,
        model="telephony",
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
        ),
    )

    request = cloud_speech.RecognizeRequest(
        recognizer=f"{parent}/recognizers/_",
        config=config,
        content=audio_bytes,
    )

    response = client.recognize(request=request)

    if not response.results:
        return STTResult(
            transcript="",
            confidence=0.0,
            needs_retry=True,
            retry_prompt=_RETRY_PROMPTS["hi-IN"],
        )

    top = response.results[0].alternatives[0]
    detected_lang = (
        response.results[0].language_code
        if response.results[0].language_code
        else "hi-IN"
    )

    # Normalise language code to our format (e.g. "hi-in" -> "hi-IN")
    if len(detected_lang) == 5 and detected_lang[2] == "-":
        detected_lang = f"{detected_lang[:2].lower()}-{detected_lang[3:].upper()}"

    confidence = top.confidence

    if confidence < CONFIDENCE_THRESHOLD:
        retry = _RETRY_PROMPTS.get(detected_lang, _RETRY_PROMPTS["hi-IN"])
        return STTResult(
            transcript=top.transcript,
            language_code=detected_lang,
            confidence=confidence,
            needs_retry=True,
            retry_prompt=retry,
        )

    return STTResult(
        transcript=top.transcript,
        language_code=detected_lang,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recognise_speech(audio_bytes: bytes) -> STTResult:
    """
    Transcribe *audio_bytes* to text with language detection.

    Uses the Cloud Speech V2 API. Raises RuntimeError if the service
    is unavailable.

    Parameters
    ----------
    audio_bytes:
        Raw audio data (LINEAR16, MULAW, or MP3).

    Returns
    -------
    STTResult with transcript, detected language, and confidence.
    """
    if not audio_bytes:
        return STTResult(
            transcript="",
            confidence=0.0,
            needs_retry=True,
            retry_prompt=_RETRY_PROMPTS["hi-IN"],
        )

    try:
        return _recognise_cloud(audio_bytes)
    except Exception as exc:
        logger.error("Cloud STT unavailable: %s", exc)
        raise RuntimeError(f"Speech-to-text service unavailable: {exc}") from exc
