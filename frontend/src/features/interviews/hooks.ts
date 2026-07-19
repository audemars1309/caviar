/** TanStack Query hooks for the Interview Product. Server state only -
 *  all scores and stage transitions come from the backend. */
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  interviewsApi,
  type CreateInterviewInput,
  type InterviewReport,
  type InterviewSession,
  type InterviewSessionDetail,
} from "@/features/interviews/api";
import { isClientError } from "@/services/api/errors";

export const interviewKeys = {
  list: ["interviews", "list"] as const,
  detail: (sessionId: string) => ["interviews", sessionId] as const,
  report: (sessionId: string) => ["interviews", sessionId, "report"] as const,
};

export function useInterviews() {
  return useQuery({
    queryKey: interviewKeys.list,
    queryFn: async () => (await interviewsApi.list()).interviews,
  });
}

export function useInterview(sessionId: string) {
  return useQuery({
    queryKey: interviewKeys.detail(sessionId),
    queryFn: () => interviewsApi.get(sessionId),
  });
}

export function useInterviewReport(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: interviewKeys.report(sessionId),
    queryFn: () => interviewsApi.report(sessionId),
    enabled,
    retry: (failureCount, error) => !isClientError(error) && failureCount < 2,
  });
}

/** Backend-computed readiness trend: one report (overall_score,
 *  readiness_level, created_at) per completed interview. The frontend
 *  plots the points; it computes nothing. */
export function useReadinessTrend(sessions: InterviewSession[] | undefined) {
  const completed = (sessions ?? []).filter((s) => s.status === "COMPLETED");
  const results = useQueries({
    queries: completed.map((session) => ({
      queryKey: interviewKeys.report(session.id),
      queryFn: () => interviewsApi.report(session.id),
      staleTime: 5 * 60_000,
      retry: false,
      meta: { silent: true },
    })),
  });
  const points = results
    .map((result) => result.data)
    .filter((report): report is InterviewReport => Boolean(report))
    .filter((report) => report.overall_score !== null)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  return { points, isLoading: results.some((result) => result.isLoading) };
}

export function useCreateInterview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateInterviewInput) => interviewsApi.create(input),
    onSuccess: (session) => {
      queryClient.setQueryData<InterviewSession[]>(interviewKeys.list, (current) => [
        session,
        ...(current ?? []),
      ]);
    },
  });
}

function useSessionAction(
  action: (sessionId: string) => Promise<InterviewSession | InterviewSessionDetail>,
  successMessage?: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: (session) => {
      queryClient.setQueryData(interviewKeys.detail(session.id), (current: unknown) => {
        const existing = (current ?? {}) as Partial<InterviewSessionDetail>;
        return { current_question: existing.current_question ?? null, ...existing, ...session };
      });
      void queryClient.invalidateQueries({ queryKey: interviewKeys.list });
      void queryClient.invalidateQueries({ queryKey: interviewKeys.detail(session.id) });
      if (successMessage) toast.success(successMessage);
    },
  });
}

export function useStartInterview() {
  return useSessionAction((sessionId) => interviewsApi.start(sessionId));
}

export function usePauseInterview() {
  return useSessionAction((sessionId) => interviewsApi.pause(sessionId), "Interview paused.");
}

export function useResumeInterview() {
  return useSessionAction((sessionId) => interviewsApi.resume(sessionId));
}

export function useCancelInterview() {
  return useSessionAction((sessionId) => interviewsApi.cancel(sessionId), "Interview ended.");
}

export function useSubmitAnswer(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { silent: true }, // failures render inline in the room with retry
    mutationFn: (input: { text?: string; audio?: Blob; includeAudio?: boolean }) =>
      interviewsApi.submitAnswer(
        sessionId,
        { ...(input.audio ? { audio: input.audio } : { text: input.text ?? "" }) },
        { includeAudio: input.includeAudio },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: interviewKeys.detail(sessionId) });
      void queryClient.invalidateQueries({ queryKey: interviewKeys.list });
    },
  });
}
