/**
 * Interview Intelligence API layer (Phase 9C). Types mirror the Phase 8
 * backend schemas exactly. The frontend renders backend output only:
 * scores, readiness, speech metrics, and stage transitions are all
 * backend-owned. Exactly one of text/audio is sent per answer.
 */
import { apiClient } from "@/services/api/client";
import { apiGet, apiPost } from "@/services/api/helpers";

export type InterviewType = "MIXED" | "TECHNICAL" | "BEHAVIORAL";
export type Difficulty = "EASY" | "MEDIUM" | "HARD";

export const INTERVIEW_STAGES = [
  "INTRODUCTION",
  "CANDIDATE_BACKGROUND",
  "RESUME_DISCUSSION",
  "PROJECT_DEEP_DIVE",
  "ROLE_SPECIFIC",
  "BEHAVIORAL",
  "ADAPTIVE_PROBING",
  "CLOSING",
  "COMPLETED",
] as const;

export interface InterviewQuestion {
  id: string;
  stage: string;
  question_type: string;
  question_text: string;
  sequence_number: number;
  difficulty: string;
  topic: string | null;
}

export interface InterviewSession {
  id: string;
  resume_id: string | null;
  job_context_id: string | null;
  target_role_snapshot: string | null;
  status: string; // PENDING/READY/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED
  current_stage: string;
  interview_type: string;
  difficulty: string;
  duration_minutes: number;
  question_budget: number;
  question_budget_used: number;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewSessionDetail extends InterviewSession {
  current_question: InterviewQuestion | null;
}

export interface NextQuestion {
  id: string;
  question_text: string;
  question_type: string;
  stage: string;
  difficulty: string;
  sequence_number: number;
}

export interface AnswerCycle {
  interviewer_observation: string;
  action_taken: string;
  recommendation_overridden: boolean;
  stage: string;
  speech_summary: {
    words_per_minute?: number | null;
    long_pause_count?: number | null;
    filler_word_count?: number | null;
  } | null;
  questions_used: number;
  question_budget: number;
  next_question: NextQuestion | null;
  interview_completed: boolean;
  question_audio_base64: string | null;
  tts_warning: string | null;
}

export interface ReportCategory {
  category: string;
  score: number | null;
  weight: number;
  evidence: string[];
}

export interface ReportHighlight {
  question: string;
  reason: string;
}

export interface ReportNarrative {
  overview: string;
  technical_observations: string[];
  behavioral_observations: string[];
  strongest_answers: ReportHighlight[];
  weakest_answers: ReportHighlight[];
  improvement_roadmap: string[];
}

export interface ReportPayload {
  schema_version: string;
  evaluation_schema_version: string;
  timeline: Array<{
    sequence: number;
    stage: string;
    question_type: string;
    topic: string | null;
    difficulty: string;
  }>;
  topic_coverage: string[];
  question_history: Array<{
    sequence: number;
    question: string;
    observation: string | null;
    strengths: string[] | null;
    weaknesses: string[] | null;
  }>;
  speech_metrics_summary: {
    answers_with_audio: number;
    avg_words_per_minute: number | null;
    avg_filler_word_count: number | null;
    total_long_pauses: number;
    avg_speech_completeness: number | null;
  };
  narrative: ReportNarrative | null;
  narrative_unavailable: boolean;
}

export interface InterviewReport {
  id: string;
  session_id: string;
  overall_score: number | null;
  readiness_level: string | null;
  scoring_algorithm_version: string;
  key_strengths: string[] | null;
  key_weaknesses: string[] | null;
  improvement_priorities: string[] | null;
  narrative_model: string | null;
  report_payload: ReportPayload | null;
  created_at: string;
  categories: ReportCategory[];
}

export interface CreateInterviewInput {
  resume_id: string;
  job_context_id: string | null;
  interview_type: InterviewType;
  difficulty: Difficulty;
  duration_minutes: number;
}

export const interviewsApi = {
  list: () => apiGet<{ interviews: InterviewSession[] }>("/interviews"),
  get: (sessionId: string) => apiGet<InterviewSessionDetail>(`/interviews/${sessionId}`),
  create: (input: CreateInterviewInput) => apiPost<InterviewSession>("/interviews", input),
  start: (sessionId: string) =>
    apiPost<InterviewSessionDetail>(`/interviews/${sessionId}/start`),
  pause: (sessionId: string) => apiPost<InterviewSession>(`/interviews/${sessionId}/pause`),
  resume: (sessionId: string) =>
    apiPost<InterviewSessionDetail>(`/interviews/${sessionId}/resume`),
  cancel: (sessionId: string) => apiPost<InterviewSession>(`/interviews/${sessionId}/cancel`),
  report: (sessionId: string) =>
    apiGet<InterviewReport>(`/interviews/${sessionId}/report`),

  /** Submit exactly one of a text answer or an audio recording. The
   *  browser never processes speech - audio goes to the backend as-is. */
  async submitAnswer(
    sessionId: string,
    input: { text?: string; audio?: Blob },
    options: { includeAudio?: boolean } = {},
  ): Promise<AnswerCycle> {
    const formData = new FormData();
    if (input.audio) {
      formData.append("audio", input.audio, "answer.webm");
    } else {
      formData.append("text_answer", input.text ?? "");
    }
    const response = await apiClient.post<AnswerCycle>(
      `/interviews/${sessionId}/answers`,
      formData,
      { params: { include_audio: options.includeAudio ?? false } },
    );
    return response.data;
  },
};

/** Mirrors backend validate_answer_audio limits so oversized clips fail
 *  fast client-side; the backend remains authoritative. */
export const ANSWER_AUDIO_MAX_BYTES = 25 * 1024 * 1024;

export function validateAnswerAudio(
  blob: Blob,
): { ok: true } | { ok: false; reason: string } {
  if (blob.size === 0) return { ok: false, reason: "The recording is empty." };
  if (blob.size > ANSWER_AUDIO_MAX_BYTES) {
    return { ok: false, reason: "The recording exceeds the 25 MB limit." };
  }
  return { ok: true };
}

export const STATUS_LABELS: Record<string, string> = {
  PENDING: "Created",
  READY: "Ready to start",
  RUNNING: "In progress",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const READINESS_LABELS: Record<string, string> = {
  NOT_READY: "Not ready",
  DEVELOPING: "Developing",
  READY: "Ready",
  STRONG: "Strong",
};
