"""Deterministic speech metrics (Phase 8).

Every metric is computed here, in the backend, from faster-whisper's
timestamped word data plus the audio duration. Gemini never computes,
estimates, or adjusts a speech metric; downstream AI may only carefully
INTERPRET these measured values ("frequent long pauses", never
psychological claims - that rule lives in the report prompt).

Pure functions over plain data: identical inputs -> identical metrics
(replay-tested). Definitions (pipeline ``speech-metrics-1.0.0``):

  * speaking_duration  - sum of word spans (end - start).
  * words_per_minute   - word_count / speaking minutes.
  * pause              - gap between consecutive words > 0.30s;
    long pause > 1.50s. avg/max computed over pauses.
  * filler words       - membership in a fixed lexicon (um, uh, er, ah,
    mm, hmm, uhm, erm) plus the bigram "you know"; frequency is fillers
    per 100 recognized words.
  * hesitation_count   - fillers + immediate word repetitions
    ("I - I built...").
  * silence_duration   - audio duration minus speaking duration (>= 0).
  * speech_completeness- speaking/audio ratio clamped to [0, 1].
  * response_duration  - the full audio duration.
  * answer_char_length - transcript length in characters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SPEECH_METRICS_VERSION = "speech-metrics-1.0.0"

PAUSE_THRESHOLD_SECONDS = 0.30
LONG_PAUSE_THRESHOLD_SECONDS = 1.50

_FILLER_WORDS = frozenset({"um", "uh", "er", "ah", "mm", "hmm", "uhm", "erm"})
_WORD_CLEAN_PATTERN = re.compile(r"[^a-z']+")


@dataclass(frozen=True)
class TimedWord:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class SpeechMetrics:
    speaking_duration_seconds: float
    word_count: int
    words_per_minute: float
    long_pause_count: int
    avg_pause_duration_seconds: float
    max_pause_duration_seconds: float
    filler_word_count: int
    filler_word_frequency: float
    hesitation_count: int
    silence_duration_seconds: float
    response_duration_seconds: float
    answer_char_length: int
    speech_completeness: float
    version: str = SPEECH_METRICS_VERSION


def _clean(word: str) -> str:
    return _WORD_CLEAN_PATTERN.sub("", word.casefold())


def compute_speech_metrics(
    words: list[TimedWord], *, audio_duration_seconds: float, transcript: str
) -> SpeechMetrics:
    """Compute all metrics deterministically. ``words`` must be in time
    order (faster-whisper emits them ordered); empty input yields honest
    zeros rather than errors - the transcription layer already rejected
    empty transcripts before metrics run."""
    audio_duration = max(audio_duration_seconds, 0.0)
    speaking = sum(max(word.end - word.start, 0.0) for word in words)
    word_count = len(words)

    pauses: list[float] = []
    for previous, current in zip(words, words[1:], strict=False):
        gap = current.start - previous.end
        if gap > PAUSE_THRESHOLD_SECONDS:
            pauses.append(gap)
    long_pauses = [gap for gap in pauses if gap > LONG_PAUSE_THRESHOLD_SECONDS]

    cleaned = [_clean(word.word) for word in words]
    fillers = sum(1 for token in cleaned if token in _FILLER_WORDS)
    fillers += sum(
        1
        for previous, current in zip(cleaned, cleaned[1:], strict=False)
        if previous == "you" and current == "know"
    )
    repetitions = sum(
        1
        for previous, current in zip(cleaned, cleaned[1:], strict=False)
        if previous and previous == current and previous not in _FILLER_WORDS
    )

    wpm = (word_count / (speaking / 60.0)) if speaking > 0 else 0.0
    return SpeechMetrics(
        speaking_duration_seconds=round(speaking, 3),
        word_count=word_count,
        words_per_minute=round(wpm, 2),
        long_pause_count=len(long_pauses),
        avg_pause_duration_seconds=round(sum(pauses) / len(pauses), 3) if pauses else 0.0,
        max_pause_duration_seconds=round(max(pauses), 3) if pauses else 0.0,
        filler_word_count=fillers,
        filler_word_frequency=round(fillers * 100.0 / word_count, 2) if word_count else 0.0,
        hesitation_count=fillers + repetitions,
        silence_duration_seconds=round(max(audio_duration - speaking, 0.0), 3),
        response_duration_seconds=round(audio_duration, 3),
        answer_char_length=len(transcript),
        speech_completeness=(
            round(min(max(speaking / audio_duration, 0.0), 1.0), 3)
            if audio_duration > 0
            else 0.0
        ),
    )
