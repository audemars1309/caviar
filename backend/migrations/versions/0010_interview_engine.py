"""Phase 8: Interview Intelligence engine storage.

1. ``interview_sessions``: upgrades the status lifecycle from Phase 2's
   3-state model to the full recoverable 7-state machine
   (PENDING/READY/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED), and adds
   the session configuration the engine needs: interview type,
   difficulty, duration, total question budget, per-session failure
   reason, and ``current_question_id`` (the question awaiting an answer -
   what makes interrupted-interview recovery a simple read). The
   approved Phase 0/2 STAGE taxonomy is deliberately kept unchanged; the
   Phase 8 stage names map 1:1 onto it (Warmup=CANDIDATE_BACKGROUND,
   Technical Round=ROLE_SPECIFIC, Problem Solving=ADAPTIVE_PROBING).

2. ``interview_questions``: per-question difficulty and topic, and the
   backend-computed ``normalized_text`` used for deterministic duplicate
   prevention.

3. ``interview_answers``: input mode (TEXT/AUDIO), detected language,
   and audio duration.

4. ``speech_metrics``: the remaining deterministic metrics -
   hesitations, silence, response duration, answer length, completeness.

5. ``interview_memories``: the structured-memory fields Phase 8 tracks
   beyond Phase 2's base set - questions asked, skills covered, user
   corrections, confidence trend, follow-up opportunities, and the
   bounded recent-turns window.

6. ``interview_reports``: ``report_payload`` JSONB for the structured
   report document (timeline, topic coverage, question history, speech
   summary, narrative sections) and ``narrative_model`` provenance.

Each op.execute contains one statement (asyncpg protocol; see 0002).
"""

from __future__ import annotations

from alembic import op

revision = "0010_interview_engine"
down_revision = "0009_generation_warnings"
branch_labels = None
depends_on = None

_UPGRADE_STATEMENTS = [
    # -- interview_sessions: 7-state lifecycle ---------------------------
    # 0002 created the status CHECK inline and unnamed; Postgres auto-named it.
    "ALTER TABLE interview_sessions DROP CONSTRAINT interview_sessions_status_check;",
    """
    ALTER TABLE interview_sessions ADD CONSTRAINT interview_sessions_status_check
        CHECK (status IN ('PENDING','READY','RUNNING','PAUSED','COMPLETED',
                          'FAILED','CANCELLED'));
    """,
    "ALTER TABLE interview_sessions ALTER COLUMN status SET DEFAULT 'PENDING';",
    """
    ALTER TABLE interview_sessions ADD COLUMN interview_type TEXT NOT NULL
        DEFAULT 'MIXED' CHECK (interview_type IN ('MIXED','TECHNICAL','BEHAVIORAL'));
    """,
    """
    ALTER TABLE interview_sessions ADD COLUMN difficulty TEXT NOT NULL
        DEFAULT 'MEDIUM' CHECK (difficulty IN ('EASY','MEDIUM','HARD'));
    """,
    """
    ALTER TABLE interview_sessions ADD COLUMN duration_minutes INTEGER NOT NULL
        DEFAULT 20 CHECK (duration_minutes BETWEEN 5 AND 60);
    """,
    """
    ALTER TABLE interview_sessions ADD COLUMN question_budget INTEGER NOT NULL
        DEFAULT 10 CHECK (question_budget BETWEEN 3 AND 30);
    """,
    "ALTER TABLE interview_sessions ADD COLUMN failure_reason TEXT;",
    """
    ALTER TABLE interview_sessions ADD COLUMN current_question_id UUID
        REFERENCES interview_questions(id) ON DELETE SET NULL;
    """,
    # -- interview_questions ---------------------------------------------
    """
    ALTER TABLE interview_questions ADD COLUMN difficulty TEXT NOT NULL
        DEFAULT 'MEDIUM' CHECK (difficulty IN ('EASY','MEDIUM','HARD'));
    """,
    "ALTER TABLE interview_questions ADD COLUMN topic TEXT;",
    "ALTER TABLE interview_questions ADD COLUMN normalized_text TEXT NOT NULL DEFAULT '';",
    # -- interview_answers ------------------------------------------------
    """
    ALTER TABLE interview_answers ADD COLUMN input_mode TEXT NOT NULL
        DEFAULT 'TEXT' CHECK (input_mode IN ('TEXT','AUDIO'));
    """,
    "ALTER TABLE interview_answers ADD COLUMN language TEXT;",
    "ALTER TABLE interview_answers ADD COLUMN audio_duration_seconds NUMERIC;",
    # -- speech_metrics ----------------------------------------------------
    "ALTER TABLE speech_metrics ADD COLUMN hesitation_count INTEGER;",
    "ALTER TABLE speech_metrics ADD COLUMN silence_duration_seconds NUMERIC;",
    "ALTER TABLE speech_metrics ADD COLUMN response_duration_seconds NUMERIC;",
    "ALTER TABLE speech_metrics ADD COLUMN answer_char_length INTEGER;",
    """
    ALTER TABLE speech_metrics ADD COLUMN speech_completeness NUMERIC
        CHECK (speech_completeness IS NULL OR
               (speech_completeness >= 0 AND speech_completeness <= 1));
    """,
    # -- interview_memories ------------------------------------------------
    "ALTER TABLE interview_memories ADD COLUMN questions_asked JSONB NOT NULL DEFAULT '[]';",
    "ALTER TABLE interview_memories ADD COLUMN skills_covered JSONB NOT NULL DEFAULT '[]';",
    "ALTER TABLE interview_memories ADD COLUMN user_corrections JSONB NOT NULL DEFAULT '[]';",
    "ALTER TABLE interview_memories ADD COLUMN confidence_trend JSONB NOT NULL DEFAULT '[]';",
    (
        "ALTER TABLE interview_memories ADD COLUMN follow_up_opportunities JSONB "
        "NOT NULL DEFAULT '[]';"
    ),
    "ALTER TABLE interview_memories ADD COLUMN recent_turns JSONB NOT NULL DEFAULT '[]';",
    # -- interview_reports -------------------------------------------------
    "ALTER TABLE interview_reports ADD COLUMN report_payload JSONB;",
    "ALTER TABLE interview_reports ADD COLUMN narrative_model TEXT;",
]

_DOWNGRADE_STATEMENTS = [
    "ALTER TABLE interview_reports DROP COLUMN IF EXISTS narrative_model;",
    "ALTER TABLE interview_reports DROP COLUMN IF EXISTS report_payload;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS recent_turns;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS follow_up_opportunities;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS confidence_trend;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS user_corrections;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS skills_covered;",
    "ALTER TABLE interview_memories DROP COLUMN IF EXISTS questions_asked;",
    "ALTER TABLE speech_metrics DROP COLUMN IF EXISTS speech_completeness;",
    "ALTER TABLE speech_metrics DROP COLUMN IF EXISTS answer_char_length;",
    "ALTER TABLE speech_metrics DROP COLUMN IF EXISTS response_duration_seconds;",
    "ALTER TABLE speech_metrics DROP COLUMN IF EXISTS silence_duration_seconds;",
    "ALTER TABLE speech_metrics DROP COLUMN IF EXISTS hesitation_count;",
    "ALTER TABLE interview_answers DROP COLUMN IF EXISTS audio_duration_seconds;",
    "ALTER TABLE interview_answers DROP COLUMN IF EXISTS language;",
    "ALTER TABLE interview_answers DROP COLUMN IF EXISTS input_mode;",
    "ALTER TABLE interview_questions DROP COLUMN IF EXISTS normalized_text;",
    "ALTER TABLE interview_questions DROP COLUMN IF EXISTS topic;",
    "ALTER TABLE interview_questions DROP COLUMN IF EXISTS difficulty;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS current_question_id;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS failure_reason;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS question_budget;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS duration_minutes;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS difficulty;",
    "ALTER TABLE interview_sessions DROP COLUMN IF EXISTS interview_type;",
    "ALTER TABLE interview_sessions ALTER COLUMN status SET DEFAULT 'IN_PROGRESS';",
    # 0002 created the status CHECK inline and unnamed; Postgres auto-named it.
    "ALTER TABLE interview_sessions DROP CONSTRAINT interview_sessions_status_check;",
    """
    ALTER TABLE interview_sessions ADD CONSTRAINT interview_sessions_status_check
        CHECK (status IN ('IN_PROGRESS','COMPLETED','ABANDONED'));
    """,
]


def upgrade() -> None:
    for statement in _UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWNGRADE_STATEMENTS:
        op.execute(statement)
