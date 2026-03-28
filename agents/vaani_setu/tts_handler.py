"""
Text-to-Speech handler for VaaniSetu.

Uses Google Cloud Text-to-Speech with Neural2 voices, tuned for
clarity over Indian telephone networks.  Falls back to empty audio
when cloud credentials are unavailable.
"""

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TTSResult(BaseModel):
    """Result from a text-to-speech synthesis attempt."""
    audio_bytes: bytes = Field(default=b"", description="Synthesised audio")
    content_type: str = Field(
        "audio/wav",
        description="MIME type of the audio (audio/wav or audio/mpeg)",
    )
    language_code: str = Field("hi-IN")
    voice_name: str = Field("")
    is_mock: bool = Field(
        False, description="True if audio was not actually synthesised"
    )

    class Config:
        # Allow bytes field in Pydantic V2
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Voice mapping (language -> Neural2 voice)
# ---------------------------------------------------------------------------

VOICE_MAP: dict[str, str] = {
    "hi-IN": "hi-IN-Neural2-D",
    "ta-IN": "ta-IN-Neural2-D",
    "te-IN": "te-IN-Neural2-D",
    "bn-IN": "bn-IN-Neural2-D",
    "kn-IN": "kn-IN-Neural2-D",
    "ml-IN": "ml-IN-Neural2-D",
    "mr-IN": "mr-IN-Neural2-D",
    "gu-IN": "gu-IN-Neural2-D",
    "en-IN": "en-IN-Neural2-D",
}

# Speaking rate optimised for rural phone audio
SPEAKING_RATE = 0.85

# Pitch (slight lower for gravitas/clarity)
PITCH = -1.0


# ---------------------------------------------------------------------------
# SSML helpers
# ---------------------------------------------------------------------------


def wrap_ssml(
    text: str,
    prices: Optional[list[str]] = None,
    action_items: Optional[list[str]] = None,
) -> str:
    """
    Wrap *text* in SSML, emphasising prices and action items.

    Parameters
    ----------
    text:
        Plain-text advisory to convert.
    prices:
        Substrings representing price info (e.g. "2400 rupaye per quintal").
        These are wrapped in ``<emphasis>`` and a brief pause is inserted.
    action_items:
        Key action phrases to emphasise (e.g. "kal subah spray karein").
    """
    ssml = text

    # Emphasise prices
    for price in prices or []:
        if price in ssml:
            ssml = ssml.replace(
                price,
                f'<break time="300ms"/><emphasis level="strong">{price}</emphasis><break time="300ms"/>',
            )

    # Emphasise action items
    for action in action_items or []:
        if action in ssml:
            ssml = ssml.replace(
                action,
                f'<emphasis level="moderate">{action}</emphasis>',
            )

    return f"<speak>{ssml}</speak>"


# ---------------------------------------------------------------------------
# Cloud TTS implementation
# ---------------------------------------------------------------------------


def _synthesise_cloud(
    text: str,
    language_code: str,
    output_format: str,
    use_ssml: bool,
) -> TTSResult:
    """Synthesise speech using Google Cloud Text-to-Speech."""
    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()

    voice_name = VOICE_MAP.get(language_code, VOICE_MAP["hi-IN"])
    if language_code not in VOICE_MAP:
        logger.warning(
            "No Neural2 voice for %s, falling back to hi-IN", language_code
        )
        language_code = "hi-IN"

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
    )

    # Audio encoding
    if output_format == "mp3":
        encoding = texttospeech.AudioEncoding.MP3
        content_type = "audio/mpeg"
    else:
        # LINEAR16 for telephony (IVR / Twilio / Exotel)
        encoding = texttospeech.AudioEncoding.LINEAR16
        content_type = "audio/wav"

    audio_config = texttospeech.AudioConfig(
        audio_encoding=encoding,
        speaking_rate=SPEAKING_RATE,
        pitch=PITCH,
        sample_rate_hertz=8000 if output_format != "mp3" else 24000,
    )

    # Build synthesis input
    if use_ssml:
        synthesis_input = texttospeech.SynthesisInput(ssml=text)
    else:
        synthesis_input = texttospeech.SynthesisInput(text=text)

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    return TTSResult(
        audio_bytes=response.audio_content,
        content_type=content_type,
        language_code=language_code,
        voice_name=voice_name,
    )


# ---------------------------------------------------------------------------
# Mock / demo fallback
# ---------------------------------------------------------------------------


def _synthesise_mock(
    text: str,
    language_code: str,
    output_format: str,
) -> TTSResult:
    """
    Return an empty audio payload when cloud credentials are unavailable.

    The transcript text is logged so developers can verify the output.
    """
    logger.info(
        "Using mock TTS (no cloud credentials). lang=%s, text_len=%d",
        language_code,
        len(text),
    )
    content_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"
    return TTSResult(
        audio_bytes=b"",
        content_type=content_type,
        language_code=language_code,
        voice_name=VOICE_MAP.get(language_code, "mock"),
        is_mock=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def synthesise_speech(
    text: str,
    language_code: str = "hi-IN",
    output_format: str = "linear16",
    prices: Optional[list[str]] = None,
    action_items: Optional[list[str]] = None,
) -> TTSResult:
    """
    Convert *text* to speech audio in the given language.

    Parameters
    ----------
    text:
        The advisory text to speak.  Can be plain text or already SSML.
    language_code:
        BCP-47 code (e.g. ``hi-IN``).
    output_format:
        ``"linear16"`` for telephony (WAV 8 kHz) or ``"mp3"`` for web.
    prices:
        Price substrings to emphasise via SSML.
    action_items:
        Action substrings to emphasise via SSML.

    Returns
    -------
    TTSResult with audio bytes and metadata.
    """
    if not text or not text.strip():
        logger.warning("Empty text received for TTS")
        return TTSResult(language_code=language_code, is_mock=True)

    # Decide whether to use SSML
    use_ssml = False
    synth_text = text

    if prices or action_items:
        synth_text = wrap_ssml(text, prices=prices, action_items=action_items)
        use_ssml = True
    elif text.strip().startswith("<speak>"):
        use_ssml = True

    try:
        return _synthesise_cloud(synth_text, language_code, output_format, use_ssml)
    except Exception as exc:
        logger.warning(
            "Cloud TTS unavailable (%s), falling back to mock", exc
        )
        return _synthesise_mock(text, language_code, output_format)
