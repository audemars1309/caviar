/** Resume Builder + Generation API layer (Phase 9B). */
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/services/api/helpers";
import type { SectionType } from "@/features/builder/schemas";

export interface BuilderProject {
  id: string;
  title: string;
  status: string; // DRAFT | FINALIZED
  created_at: string;
  updated_at: string;
}

export interface BuilderSection {
  id: string;
  section_type: string;
  sort_order: number;
  content: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BuilderProjectDetail extends BuilderProject {
  sections: BuilderSection[];
}

export type AssistType = "GENERATE_SUMMARY" | "IMPROVE_SUMMARY" | "IMPROVE_BULLETS";

export interface ImprovedBullet {
  original: string;
  improved: string;
  changes_explained: string[];
  missing_fact_questions: string[];
  unsupported_numbers: string[];
}

export interface SummaryAssistResult {
  assist_type: AssistType;
  schema_version: string;
  ai_model: string;
  improved_summary: string;
  changes_explained: string[];
  missing_fact_questions: string[];
  action_verb_suggestions: string[];
  unsupported_numbers: string[];
}

export interface BulletsAssistResult {
  assist_type: AssistType;
  schema_version: string;
  ai_model: string;
  bullets: ImprovedBullet[];
  action_verb_suggestions: string[];
}

export interface ResumeTemplate {
  template_id: string;
  name: string;
  template_version: string;
  description: string;
  engine: string;
  ats_classification: string;
  supported_sections: string[];
  max_pages: number;
}

export interface Generation {
  id: string;
  template_id: string;
  template_version: string;
  status: string; // PENDING..COMPLETED | FAILED (backend lifecycle)
  page_count: number | null;
  file_size_bytes: number | null;
  compiler_version: string | null;
  compilation_duration_ms: number | null;
  warnings: Array<Record<string, unknown>>;
  failure_category: string | null;
  failure_reason: string | null;
  created_at?: string;
  updated_at?: string;
}

export const builderApi = {
  listProjects: () => apiGet<{ projects: BuilderProject[] }>("/resume-builder/projects"),
  createProject: (title: string) =>
    apiPost<BuilderProject>("/resume-builder/projects", { title }),
  getProject: (projectId: string) =>
    apiGet<BuilderProjectDetail>(`/resume-builder/projects/${projectId}`),
  updateProject: (projectId: string, payload: { title?: string; status?: "DRAFT" | "FINALIZED" }) =>
    apiPatch<BuilderProject>(`/resume-builder/projects/${projectId}`, payload),
  deleteProject: (projectId: string) => apiDelete(`/resume-builder/projects/${projectId}`),

  upsertSection: (projectId: string, sectionType: SectionType, content: Record<string, unknown>) =>
    apiPut<BuilderSection>(
      `/resume-builder/projects/${projectId}/sections/${sectionType}`,
      { content },
    ),
  deleteSection: (projectId: string, sectionType: SectionType) =>
    apiDelete(`/resume-builder/projects/${projectId}/sections/${sectionType}`),

  assist: (
    projectId: string,
    payload: {
      assist_type: AssistType;
      section_type?: SectionType;
      entry_index?: number;
      target_role?: string;
    },
  ) =>
    apiPost<SummaryAssistResult | BulletsAssistResult>(
      `/resume-builder/projects/${projectId}/assist`,
      payload,
    ),

  listTemplates: () => apiGet<{ templates: ResumeTemplate[] }>("/resume-templates"),
  listGenerations: (projectId: string) =>
    apiGet<{ generations: Generation[] }>(`/resume-builder/projects/${projectId}/generations`),
  createGeneration: (projectId: string, templateId: string) =>
    apiPost<Generation>(`/resume-builder/projects/${projectId}/generations`, {
      template_id: templateId,
    }),
  getGeneration: (generationId: string) =>
    apiGet<Generation>(`/resume-generations/${generationId}`),
  downloadGeneration: (generationId: string) =>
    apiGet<{ url: string; expires_in_seconds: number }>(
      `/resume-generations/${generationId}/download`,
    ),
};

/** Safe download filename derived from the project title. */
export function generationFilename(projectTitle: string): string {
  const base = projectTitle
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${base || "resume"}.pdf`;
}
