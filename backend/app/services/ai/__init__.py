"""Centralized AI integration layer (Phase 4).

ALL Gemini access in Caviar goes through this package - route modules and
domain services never import the google-genai SDK directly. The package
provides: typed AI exceptions, task-based model routing, prompt trust
boundaries for untrusted content, strict Pydantic output schemas, and a
structured-output runner with exactly one bounded repair attempt.
"""
