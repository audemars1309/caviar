# Interview System Guide

The Adaptive AI Interviewer is a **stateful orchestration engine**, not a
chatbot. Gemini assists; the backend owns state and scoring.

## Session lifecycle

Seven states: `PENDING → READY → RUNNING → PAUSED → COMPLETED`, plus
`FAILED` and `CANCELLED`. Transitions are forward-only and validated by the
backend; a session survives individual service failures.

## Stage machine

Fixed stages: introduction, candidate background, resume discussion, project
deep dive, role-specific, behavioral, adaptive probing, closing, completed.
The engine controls transitions using deterministic per-type stage plans and
a largest-remainder question-budget allocation. Gemini may *recommend* an
action from a fixed enum; the backend validates whether it is allowed in the
current stage and **can override it**.

## Answer cycle & audio flow

1. The browser records audio (MediaRecorder → webm/opus). It performs **no
   speech processing**.
2. The clip is POSTed to the backend (exactly one of audio or text per
   answer; 25 MiB cap validated by magic bytes).
3. faster-whisper transcribes with word timestamps.
4. **The backend computes deterministic speech metrics**
   (`speech-metrics-1.0.0`: WPM, pauses, fillers, hesitations, silence,
   completeness). Gemini computes none of them and makes no psychological or
   medical claims.
5. The answer + transcript are persisted **before** any AI call.
6. Gemini evaluates the answer (`answer-evaluation-1.0.0`, validated); the
   backend orchestration decides the next action; Gemini drafts the next
   question; optional Kokoro TTS is returned (`?include_audio=true`).

Resilience: if TTS fails, text is still returned; if evaluation fails, the
transcript is preserved and the attempt can be resubmitted; invalid AI output
triggers one bounded repair. A single failure never strands the session.

## Interviewer Observation

A short, evidence-based, user-facing note (e.g. "explains the architecture
but not the candidate's personal contribution"). It is **not** chain-of-
thought and never exposes hidden model reasoning.

## Report

Deterministic components (timeline, topic coverage, question history, speech
summary, and readiness categories aggregated by `interview-readiness-1.0.0`:
difficulty-weighted, outlier-trimmed, NULL-excluding) plus a **resilient AI
narrative** (overview, technical/behavioral observations, strongest/weakest
answers, improvement roadmap). If the narrative call fails, the deterministic
report still stands and is clearly marked. The frontend renders everything
read-only and offers browser print-to-PDF.
