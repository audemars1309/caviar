/**
 * Resume Intelligence API layer (Phase 9B). Types mirror the backend
 * response schemas exactly; the frontend renders backend data and never
 * computes scores. All calls flow through the central client.
 */
import type { AxiosProgressEvent } from "axios";

import { apiClient } from "@/services/api/client";
import { apiDelete, apiGet, apiPost } from "@/services/api/helpers";

export interface Resume {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  extraction_status: string; // PENDING | EXTRACTED | FAILED (backend-owned)
  extraction_failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResumeUploadResult {
  resume: Resume;
  detected_section_types: string[];
  missing_section_types: string[];
  page_count: number | null;
}

export interface AnalysisCategory {
  category: string;
  score: number | null;
  weight: number;
  evidence: Array<Record<string, unknown>>;
  penalties: string[];
  adjusted_score: number | null;
  adjustments: Array<Record<string, unknown>>;
}

export interface AnalysisSummary {
  id: string;
  resume_id: string;
  job_context_id: string | null;
  target_role_snapshot: string | null;
  status: string; // PENDING | COMPLETED | FAILED (backend-owned)
  overall_score: number | null;
  scoring_algorithm_version: string;
  analysis_schema_version: string | null;
  ai_model: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisDetail extends AnalysisSummary {
  strengths: string[] | null;
  weaknesses: string[] | null;
  missing_sections: string[] | null;
  critical_issues: string[] | null;
  ats_observations: string[] | null;
  section_feedback: Array<Record<string, unknown>> | null;
  bullet_improvements: Array<Record<string, unknown>> | null;
  priority_improvements: string[] | null;
  role_relevance: Record<string, unknown> | null;
  categories: AnalysisCategory[];
}

export interface JobContext {
  id: string;
  target_role: string;
  company_name: string | null;
  job_description: string | null;
  created_at: string;
  updated_at: string;
}

export const resumesApi = {
  list: () => apiGet<{ resumes: Resume[] }>("/resumes"),
  get: (resumeId: string) => apiGet<Resume>(`/resumes/${resumeId}`),
  remove: (resumeId: string) => apiDelete(`/resumes/${resumeId}`),
  retryExtraction: (resumeId: string) =>
    apiPost<ResumeUploadResult>(`/resumes/${resumeId}/extraction/retry`),
  download: (resumeId: string) =>
    apiGet<{ url: string; expires_in_seconds: number }>(`/resumes/${resumeId}/download`),
  async upload(
    file: File,
    options: { signal?: AbortSignal; onProgress?: (percent: number) => void } = {},
  ): Promise<ResumeUploadResult> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<ResumeUploadResult>("/resumes", formData, {
      signal: options.signal,
      onUploadProgress: (event: AxiosProgressEvent) => {
        if (event.total && options.onProgress) {
          options.onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    });
    return response.data;
  },

  listAnalyses: (resumeId: string) =>
    apiGet<{ analyses: AnalysisSummary[] }>(`/resumes/${resumeId}/analyses`),
  createAnalysis: (resumeId: string, jobContextId: string | null) =>
    apiPost<AnalysisDetail>(`/resumes/${resumeId}/analyses`, {
      job_context_id: jobContextId,
    }),
  getAnalysis: (analysisId: string) =>
    apiGet<AnalysisDetail>(`/resume-analyses/${analysisId}`),

  listJobContexts: () => apiGet<{ job_contexts: JobContext[] }>("/job-contexts"),
  createJobContext: (payload: {
    target_role: string;
    company_name?: string;
    job_description?: string;
  }) => apiPost<JobContext>("/job-contexts", payload),
};

/** Client-side pre-checks mirroring backend validation so obvious
 *  problems fail fast; the backend remains authoritative. */
export const RESUME_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

export function validateResumeFile(
  file: File,
  existing: Resume[],
): { ok: true } | { ok: false; reason: string } {
  const isPdf =
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) {
    return { ok: false, reason: "Only PDF resumes are supported." };
  }
  if (file.size === 0) return { ok: false, reason: "The file is empty." };
  if (file.size > RESUME_MAX_FILE_SIZE_BYTES) {
    return { ok: false, reason: "The file exceeds the 10 MB limit." };
  }
  const duplicate = existing.find(
    (resume) =>
      resume.original_filename === file.name && resume.file_size_bytes === file.size,
  );
  if (duplicate) {
    return {
      ok: false,
      reason: `"${file.name}" looks already uploaded (same name and size).`,
    };
  }
  return { ok: true };
}
