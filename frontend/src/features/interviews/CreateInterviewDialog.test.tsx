/** Interview creation: input validation before submission (resume
 *  required, duration 5-60) and the exact create payload. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

import { CreateInterviewDialog } from "@/features/interviews/components/CreateInterviewDialog";
import { apiGet, apiPost } from "@/services/api/helpers";

function Providers({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

const resume = {
  id: "r1",
  original_filename: "cv.pdf",
  file_size_bytes: 100,
  mime_type: "application/pdf",
  extraction_status: "EXTRACTED",
  extraction_failure_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("CreateInterviewDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiGet).mockImplementation((url: string) => {
      if (url === "/resumes") return Promise.resolve({ resumes: [resume] });
      if (url === "/job-contexts") return Promise.resolve({ job_contexts: [] });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  });

  it("disables creation until a resume is selected", async () => {
    render(
      <Providers>
        <CreateInterviewDialog open onOpenChange={() => undefined} />
      </Providers>,
    );
    const submit = await screen.findByRole("button", { name: /create interview/i });
    expect(submit).toBeDisabled();
  });

  it("validates duration bounds (5-60 minutes)", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <CreateInterviewDialog open onOpenChange={() => undefined} />
      </Providers>,
    );
    const duration = await screen.findByLabelText(/duration/i);
    await user.clear(duration);
    await user.type(duration, "90");
    expect(screen.getByText(/between 5 and 60/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create interview/i })).toBeDisabled();
  });

  it("submits the exact backend payload once valid", async () => {
    const user = userEvent.setup();
    vi.mocked(apiPost).mockResolvedValue({ id: "s1", status: "PENDING" });
    render(
      <Providers>
        <CreateInterviewDialog open onOpenChange={() => undefined} />
      </Providers>,
    );
    await user.click(await screen.findByLabelText("Resume"));
    await user.click(await screen.findByRole("option", { name: "cv.pdf" }));
    await user.click(screen.getByRole("button", { name: /create interview/i }));
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith("/interviews", {
        resume_id: "r1",
        job_context_id: null,
        interview_type: "MIXED",
        difficulty: "MEDIUM",
        duration_minutes: 20,
      }),
    );
  });
});
