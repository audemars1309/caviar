"""Text-to-speech provider abstraction (Phase 8).

``TTSProvider`` is a Protocol; interview logic depends on it (and only
optionally - a TTS failure degrades to text-only, never breaks the
interview cycle). ``KokoroTTSProvider`` (pinned ``kokoro>=0.9,<1.0`` plus
``soundfile`` in the optional ``[tts]`` extra - validated against PyPI
July 2026, kokoro 0.9.4) lazily imports its heavy dependencies (torch);
absence is a typed ``TTSUnavailableError``.

Streaming-ready by construction: Kokoro's pipeline yields audio in
chunks and ``_synthesize_sync`` consumes that chunk stream; v1 returns
one concatenated WAV (the current API is request/response), and a future
streaming endpoint can consume the same chunk iterator without touching
interview logic - which is exactly the decoupling the spec requires.
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import status

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_KOKORO_SAMPLE_RATE = 24_000
_MAX_TTS_CHARS = 1_000


class TTSUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "tts_unavailable"


class TTSFailedError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "tts_failed"


@dataclass(frozen=True)
class TTSResult:
    audio_wav: bytes
    sample_rate: int
    voice: str
    provider: str


class TTSProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult: ...


class KokoroTTSProvider:
    """Local Kokoro inference behind the TTSProvider Protocol."""

    def __init__(
        self, *, default_voice: str, lang_code: str, timeout_seconds: float
    ) -> None:
        self._default_voice = default_voice
        self._lang_code = lang_code
        self._timeout = timeout_seconds
        self._pipeline: Any = None

    def _load_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from kokoro import KPipeline  # lazy heavy import (torch)
            except ImportError as exc:
                raise TTSUnavailableError(
                    "Speech synthesis is not available on this deployment "
                    "(install the [tts] extra)."
                ) from exc
            try:
                self._pipeline = KPipeline(lang_code=self._lang_code)
            except Exception as exc:
                logger.error("Kokoro pipeline load failed: %s", exc.__class__.__name__)
                raise TTSUnavailableError("The TTS model could not be loaded.") from exc
        return self._pipeline

    def _synthesize_sync(self, text: str, voice: str) -> TTSResult:
        pipeline = self._load_pipeline()
        try:
            import numpy as np
            import soundfile as sf

            # The pipeline yields audio chunk-by-chunk (streaming-ready);
            # v1 concatenates the chunk stream into one WAV.
            chunks = [audio for _, _, audio in pipeline(text, voice=voice)]
            if not chunks:
                raise TTSFailedError("The TTS engine produced no audio.")
            buffer = io.BytesIO()
            sf.write(buffer, np.concatenate(chunks), _KOKORO_SAMPLE_RATE, format="WAV")
        except TTSFailedError:
            raise
        except Exception as exc:
            logger.error("Kokoro synthesis failed: %s", exc.__class__.__name__)
            raise TTSFailedError("Speech synthesis failed.") from exc
        return TTSResult(
            audio_wav=buffer.getvalue(),
            sample_rate=_KOKORO_SAMPLE_RATE,
            voice=voice,
            provider="kokoro",
        )

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:
        # Length cap: interviewer turns are short by design; this also
        # bounds synthesis time.
        trimmed = text.strip()[:_MAX_TTS_CHARS]
        if not trimmed:
            raise TTSFailedError("Nothing to synthesize.")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, trimmed, voice or self._default_voice),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise TTSFailedError("Speech synthesis timed out.") from exc
