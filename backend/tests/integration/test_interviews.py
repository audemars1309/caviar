"""Integration tests for the Phase 8 Interview Intelligence System over
HTTP against a real, migrated Postgres with RLS enforced. Conventions
match the earlier integration suites. Externals are replaced through
their production seams only: Supabase Storage (fake via
``get_storage_client`` - needed to upload the resume the interview is
grounded in), Gemini (scripted raw client behind the REAL
StructuredAIRunner - validation/repair logic runs for real), and the
transcription/TTS providers (fakes via ``get_transcription_provider`` /
``get_tts_provider``).

Proven here beyond the unit suites:
  1. Full lifecycle: create (grounded in an EXTRACTED resume + job
     context) -> start -> text answer cycle (evaluation persisted with
     profile-filtered NULL criteria, memory deterministically updated,
     next question persisted) -> audio answer (fake transcription ->
     real deterministic speech metrics persisted) -> pause -> resume
     (recovery returns the pending question) -> forced completion at the
     question budget -> report with deterministic readiness categories +
     AI narrative.
  2. Resilience: evaluation AI failure preserves the answer
     (TRANSCRIBED) and resubmission works; narrative AI failure still
     persists the deterministic report (narrative_unavailable).
  3. Rules over HTTP: unextracted resume -> 409; illegal transitions ->
     409; TTS failure degrades to text with a warning.
  4. Cross-user isolation across every interview route.
"""

from __future__ import annotations

import json
import time
import uuid

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.ai.client import StructuredAIRunner, get_ai_runner
from app.services.ai.exceptions import AIProviderUnavailableError
from app.services.speech.transcription import TranscribedWord, TranscriptionResult
from app.services.speech.tts import TTSFailedError, TTSResult
from app.services.storage.supabase_storage import (
    StorageObjectNotFoundError,
    get_storage_client,
)
from tests.fixtures.pdf_fixtures import build_resume_pdf, build_textless_pdf
from tests.unit.test_interview_prompts_and_speech import make_valid_evaluation_dict

_TEST_SECRET = "integration-test-secret-0123456789abcdef"

pytestmark = pytest.mark.asyncio


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    settings = get_settings()
    return pyjwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.SUPABASE_JWT_AUDIENCE,
            "iss": settings.resolved_jwt_issuer or "https://test.local/auth/v1",
            "iat": now - 10,
            "exp": now + 3600,
            "email": f"user-{user_id}@test.local",
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


class FakeStorageClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def upload_object(self, *, bucket, path, content, content_type, access_token) -> None:
        self.objects[(bucket, path)] = content

    async def download_object(self, *, bucket, path, access_token) -> bytes:
        try:
            return self.objects[(bucket, path)]
        except KeyError:
            raise StorageObjectNotFoundError("Missing.") from None

    async def delete_object(self, *, bucket, path, access_token) -> None:
        self.objects.pop((bucket, path), None)

    async def create_signed_url(self, *, bucket, path, expires_in_seconds, access_token) -> str:
        return f"https://fake.storage/{bucket}/{path}"


class ScriptedRawClient:
    def __init__(self, script: list) -> None:
        self.script = script
        self.calls: list[dict] = []

    async def generate_raw(self, **kwargs) -> str:
        self.calls.append(kwargs)
        behavior = self.script.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


class FakeTranscriptionProvider:
    async def transcribe(self, content: bytes) -> TranscriptionResult:
        words = [
            TranscribedWord(word="Um", start=0.0, end=0.3, probability=0.9),
            TranscribedWord(word="I", start=0.5, end=0.6, probability=0.95),
            TranscribedWord(word="built", start=0.7, end=1.0, probability=0.97),
            TranscribedWord(word="the", start=1.1, end=1.2, probability=0.98),
            TranscribedWord(word="pipeline", start=3.0, end=3.6, probability=0.96),
        ]
        return TranscriptionResult(
            text="Um I built the pipeline",
            language="en",
            language_probability=0.99,
            audio_duration_seconds=5.0,
            words=tuple(words),
            provider="fake-transcriber",
        )


class FakeTTSProvider:
    def __init__(self) -> None:
        self.fail = False

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:
        if self.fail:
            raise TTSFailedError("Fake synthesis failure.")
        return TTSResult(
            audio_wav=b"RIFFfakewav", sample_rate=24_000, voice=voice or "af_heart",
            provider="fake-tts",
        )


def question_json(text_: str, qtype: str = "TECHNICAL", topic: str = "systems") -> str:
    return json.dumps(
        {"question_text": text_, "question_type": qtype, "topic": topic, "difficulty": "MEDIUM"}
    )


def evaluation_json(**overrides) -> str:
    return json.dumps(make_valid_evaluation_dict(**overrides))


def narrative_json() -> str:
    return json.dumps(
        {
            "overview": "The candidate performed steadily across stages with clear answers.",
            "technical_observations": ["Explained the pipeline architecture concretely."],
            "behavioral_observations": ["Communicated in structured, complete answers."],
            "strongest_answers": [
                {"question": "Q1", "reason": "Concrete and well-evidenced."}
            ],
            "weakest_answers": [{"question": "Q2", "reason": "Lacked measurable impact."}],
            "improvement_roadmap": [
                "Quantify project outcomes: two answers claimed improvements without numbers."
            ],
            "recommendations": ["Practice the problem-ownership-outcome answer structure."],
        }
    )


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            migrated = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE "
                        "table_name = 'interview_sessions' AND column_name = 'question_budget')"
                    )
                )
            ).scalar_one()
    except Exception:
        await engine.dispose()
        pytest.skip("Database unreachable - integration tests skipped.")
    if not migrated:
        await engine.dispose()
        pytest.skip("Schema not migrated to 0010 - run `alembic upgrade head` first.")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_users(db_engine):
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with db_engine.begin() as conn:
        for uid in (user_a, user_b):
            await conn.execute(
                text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
                {"id": uid, "email": f"user-{uid}@test.local"},
            )
    yield user_a, user_b
    async with db_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM auth.users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b}
        )


@pytest.fixture
def monkeypatch_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_JWKS_URL", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "integration-test-openai-key")
    return settings


@pytest.fixture
def ai_script():
    return []


@pytest.fixture
def fake_tts():
    return FakeTTSProvider()


@pytest_asyncio.fixture
async def client(monkeypatch_settings, ai_script, fake_tts):
    from app.api.v1.routes.interviews import get_transcription_provider, get_tts_provider
    from app.main import app

    raw_client = ScriptedRawClient(ai_script)
    app.dependency_overrides[get_storage_client] = lambda: FakeStorageClient()
    app.dependency_overrides[get_ai_runner] = lambda: StructuredAIRunner(
        raw_client, monkeypatch_settings
    )
    app.dependency_overrides[get_transcription_provider] = FakeTranscriptionProvider
    app.dependency_overrides[get_tts_provider] = lambda: fake_tts
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.raw_ai = raw_client  # type: ignore[attr-defined]
            yield ac
    finally:
        for dependency in (
            get_storage_client,
            get_ai_runner,
            get_transcription_provider,
            get_tts_provider,
        ):
            app.dependency_overrides.pop(dependency, None)


async def _rls_rows(engine, user_id: uuid.UUID, query: str, params: dict):
    """Run a verification query as the given user: RLS (FORCE) hides all
    rows unless auth.uid() resolves, exactly as in production."""
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('request.jwt.claims', :claims, true)"),
            {"claims": json.dumps({"sub": str(user_id)})},
        )
        return (await conn.execute(text(query), params)).all()


async def _provision(client: AsyncClient, user_id: uuid.UUID) -> None:
    response = await client.get("/api/v1/profiles/me", headers=_auth(user_id))
    assert response.status_code == 200


async def _upload_resume(client: AsyncClient, user_id: uuid.UUID, content: bytes) -> str:
    response = await client.post(
        "/api/v1/resumes",
        headers=_auth(user_id),
        files={"file": ("cv.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["resume"]["id"]


async def _create_interview(
    client: AsyncClient, user_id: uuid.UUID, resume_id: str, **overrides
) -> dict:
    payload = {
        "resume_id": resume_id,
        "interview_type": "MIXED",
        "difficulty": "MEDIUM",
        "duration_minutes": 5,  # budget 3: INTRODUCTION + 1 middle + CLOSING
    }
    payload.update(overrides)
    response = await client.post("/api/v1/interviews", headers=_auth(user_id), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestInterviewLifecycle:
    async def test_full_lifecycle_to_report(
        self, client, two_users, ai_script, db_engine, fake_tts
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        resume_id = await _upload_resume(client, user_a, build_resume_pdf())

        session = await _create_interview(client, user_a, resume_id)
        assert session["status"] == "PENDING"
        assert session["question_budget"] == 3
        session_id = session["id"]

        # ---- start: PENDING -> READY -> RUNNING, intro question -------
        ai_script.append(question_json("Tell me about yourself.", "INTRODUCTORY", "intro"))
        started = await client.post(
            f"/api/v1/interviews/{session_id}/start", headers=_auth(user_a)
        )
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["status"] == "RUNNING"
        assert body["current_stage"] == "INTRODUCTION"
        assert body["current_question"]["question_text"] == "Tell me about yourself."
        assert body["question_budget_used"] == 1

        # ---- text answer #1: evaluation + decision + next question ----
        ai_script.append(evaluation_json(recommended_action="ADVANCE_STAGE"))
        ai_script.append(question_json("How did you design the ingestion pipeline?"))
        cycle = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "I am a backend engineer who built Caviar."},
        )
        assert cycle.status_code == 200, cycle.text
        cycle_body = cycle.json()
        assert cycle_body["interview_completed"] is False
        assert cycle_body["action_taken"] == "ADVANCE_STAGE"
        assert cycle_body["stage"] == "ROLE_SPECIFIC"  # budget-3 plan middle stage
        assert cycle_body["next_question"]["sequence_number"] == 2
        # Live cycle exposes the observation, never numeric scores.
        assert "relevance_score" not in json.dumps(cycle_body)

        # Evaluation stored with profile-filtered NULLs (INTRODUCTORY:
        # technical depth does not apply).
        [row] = await _rls_rows(
            db_engine,
            user_a,
            "SELECT ae.technical_depth_score, ae.communication_score, "
            "ae.recommended_action FROM answer_evaluations ae "
            "JOIN interview_answers ia ON ia.id = ae.answer_id "
            "WHERE ia.session_id = :sid",
            {"sid": session_id},
        )
        assert row.technical_depth_score is None
        assert row.communication_score == 76
        assert row.recommended_action == "ADVANCE_STAGE"  # recommendation recorded

        # ---- pause / resume recovery ---------------------------------
        paused = await client.post(
            f"/api/v1/interviews/{session_id}/pause", headers=_auth(user_a)
        )
        assert paused.json()["status"] == "PAUSED"
        blocked = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "answering while paused"},
        )
        assert blocked.status_code == 409
        resumed = await client.post(
            f"/api/v1/interviews/{session_id}/resume", headers=_auth(user_a)
        )
        resumed_body = resumed.json()
        assert resumed_body["status"] == "RUNNING"
        assert (
            resumed_body["current_question"]["question_text"]
            == "How did you design the ingestion pipeline?"
        )

        # ---- audio answer #2: transcription + speech metrics + TTS ----
        ai_script.append(evaluation_json(recommended_action="ASK_FOLLOW_UP"))
        ai_script.append(question_json("What is your proudest achievement?", "INTRODUCTORY"))
        audio_cycle = await client.post(
            f"/api/v1/interviews/{session_id}/answers?include_audio=true",
            headers=_auth(user_a),
            files={"audio": ("answer.wav", b"RIFF" + b"\x00" * 200, "audio/wav")},
        )
        assert audio_cycle.status_code == 200, audio_cycle.text
        audio_body = audio_cycle.json()
        assert audio_body["speech_summary"]["filler_word_count"] == 1  # "Um"
        assert audio_body["question_audio_base64"]  # fake TTS audio attached
        # Budget 3 reached -> next answer will close regardless of AI.
        assert audio_body["questions_used"] == 3

        [metrics] = await _rls_rows(
            db_engine,
            user_a,
            "SELECT sm.word_count, sm.long_pause_count, sm.speech_completeness "
            "FROM speech_metrics sm JOIN interview_answers ia "
            "ON ia.id = sm.answer_id WHERE ia.session_id = :sid",
            {"sid": session_id},
        )
        assert metrics.word_count == 5
        assert metrics.long_pause_count == 1  # the 1.8s gap in the fake words

        # ---- answer #3: budget exhausted -> completion + report -------
        ai_script.append(evaluation_json(recommended_action="ASK_FOLLOW_UP"))
        ai_script.append(narrative_json())
        final = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "Thank you, nothing further."},
        )
        assert final.status_code == 200, final.text
        final_body = final.json()
        assert final_body["interview_completed"] is True
        assert final_body["action_taken"] == "CLOSE_INTERVIEW"
        assert final_body["next_question"] is None

        # ---- report ----------------------------------------------------
        report = await client.get(
            f"/api/v1/interviews/{session_id}/report", headers=_auth(user_a)
        )
        assert report.status_code == 200, report.text
        report_body = report.json()
        assert report_body["scoring_algorithm_version"] == "interview-readiness-1.0.0"
        assert report_body["overall_score"] is not None
        assert report_body["readiness_level"] in (
            "NOT_READY", "DEVELOPING", "READY", "STRONG",
        )
        assert len(report_body["categories"]) == 7
        payload = report_body["report_payload"]
        assert payload["narrative_unavailable"] is False
        assert payload["narrative"]["overview"].startswith("The candidate")
        assert len(payload["timeline"]) == 3
        assert len(payload["question_history"]) == 3
        assert payload["speech_metrics_summary"]["answers_with_audio"] == 1

        # Completed interviews accept no further transitions.
        assert (
            await client.post(f"/api/v1/interviews/{session_id}/pause", headers=_auth(user_a))
        ).status_code == 409
        assert (
            await client.post(f"/api/v1/interviews/{session_id}/cancel", headers=_auth(user_a))
        ).status_code == 409

    async def test_evaluation_failure_preserves_answer_and_is_retryable(
        self, client, two_users, ai_script, db_engine
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        resume_id = await _upload_resume(client, user_a, build_resume_pdf())
        session_id = (await _create_interview(client, user_a, resume_id))["id"]
        ai_script.append(question_json("Introduce yourself.", "INTRODUCTORY"))
        await client.post(f"/api/v1/interviews/{session_id}/start", headers=_auth(user_a))

        # Evaluation fails (transient, retried once by the runner).
        ai_script.extend(
            [AIProviderUnavailableError("down"), AIProviderUnavailableError("down")]
        )
        failed = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "My answer that must not be lost."},
        )
        assert failed.status_code == 503
        [answer] = await _rls_rows(
            db_engine,
            user_a,
            "SELECT transcript, status FROM interview_answers WHERE session_id = :sid",
            {"sid": session_id},
        )
        assert answer.transcript == "My answer that must not be lost."
        assert answer.status == "TRANSCRIBED"  # preserved, not evaluated
        session_state = await client.get(
            f"/api/v1/interviews/{session_id}", headers=_auth(user_a)
        )
        assert session_state.json()["status"] == "RUNNING"  # session survived

        # Resubmission replaces the unevaluated attempt and completes.
        ai_script.append(evaluation_json())
        ai_script.append(question_json("Next question?"))
        retried = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "My answer that must not be lost."},
        )
        assert retried.status_code == 200, retried.text
        rows = await _rls_rows(
            db_engine,
            user_a,
            "SELECT id FROM interview_answers WHERE session_id = :sid",
            {"sid": session_id},
        )
        assert len(rows) == 1  # replaced, not duplicated

    async def test_narrative_failure_still_persists_deterministic_report(
        self, client, two_users, ai_script, fake_tts
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        resume_id = await _upload_resume(client, user_a, build_resume_pdf())
        session_id = (await _create_interview(client, user_a, resume_id))["id"]
        ai_script.append(question_json("Introduce yourself.", "INTRODUCTORY"))
        await client.post(f"/api/v1/interviews/{session_id}/start", headers=_auth(user_a))
        for _ in range(2):
            ai_script.append(evaluation_json(recommended_action="CHANGE_TOPIC"))
            ai_script.append(question_json(f"Question {uuid.uuid4().hex[:8]}?"))
            response = await client.post(
                f"/api/v1/interviews/{session_id}/answers",
                headers=_auth(user_a),
                data={"text_answer": "An answer."},
            )
            assert response.status_code == 200
        # Final answer: evaluation succeeds, narrative fails twice.
        ai_script.append(evaluation_json())
        ai_script.extend(
            [AIProviderUnavailableError("down"), AIProviderUnavailableError("down")]
        )
        final = await client.post(
            f"/api/v1/interviews/{session_id}/answers",
            headers=_auth(user_a),
            data={"text_answer": "Closing answer."},
        )
        assert final.status_code == 200, final.text
        assert final.json()["interview_completed"] is True

        report = await client.get(
            f"/api/v1/interviews/{session_id}/report", headers=_auth(user_a)
        )
        body = report.json()
        assert body["overall_score"] is not None  # deterministic core intact
        assert body["narrative_model"] is None
        assert body["report_payload"]["narrative_unavailable"] is True

    async def test_tts_failure_degrades_to_text(
        self, client, two_users, ai_script, fake_tts
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        resume_id = await _upload_resume(client, user_a, build_resume_pdf())
        session_id = (await _create_interview(client, user_a, resume_id))["id"]
        ai_script.append(question_json("Introduce yourself.", "INTRODUCTORY"))
        await client.post(f"/api/v1/interviews/{session_id}/start", headers=_auth(user_a))

        fake_tts.fail = True
        ai_script.append(evaluation_json(recommended_action="CHANGE_TOPIC"))
        ai_script.append(question_json("What drives you?", "INTRODUCTORY"))
        cycle = await client.post(
            f"/api/v1/interviews/{session_id}/answers?include_audio=true",
            headers=_auth(user_a),
            data={"text_answer": "An answer."},
        )
        assert cycle.status_code == 200
        body = cycle.json()
        assert body["next_question"]["question_text"] == "What drives you?"
        assert body["question_audio_base64"] is None
        assert "TTSFailedError" in body["tts_warning"]

    async def test_setup_rules_and_isolation(self, client, two_users, ai_script) -> None:
        user_a, user_b = two_users
        await _provision(client, user_a)
        await _provision(client, user_b)

        # Unextracted (textless) resume -> 409.
        textless_id = await _upload_resume(client, user_a, build_textless_pdf())
        response = await client.post(
            "/api/v1/interviews",
            headers=_auth(user_a),
            json={"resume_id": textless_id},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "interview_setup_invalid"

        # Illegal transitions -> 409 (answer/pause before start).
        resume_id = await _upload_resume(client, user_a, build_resume_pdf())
        session_id = (await _create_interview(client, user_a, resume_id))["id"]
        assert (
            await client.post(
                f"/api/v1/interviews/{session_id}/answers",
                headers=_auth(user_a),
                data={"text_answer": "early"},
            )
        ).status_code == 409
        assert (
            await client.post(f"/api/v1/interviews/{session_id}/pause", headers=_auth(user_a))
        ).status_code == 409

        # Cancel works from PENDING; cancelled is terminal.
        cancelled = await client.post(
            f"/api/v1/interviews/{session_id}/cancel", headers=_auth(user_a)
        )
        assert cancelled.json()["status"] == "CANCELLED"
        assert (
            await client.post(f"/api/v1/interviews/{session_id}/start", headers=_auth(user_a))
        ).status_code == 409

        # Cross-user isolation on every route.
        other_id = (await _create_interview(client, user_a, resume_id))["id"]
        for method, url, kwargs in [
            ("get", f"/api/v1/interviews/{other_id}", {}),
            ("post", f"/api/v1/interviews/{other_id}/start", {}),
            (
                "post",
                f"/api/v1/interviews/{other_id}/answers",
                {"data": {"text_answer": "hijack"}},
            ),
            ("post", f"/api/v1/interviews/{other_id}/pause", {}),
            ("post", f"/api/v1/interviews/{other_id}/resume", {}),
            ("post", f"/api/v1/interviews/{other_id}/cancel", {}),
            ("get", f"/api/v1/interviews/{other_id}/report", {}),
        ]:
            response = await getattr(client, method)(url, headers=_auth(user_b), **kwargs)
            assert response.status_code == 404, (method, url, response.text)
        listing = await client.get("/api/v1/interviews", headers=_auth(user_b))
        assert listing.json()["interviews"] == []
