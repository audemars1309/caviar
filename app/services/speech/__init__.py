"""Speech services (Phase 8): transcription provider abstraction
(faster-whisper), deterministic speech metrics, and the TTS provider
abstraction (Kokoro). Providers are replaceable behind Protocols and
lazily import their heavy ML dependencies (optional extras [speech] and
[tts]); absence surfaces as typed unavailability errors, never crashes."""
