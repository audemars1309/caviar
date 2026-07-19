/** TanStack Query hooks for Resume Intelligence. Server state lives
 *  here - never in Zustand. */
import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

import { resumesApi, validateResumeFile, type Resume } from "@/features/resumes/api";
import { getApiErrorMessage } from "@/services/api/errors";

export const resumeKeys = {
  all: ["resumes"] as const,
  list: () => [...resumeKeys.all, "list"] as const,
  analyses: (resumeId: string) => [...resumeKeys.all, resumeId, "analyses"] as const,
  analysis: (analysisId: string) => ["resume-analyses", analysisId] as const,
  jobContexts: ["job-contexts"] as const,
};

export function useResumes() {
  return useQuery({
    queryKey: resumeKeys.list(),
    queryFn: async () => (await resumesApi.list()).resumes,
    placeholderData: keepPreviousData,
  });
}

export function useResumeAnalyses(resumeId: string | null) {
  return useQuery({
    queryKey: resumeKeys.analyses(resumeId ?? "none"),
    queryFn: async () => (await resumesApi.listAnalyses(resumeId ?? "")).analyses,
    enabled: resumeId !== null,
  });
}

export function useAnalysis(analysisId: string) {
  return useQuery({
    queryKey: resumeKeys.analysis(analysisId),
    queryFn: () => resumesApi.getAnalysis(analysisId),
  });
}

export function useJobContexts() {
  return useQuery({
    queryKey: resumeKeys.jobContexts,
    queryFn: async () => (await resumesApi.listJobContexts()).job_contexts,
  });
}

export function useCreateJobContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resumesApi.createJobContext,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: resumeKeys.jobContexts }),
  });
}

export function useDeleteResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resumeId: string) => resumesApi.remove(resumeId),
    onSuccess: (_data, resumeId) => {
      // Server confirmed - drop it from the cached list immediately.
      queryClient.setQueryData<Resume[]>(resumeKeys.list(), (current) =>
        current?.filter((item) => item.id !== resumeId),
      );
      toast.success("Resume deleted.");
    },
  });
}

export function useRetryExtraction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resumeId: string) => resumesApi.retryExtraction(resumeId),
    onSuccess: () => {
      toast.success("Extraction retried.");
      void queryClient.invalidateQueries({ queryKey: resumeKeys.list() });
    },
  });
}

export function useCreateAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ resumeId, jobContextId }: { resumeId: string; jobContextId: string | null }) =>
      resumesApi.createAnalysis(resumeId, jobContextId),
    onSuccess: (analysis) => {
      queryClient.setQueryData(resumeKeys.analysis(analysis.id), analysis);
      void queryClient.invalidateQueries({ queryKey: resumeKeys.analyses(analysis.resume_id) });
    },
  });
}

export type UploadPhase = "idle" | "uploading" | "success" | "error" | "cancelled";

export interface UploadState {
  phase: UploadPhase;
  progress: number;
  fileName: string | null;
  error: string | null;
}

const IDLE_UPLOAD: UploadState = { phase: "idle", progress: 0, fileName: null, error: null };

/**
 * Upload controller: validation (type/size/duplicate) before any bytes
 * move, streamed progress, cancellation via AbortController, retry of
 * the last file, and backend validation errors surfaced verbatim.
 */
export function useResumeUpload(existing: Resume[]) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<UploadState>(IDLE_UPLOAD);
  const abortRef = useRef<AbortController | null>(null);
  const lastFileRef = useRef<File | null>(null);

  const start = useCallback(
    async (file: File) => {
      const verdict = validateResumeFile(file, existing);
      if (!verdict.ok) {
        setState({ phase: "error", progress: 0, fileName: file.name, error: verdict.reason });
        return;
      }
      lastFileRef.current = file;
      const controller = new AbortController();
      abortRef.current = controller;
      setState({ phase: "uploading", progress: 0, fileName: file.name, error: null });
      try {
        const result = await resumesApi.upload(file, {
          signal: controller.signal,
          onProgress: (progress) =>
            setState((current) => ({ ...current, progress })),
        });
        setState({ phase: "success", progress: 100, fileName: file.name, error: null });
        toast.success(`"${file.name}" uploaded.`);
        queryClient.setQueryData<Resume[]>(resumeKeys.list(), (current) => [
          result.resume,
          ...(current ?? []),
        ]);
        void queryClient.invalidateQueries({ queryKey: resumeKeys.list() });
      } catch (error) {
        if (controller.signal.aborted) {
          setState({ ...IDLE_UPLOAD, phase: "cancelled", fileName: file.name });
          return;
        }
        setState({
          phase: "error",
          progress: 0,
          fileName: file.name,
          error: getApiErrorMessage(error),
        });
      } finally {
        abortRef.current = null;
      }
    },
    [existing, queryClient],
  );

  const cancel = useCallback(() => abortRef.current?.abort(), []);
  const retry = useCallback(() => {
    if (lastFileRef.current) void start(lastFileRef.current);
  }, [start]);
  const reset = useCallback(() => setState(IDLE_UPLOAD), []);

  return { state, start, cancel, retry, reset };
}
