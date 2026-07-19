/** Interview Room tests: start flow, question rendering from backend
 *  state, answer submission cycle, and inline error retry. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/client", () => ({ apiClient: { post: vi.fn() } }));
vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import type { InterviewSessionDetail } from "@/features/interviews/api";
import InterviewRoomPage from "@/pages/InterviewRoomPage";
import { apiClient } from "@/services/api/client";
import { apiGet, apiPost } from "@/services/api/helpers";

function Providers({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter initialEntries={["/interview/s1"]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/interview/:sessionId" element={children} />
          <Route path="/interview/:sessionId/report" element={<p>REPORT PAGE</p>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

function detail(partial: Partial<InterviewSessionDetail>): InterviewSessionDetail {
  return {
    id: "s1",
    resume_id: "r1",
    job_context_id: null,
    target_role_snapshot: "Backend Engineer",
    status: "RUNNING",
    current_stage: "RESUME_DISCUSSION",
    interview_type: "MIXED",
    difficulty: "MEDIUM",
    duration_minutes: 20,
    question_budget: 12,
    question_budget_used: 3,
    failure_reason: null,
    created_at: "2026-07-01T10:00:00Z",
    updated_at: "2026-07-01T10:10:00Z",
    current_question: {
      id: "q3",
      stage: "RESUME_DISCUSSION",
      question_type: "RESUME",
      question_text: "Tell me about your FastAPI experience.",
      sequence_number: 3,
      difficulty: "MEDIUM",
      topic: "FastAPI",
    },
    ...partial,
  };
}

describe("InterviewRoomPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("offers to start a READY session", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({ status: "READY", current_question: null }));
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    expect(await screen.findByRole("button", { name: /start interview/i })).toBeInTheDocument();
  });

  it("renders the backend question, stage, and budget while running", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({}));
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    expect(
      await screen.findByText("Tell me about your FastAPI experience."),
    ).toBeInTheDocument();
    expect(screen.getByText("3/12 questions")).toBeInTheDocument();
    expect(screen.getByText("Resume")).toHaveAttribute("aria-current", "step");
  });

  it("submits a typed answer and renders the interviewer observation + next question", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({}));
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        interviewer_observation: "The answer names the stack but not your contribution.",
        action_taken: "PROBE_VAGUE_ANSWER",
        recommendation_overridden: false,
        stage: "RESUME_DISCUSSION",
        speech_summary: null,
        questions_used: 4,
        question_budget: 12,
        next_question: {
          id: "q4",
          question_text: "What did you personally implement?",
          question_type: "FOLLOW_UP",
          stage: "RESUME_DISCUSSION",
          difficulty: "MEDIUM",
          sequence_number: 4,
        },
        interview_completed: false,
        question_audio_base64: null,
        tts_warning: null,
      },
    });
    const user = userEvent.setup();
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    await screen.findByText("Tell me about your FastAPI experience.");
    await user.click(screen.getByRole("button", { name: /type/i }));
    await user.type(screen.getByLabelText("Typed answer"), "I built the API layer.");
    await user.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(
      await screen.findByText(/names the stack but not your contribution/i),
    ).toBeInTheDocument();
    // Appears in both the question panel and the session log.
    expect(screen.getAllByText("What did you personally implement?").length).toBeGreaterThan(0);
    const [url] = vi.mocked(apiClient.post).mock.calls[0]!;
    expect(url).toBe("/interviews/s1/answers");
  });

  it("navigates to the report when the backend completes the interview", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({}));
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        interviewer_observation: "Closing.",
        action_taken: "CLOSE_INTERVIEW",
        recommendation_overridden: false,
        stage: "COMPLETED",
        speech_summary: null,
        questions_used: 12,
        question_budget: 12,
        next_question: null,
        interview_completed: true,
        question_audio_base64: null,
        tts_warning: null,
      },
    });
    const user = userEvent.setup();
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    await screen.findByText("Tell me about your FastAPI experience.");
    await user.click(screen.getByRole("button", { name: /type/i }));
    await user.type(screen.getByLabelText("Typed answer"), "Thank you.");
    await user.click(screen.getByRole("button", { name: /submit answer/i }));
    expect(await screen.findByText("REPORT PAGE")).toBeInTheDocument();
  });

  it("shows a retryable inline error when submission fails", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({}));
    vi.mocked(apiClient.post).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    await screen.findByText("Tell me about your FastAPI experience.");
    await user.click(screen.getByRole("button", { name: /type/i }));
    await user.type(screen.getByLabelText("Typed answer"), "Answer.");
    await user.click(screen.getByRole("button", { name: /submit answer/i }));
    expect(await screen.findByRole("button", { name: /^retry$/i })).toBeInTheDocument();
  });

  it("routes pause through the backend session action", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail({}));
    vi.mocked(apiPost).mockResolvedValue({ ...detail({}), status: "PAUSED" });
    const user = userEvent.setup();
    render(
      <Providers>
        <InterviewRoomPage />
      </Providers>,
    );
    await screen.findByText("Tell me about your FastAPI experience.");
    await user.click(screen.getByRole("button", { name: /pause/i }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith("/interviews/s1/pause"));
  });
});
