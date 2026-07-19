# Caviar Backend

Current phase: **Phase 8 complete** - the Interview Intelligence
System: recoverable 7-state session lifecycle (PENDING/READY/RUNNING/
PAUSED/COMPLETED/FAILED/CANCELLED) with `current_question_id` recovery;
a backend-owned state machine over the approved stage taxonomy
(deterministic per-type stage plans and largest-remainder question-budget
allocation, forward-only transitions, per-stage allowed-action tables,
follow-up loop guard) where Gemini recommendations are validated inputs
the engine can override; structured bounded interview memory (never
concatenated prompt history); faster-whisper transcription behind a
`TranscriptionProvider` Protocol (lazy optional `[speech]` extra, CPU/GPU
via settings, word timestamps + language detection, typed
unavailable/failed/timeout/empty/unsupported/too-large errors) with
deterministic backend speech metrics (`speech-metrics-1.0.0`: WPM,
pauses, fillers, hesitations, silence, completeness - Gemini computes
none of them); centralized Gemini answer evaluation
(`answer-evaluation-1.0.0`, all 8 criteria validated, backend
profile-filters applicability by question type, one bounded repair);
adaptive questioning with deterministic duplicate prevention (normalized
no-repeat set, one regeneration, deterministic stage fallback - AI
failure never strands a session); deterministic readiness calculation
(`interview-readiness-1.0.0`: difficulty-weighted, outlier-trimmed,
NULL-excluding category aggregation with backend weights - Gemini never
computes the score); Kokoro TTS behind a `TTSProvider` Protocol
(optional `[tts]` extra; failure degrades to text); and structured
interview reports (deterministic timeline/topic-coverage/question-history/
speech summary + readiness categories, resilient AI narrative). Answers
are persisted before any AI call; evaluation failure preserves the
transcript and resubmission replaces the unevaluated attempt. Migration
head: `0010_interview_engine`.

**Speech extras:** `pip install -e ".[speech]"` enables transcription,
`pip install -e ".[tts]"` enables the interviewer voice; both models
download from Hugging Face on first use and run locally (0 API cost).
Without the extras, audio endpoints return typed 503s and text-mode
interviews work fully.

Built on: Phase 7 (LaTeX generation), Phase 6 (Resume Builder), Phase 5
(scoring engine), Phase 4 (Gemini integration), Phase 3 (upload/
extraction), Phase 2 (schema, auth, RLS), Phase 1 (foundation).

## Setup

Run all commands below from this `backend/` directory.

```
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000`
Docs (development only): `http://127.0.0.1:8000/api/v1/docs`

## Tests

```
python -m pytest -v
```
