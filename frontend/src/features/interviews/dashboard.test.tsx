/** Dashboard tests: states, filter, and search over backend sessions. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/client", () => ({ apiClient: { post: vi.fn() } }));
vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import type { InterviewSession } from "@/features/interviews/api";
import InterviewPage from "@/pages/InterviewPage";
import { apiGet } from "@/services/api/helpers";

function Providers({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

function session(partial: Partial<InterviewSession>): InterviewSession {
  return {
    id: "s1",
    resume_id: "r1",
    job_context_id: null,
    target_role_snapshot: "Backend Engineer",
    status: "COMPLETED",
    current_stage: "COMPLETED",
    interview_type: "MIXED",
    difficulty: "MEDIUM",
    duration_minutes: 20,
    question_budget: 12,
    question_budget_used: 12,
    failure_reason: null,
    created_at: "2026-07-01T10:00:00Z",
    updated_at: "2026-07-01T10:30:00Z",
    ...partial,
  };
}

describe("InterviewPage dashboard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the empty state when there are no interviews", async () => {
    vi.mocked(apiGet).mockResolvedValue({ interviews: [] });
    render(
      <Providers>
        <InterviewPage />
      </Providers>,
    );
    expect(await screen.findByText(/no interviews yet/i)).toBeInTheDocument();
  });

  it("shows the error state with retry when loading fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("network"));
    render(
      <Providers>
        <InterviewPage />
      </Providers>,
    );
    expect(await screen.findByText(/could not load your interviews/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("lists sessions and filters them by search text", async () => {
    vi.mocked(apiGet).mockImplementation((url: string) => {
      if (url === "/interviews") {
        return Promise.resolve({
          interviews: [
            session({ id: "s1", target_role_snapshot: "Backend Engineer", status: "RUNNING", current_stage: "BEHAVIORAL" }),
            session({ id: "s2", target_role_snapshot: "Data Scientist", status: "RUNNING", current_stage: "BEHAVIORAL" }),
          ],
        });
      }
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    render(
      <Providers>
        <InterviewPage />
      </Providers>,
    );
    expect(await screen.findByText(/Backend Engineer/)).toBeInTheDocument();
    expect(screen.getByText(/Data Scientist/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search"), "data");
    expect(screen.queryByText(/Backend Engineer/)).not.toBeInTheDocument();
    expect(screen.getByText(/Data Scientist/)).toBeInTheDocument();
  });
});
