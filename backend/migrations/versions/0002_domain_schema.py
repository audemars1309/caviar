"""Create the Caviar domain schema (Phase 2): profiles, job_contexts,
resumes, resume analysis, resume builder, interview engine, speech, and
reporting tables - per the approved Phase 0 Draft 2 architecture baseline.

This migration also creates a shared `public.set_updated_at()` trigger
function and attaches a BEFORE UPDATE trigger to every table with an
`updated_at` column. This directly addresses Phase 1 review observation
#2: SQLAlchemy's `onupdate=func.now()` only fires for writes that go
through the ORM's UPDATE statement construction; it does not cover direct
SQL writes (psql, the Supabase dashboard, other clients). The database
trigger is authoritative and covers every write path; the ORM-side
`onupdate` in `app/db/base.py` is retained as a harmless, redundant
default for ORM-level clarity and tests, not as the source of truth.

Implementation note: each call to `op.execute()` below contains exactly
one top-level SQL statement. asyncpg (used via SQLAlchemy's async engine)
executes migrations through the extended/prepared-statement protocol,
which rejects multiple semicolon-separated top-level statements in a
single call - unlike a single `DO $$ ... $$;` or `CREATE FUNCTION ... $$;`
block, whose internal semicolons are part of one dollar-quoted body and
are therefore fine.
"""

from __future__ import annotations

from alembic import op

revision = "0002_domain_schema"
down_revision = "0001_local_dev_compat"
branch_labels = None
depends_on = None

_STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$;
    """,
    # profiles
    """
    CREATE TABLE profiles (
        id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        full_name TEXT,
        target_role TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_profiles_set_updated_at
        BEFORE UPDATE ON profiles
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # job_contexts
    """
    CREATE TABLE job_contexts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        target_role TEXT NOT NULL,
        company_name TEXT,
        job_description TEXT,
        requirements_summary TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_job_contexts_user_id ON job_contexts(user_id);",
    """
    CREATE TRIGGER trg_job_contexts_set_updated_at
        BEFORE UPDATE ON job_contexts
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resumes
    """
    CREATE TABLE resumes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        storage_path TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL
            CHECK (file_size_bytes > 0 AND file_size_bytes <= 10485760),
        mime_type TEXT NOT NULL,
        extraction_status TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (extraction_status IN ('PENDING','EXTRACTED','FAILED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_resumes_user_id ON resumes(user_id);",
    """
    CREATE TRIGGER trg_resumes_set_updated_at
        BEFORE UPDATE ON resumes
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resume_analyses
    """
    CREATE TABLE resume_analyses (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        job_context_id UUID REFERENCES job_contexts(id) ON DELETE SET NULL,
        target_role_snapshot TEXT,
        overall_score INTEGER CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 100),
        status TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (status IN ('PENDING','COMPLETED','AI_ANALYSIS_FAILED')),
        scoring_algorithm_version TEXT NOT NULL,
        strengths JSONB,
        weaknesses JSONB,
        missing_sections JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_resume_analyses_user_id_created_at ON resume_analyses(user_id, created_at);",
    """
    CREATE TRIGGER trg_resume_analyses_set_updated_at
        BEFORE UPDATE ON resume_analyses
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resume_analysis_categories
    """
    CREATE TABLE resume_analysis_categories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resume_analysis_id UUID NOT NULL REFERENCES resume_analyses(id) ON DELETE CASCADE,
        category TEXT NOT NULL CHECK (category IN (
            'CONTENT_QUALITY','EXPERIENCE_IMPACT','SKILLS_RELEVANCE',
            'PROJECT_QUALITY','RESUME_STRUCTURE','ATS_COMPATIBILITY',
            'EVIDENCE_QUANTIFICATION'
        )),
        score INTEGER CHECK (score IS NULL OR score BETWEEN 0 AND 100),
        weight NUMERIC(4,3) NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]',
        penalties JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (resume_analysis_id, category)
    );
    """,
    """
    CREATE TRIGGER trg_resume_analysis_categories_set_updated_at
        BEFORE UPDATE ON resume_analysis_categories
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resume_builder_projects
    """
    CREATE TABLE resume_builder_projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','FINALIZED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_resume_builder_projects_user_id ON resume_builder_projects(user_id);",
    """
    CREATE TRIGGER trg_resume_builder_projects_set_updated_at
        BEFORE UPDATE ON resume_builder_projects
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resume_builder_sections
    """
    CREATE TABLE resume_builder_sections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES resume_builder_projects(id) ON DELETE CASCADE,
        section_type TEXT NOT NULL CHECK (section_type IN (
            'PERSONAL_INFO','SUMMARY','EDUCATION','SKILLS','EXPERIENCE',
            'INTERNSHIPS','PROJECTS','CERTIFICATIONS','ACHIEVEMENTS'
        )),
        sort_order INTEGER NOT NULL,
        content JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (project_id, sort_order)
    );
    """,
    """
    CREATE TRIGGER trg_resume_builder_sections_set_updated_at
        BEFORE UPDATE ON resume_builder_sections
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # resume_generations
    """
    CREATE TABLE resume_generations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES resume_builder_projects(id) ON DELETE CASCADE,
        template_id TEXT NOT NULL,
        template_version TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
            'PENDING','RENDERING','COMPILING','VALIDATING','UPLOADING','COMPLETED','FAILED'
        )),
        storage_path TEXT,
        page_count INTEGER,
        file_size_bytes INTEGER,
        compiler_version TEXT,
        failure_reason TEXT,
        compilation_duration_ms INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_resume_generations_project_id ON resume_generations(project_id);",
    """
    CREATE TRIGGER trg_resume_generations_set_updated_at
        BEFORE UPDATE ON resume_generations
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_sessions
    """
    CREATE TABLE interview_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
        job_context_id UUID REFERENCES job_contexts(id) ON DELETE SET NULL,
        target_role_snapshot TEXT,
        current_stage TEXT NOT NULL DEFAULT 'INTRODUCTION' CHECK (current_stage IN (
            'INTRODUCTION','CANDIDATE_BACKGROUND','RESUME_DISCUSSION','PROJECT_DEEP_DIVE',
            'ROLE_SPECIFIC','BEHAVIORAL','ADAPTIVE_PROBING','CLOSING','COMPLETED'
        )),
        status TEXT NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN (
            'IN_PROGRESS','COMPLETED','ABANDONED'
        )),
        question_budget_used INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_interview_sessions_user_id ON interview_sessions(user_id);",
    """
    CREATE TRIGGER trg_interview_sessions_set_updated_at
        BEFORE UPDATE ON interview_sessions
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_questions
    """
    CREATE TABLE interview_questions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
        stage TEXT NOT NULL,
        question_type TEXT NOT NULL CHECK (question_type IN (
            'INTRODUCTORY','RESUME','PROJECT','TECHNICAL','BEHAVIORAL',
            'SITUATIONAL','FOLLOW_UP','CLAIM_VERIFICATION'
        )),
        question_text TEXT NOT NULL,
        sequence_number INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (session_id, sequence_number)
    );
    """,
    """
    CREATE TRIGGER trg_interview_questions_set_updated_at
        BEFORE UPDATE ON interview_questions
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_answers
    """
    CREATE TABLE interview_answers (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        question_id UUID NOT NULL REFERENCES interview_questions(id) ON DELETE CASCADE,
        session_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
        audio_storage_path TEXT,
        transcript TEXT,
        transcript_segments JSONB,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
            'PENDING','TRANSCRIBED','EVALUATED','FAILED'
        )),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX ix_interview_answers_session_id ON interview_answers(session_id);",
    """
    CREATE TRIGGER trg_interview_answers_set_updated_at
        BEFORE UPDATE ON interview_answers
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # speech_metrics
    """
    CREATE TABLE speech_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        answer_id UUID NOT NULL UNIQUE REFERENCES interview_answers(id) ON DELETE CASCADE,
        speaking_duration_seconds NUMERIC,
        word_count INTEGER,
        words_per_minute NUMERIC,
        long_pause_count INTEGER,
        avg_pause_duration_seconds NUMERIC,
        max_pause_duration_seconds NUMERIC,
        filler_word_count INTEGER,
        filler_word_frequency NUMERIC,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_speech_metrics_set_updated_at
        BEFORE UPDATE ON speech_metrics
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # answer_evaluations
    """
    CREATE TABLE answer_evaluations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        answer_id UUID NOT NULL UNIQUE REFERENCES interview_answers(id) ON DELETE CASCADE,
        question_type TEXT NOT NULL,
        relevance_score INTEGER CHECK (relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100),
        clarity_score INTEGER CHECK (clarity_score IS NULL OR clarity_score BETWEEN 0 AND 100),
        technical_depth_score INTEGER CHECK (technical_depth_score IS NULL OR technical_depth_score BETWEEN 0 AND 100),
        specificity_score INTEGER CHECK (specificity_score IS NULL OR specificity_score BETWEEN 0 AND 100),
        evidence_score INTEGER CHECK (evidence_score IS NULL OR evidence_score BETWEEN 0 AND 100),
        problem_solving_score INTEGER CHECK (problem_solving_score IS NULL OR problem_solving_score BETWEEN 0 AND 100),
        communication_score INTEGER CHECK (communication_score IS NULL OR communication_score BETWEEN 0 AND 100),
        answer_structure_score INTEGER CHECK (answer_structure_score IS NULL OR answer_structure_score BETWEEN 0 AND 100),
        strengths JSONB,
        weaknesses JSONB,
        supporting_evidence JSONB,
        unsupported_claims JSONB,
        follow_up_required BOOLEAN NOT NULL DEFAULT false,
        follow_up_reason TEXT,
        recommended_action TEXT,
        target_topic TEXT,
        interviewer_observation TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_answer_evaluations_set_updated_at
        BEFORE UPDATE ON answer_evaluations
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_memories
    """
    CREATE TABLE interview_memories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE,
        candidate_profile_summary TEXT,
        resume_evidence_summary TEXT,
        job_requirements_summary TEXT,
        verified_evidence JSONB NOT NULL DEFAULT '[]',
        weak_areas JSONB NOT NULL DEFAULT '[]',
        strong_areas JSONB NOT NULL DEFAULT '[]',
        contradictions JSONB NOT NULL DEFAULT '[]',
        topics_explored JSONB NOT NULL DEFAULT '[]',
        topics_pending JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_interview_memories_set_updated_at
        BEFORE UPDATE ON interview_memories
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_reports
    """
    CREATE TABLE interview_reports (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE,
        overall_score INTEGER CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 100),
        scoring_algorithm_version TEXT NOT NULL,
        readiness_level TEXT CHECK (readiness_level IS NULL OR readiness_level IN (
            'NOT_READY','DEVELOPING','READY','STRONG'
        )),
        key_strengths JSONB,
        key_weaknesses JSONB,
        improvement_priorities JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TRIGGER trg_interview_reports_set_updated_at
        BEFORE UPDATE ON interview_reports
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
    # interview_report_categories
    """
    CREATE TABLE interview_report_categories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        interview_report_id UUID NOT NULL REFERENCES interview_reports(id) ON DELETE CASCADE,
        category TEXT NOT NULL CHECK (category IN (
            'COMMUNICATION','TECHNICAL_DEPTH','RELEVANCE','SPECIFICITY',
            'EVIDENCE','PROBLEM_SOLVING','ANSWER_STRUCTURE'
        )),
        score INTEGER CHECK (score IS NULL OR score BETWEEN 0 AND 100),
        weight NUMERIC(4,3) NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (interview_report_id, category)
    );
    """,
    """
    CREATE TRIGGER trg_interview_report_categories_set_updated_at
        BEFORE UPDATE ON interview_report_categories
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """,
]

_DOWNGRADE_STATEMENTS = [
    "DROP TABLE IF EXISTS interview_report_categories CASCADE;",
    "DROP TABLE IF EXISTS interview_reports CASCADE;",
    "DROP TABLE IF EXISTS interview_memories CASCADE;",
    "DROP TABLE IF EXISTS answer_evaluations CASCADE;",
    "DROP TABLE IF EXISTS speech_metrics CASCADE;",
    "DROP TABLE IF EXISTS interview_answers CASCADE;",
    "DROP TABLE IF EXISTS interview_questions CASCADE;",
    "DROP TABLE IF EXISTS interview_sessions CASCADE;",
    "DROP TABLE IF EXISTS resume_generations CASCADE;",
    "DROP TABLE IF EXISTS resume_builder_sections CASCADE;",
    "DROP TABLE IF EXISTS resume_builder_projects CASCADE;",
    "DROP TABLE IF EXISTS resume_analysis_categories CASCADE;",
    "DROP TABLE IF EXISTS resume_analyses CASCADE;",
    "DROP TABLE IF EXISTS resumes CASCADE;",
    "DROP TABLE IF EXISTS job_contexts CASCADE;",
    "DROP TABLE IF EXISTS profiles CASCADE;",
    "DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;",
]


def upgrade() -> None:
    for statement in _STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWNGRADE_STATEMENTS:
        op.execute(statement)
