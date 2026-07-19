/** TanStack Query hooks for the Resume Builder, including debounced
 *  section autosave with validate-before-send. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import {
  builderApi,
  type BuilderProject,
  type BuilderProjectDetail,
  type Generation,
} from "@/features/builder/api";
import {
  validateSectionContent,
  type SectionType,
} from "@/features/builder/schemas";
import { useDebouncedCallback } from "@/hooks/useDebouncedCallback";
import { getApiErrorMessage } from "@/services/api/errors";

export const builderKeys = {
  projects: ["builder", "projects"] as const,
  project: (projectId: string) => ["builder", "projects", projectId] as const,
  templates: ["builder", "templates"] as const,
  generations: (projectId: string) => ["builder", projectId, "generations"] as const,
};

export function useBuilderProjects() {
  return useQuery({
    queryKey: builderKeys.projects,
    queryFn: async () => (await builderApi.listProjects()).projects,
  });
}

export function useBuilderProject(projectId: string) {
  return useQuery({
    queryKey: builderKeys.project(projectId),
    queryFn: () => builderApi.getProject(projectId),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => builderApi.createProject(title),
    onSuccess: (project) => {
      queryClient.setQueryData<BuilderProject[]>(builderKeys.projects, (current) => [
        project,
        ...(current ?? []),
      ]);
    },
  });
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { title?: string; status?: "DRAFT" | "FINALIZED" }) =>
      builderApi.updateProject(projectId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: builderKeys.projects });
      void queryClient.invalidateQueries({ queryKey: builderKeys.project(projectId) });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => builderApi.deleteProject(projectId),
    onSuccess: (_data, projectId) => {
      queryClient.setQueryData<BuilderProject[]>(builderKeys.projects, (current) =>
        current?.filter((item) => item.id !== projectId),
      );
      toast.success("Project deleted.");
    },
  });
}

export function useDeleteSection(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sectionType: SectionType) => builderApi.deleteSection(projectId, sectionType),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: builderKeys.project(projectId) }),
  });
}

export type AutosaveStatus = "idle" | "editing" | "saving" | "saved" | "invalid" | "error";

export interface AutosaveState {
  status: AutosaveStatus;
  message: string | null;
}

/**
 * Debounced per-section autosave. Content is validated against the
 * mirrored backend schema BEFORE any request: incomplete drafts show
 * "invalid" quietly instead of hammering the API with 422s. The user's
 * upsert is the only write path for their data (AI assist never saves).
 */
export function useSectionAutosave(projectId: string, sectionType: SectionType) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AutosaveState>({ status: "idle", message: null });

  const save = useCallback(
    async (content: unknown) => {
      const verdict = validateSectionContent(sectionType, content);
      if (!verdict.ok) {
        setState({ status: "invalid", message: verdict.message });
        return;
      }
      setState({ status: "saving", message: null });
      try {
        const section = await builderApi.upsertSection(projectId, sectionType, verdict.content);
        setState({ status: "saved", message: null });
        queryClient.setQueryData<BuilderProjectDetail>(
          builderKeys.project(projectId),
          (current) => {
            if (!current) return current;
            const others = current.sections.filter(
              (item) => item.section_type !== sectionType,
            );
            return { ...current, sections: [...others, section] };
          },
        );
      } catch (error) {
        setState({ status: "error", message: getApiErrorMessage(error) });
      }
    },
    [projectId, sectionType, queryClient],
  );

  const debouncedSave = useDebouncedCallback((content: unknown) => void save(content), 800);

  const onChange = useCallback(
    (content: unknown) => {
      setState((current) =>
        current.status === "saving" ? current : { status: "editing", message: null },
      );
      debouncedSave.run(content);
    },
    [debouncedSave],
  );

  return { state, onChange, flush: debouncedSave.flush, saveNow: save };
}

export function useAssist(projectId: string) {
  return useMutation({
    meta: { silent: true }, // errors render inline with a retry button
    mutationFn: (payload: Parameters<typeof builderApi.assist>[1]) =>
      builderApi.assist(projectId, payload),
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: builderKeys.templates,
    queryFn: async () => (await builderApi.listTemplates()).templates,
    staleTime: 10 * 60_000, // template registry changes rarely
  });
}

export function useGenerations(projectId: string) {
  return useQuery({
    queryKey: builderKeys.generations(projectId),
    queryFn: async () => (await builderApi.listGenerations(projectId)).generations,
  });
}

export function useCreateGeneration(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { silent: true },
    mutationFn: (templateId: string) => builderApi.createGeneration(projectId, templateId),
    onSuccess: (generation) => {
      queryClient.setQueryData<Generation[]>(builderKeys.generations(projectId), (current) => [
        generation,
        ...(current ?? []),
      ]);
    },
  });
}

/** Fetch the signed URL and trigger a browser download with a clean
 *  filename. Backend-generated files only. */
export function useDownloadGeneration() {
  return useMutation({
    mutationFn: async ({ generationId, filename }: { generationId: string; filename: string }) => {
      const { url } = await builderApi.downloadGeneration(generationId);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.rel = "noopener";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    },
  });
}
