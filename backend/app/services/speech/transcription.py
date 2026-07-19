"""Speech-to-text provider abstraction (Phase 8).

``TranscriptionProvider`` is a Protocol; the interview pipeline depends
on it, never on faster-whisper directly, so providers are replaceable
(and tests inject fakes through the same seam production wiring uses).

``FasterWhisperProvider`` (pinned ``faster-whisper>=1.2,<2.0`` with
``ctranslate2>=4.5,<5.0`` in the optional ``[speech]`` extra - validated
against PyPI July 2026) lazily imports its heavy ML dependency: absence
surfaces as a typed ``TranscriptionUnavailableError`` (503), never an
import crash at app startup. It supports CPU and GPU through settings
(``WHISPER_DEVICE=cpu|cuda|auto``, with compute type per device), word
timestamps, language detection with probability, and per-word confidence.
Long recordings are handled by faster-whisper's internal VAD-based
segmentation; Caviar additionally caps accepted audio duration and size
upstream. Inference runs in a worker thread under ``asyncio.wait_for``
so a hung model cannot block the event loop (typed timeout).

Audio validation (before any decode): size cap, then magic-byte
detection for the accepted container formats (wav/webm/ogg/mp3/m4a).
Declared MIME is advisory only. Corrupt-but-well-magicked audio fails
inside decode and maps to ``TranscriptionFailedError``; an audio stream
that decodes to no recognized words raises ``EmptyTranscriptError``.
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import status

from app.core.exceptions import AppError, ValidationFailedError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------ exceptions


class TranscriptionUnavailableError(AppError):
    """The transcription provider (library/model) is not available."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "transcription_unavailable"


class TranscriptionFailedError(AppError):
    """Decoding or inference failed (corrupt audio, model error)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "transcription_failed"


class TranscriptionTimeoutError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "transcription_timeout"


class EmptyTranscriptError(AppError):
    """Structurally valid audio containing no recognizable speech."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "empty_transcript"


class UnsupportedAudioFormatError(ValidationFailedError):
    error_code = "unsupported_audio_format"


class AudioTooLargeError(ValidationFailedError):
    error_code = "audio_too_large"


# ---------------------------------------------------------------- types


@dataclass(frozen=True)
class TranscribedWord:
    word: str
    start: float
    end: float
    probability: float


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    audio_duration_seconds: float
    words: tuple[TranscribedWord, ...] = field(default_factory=tuple)
    provider: str = "unknown"


class TranscriptionProvider(Protocol):
    async def transcribe(self, content: bytes) -> TranscriptionResult: ...


# ------------------------------------------------------ audio validation

_AUDIO_MAGIC: tuple[tuple[bytes, int, str], ...] = (
    (b"RIFF", 0, "wav"),
    (b"\x1a\x45\xdf\xa3", 0, "webm"),
    (b"OggS", 0, "ogg"),
    (b"ID3", 0, "mp3"),
    (b"\xff\xfb", 0, "mp3"),
    (b"\xff\xf3", 0, "mp3"),
    (b"ftyp", 4, "m4a"),
)


def validate_answer_audio(content: bytes, *, max_bytes: int) -> str:
    """Reject empty/oversized/unrecognized audio before any decode.
    Returns the detected container format."""
    if not content:
        raise UnsupportedAudioFormatError("The uploaded audio is empty.")
    if len(content) > max_bytes:
        raise AudioTooLargeError(
            f"The audio exceeds the maximum allowed size of {max_bytes} bytes.",
            details={"max_bytes": max_bytes},
        )
    for magic, offset, container in _AUDIO_MAGIC:
        if content[offset : offset + len(magic)] == magic:
            return container
    raise UnsupportedAudioFormatError(
        "Unsupported audio format. Supported containers: wav, webm, ogg, mp3, m4a."
    )


# ------------------------------------------------- faster-whisper provider


class FasterWhisperProvider:
    """CPU/GPU local inference via faster-whisper (CTranslate2)."""

    def __init__(
        self,
        *,
        model_size: str,
        device: str,
        compute_type: str | None,
        timeout_seconds: float,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type or ("float16" if device == "cuda" else "int8")
        self._timeout = timeout_seconds
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # lazy heavy import
            except ImportError as exc:
                raise TranscriptionUnavailableError(
                    "Speech transcription is not available on this deployment "
                    "(install the [speech] extra)."
                ) from exc
            try:
                self._model = WhisperModel(
                    self._model_size, device=self._device, compute_type=self._compute_type
                )
            except Exception as exc:
                logger.error("Whisper model load failed: %s", exc.__class__.__name__)
                raise TranscriptionUnavailableError(
                    "The transcription model could not be loaded."
                ) from exc
        return self._model

    def _transcribe_sync(self, content: bytes) -> TranscriptionResult:
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                io.BytesIO(content), word_timestamps=True, vad_filter=True
            )
            words: list[TranscribedWord] = []
            texts: list[str] = []
            for segment in segments:  # generator: iteration performs inference
                texts.append(segment.text)
                for word in segment.words or []:
                    words.append(
                        TranscribedWord(
                            word=word.word.strip(),
                            start=float(word.start),
                            end=float(word.end),
                            probability=float(word.probability),
                        )
                    )
        except Exception as exc:
            logger.info("Transcription failed: %s", exc.__class__.__name__)
            raise TranscriptionFailedError(
                "The audio could not be transcribed. It may be corrupt or unreadable."
            ) from exc

        text = " ".join(part.strip() for part in texts if part.strip()).strip()
        if not text or not words:
            raise EmptyTranscriptError("No speech was recognized in the audio.")
        return TranscriptionResult(
            text=text,
            language=info.language,
            language_probability=float(info.language_probability),
            audio_duration_seconds=float(info.duration),
            words=tuple(words),
            provider=f"faster-whisper/{self._model_size}/{self._device}",
        )

    async def transcribe(self, content: bytes) -> TranscriptionResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._transcribe_sync, content), timeout=self._timeout
            )
        except TimeoutError as exc:
            raise TranscriptionTimeoutError(
                "Transcription timed out. Try a shorter recording."
            ) from exc
