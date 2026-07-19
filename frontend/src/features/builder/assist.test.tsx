/** AI assist integration tests: request payload shapes match the
 *  backend AssistRequest contract, and results only enter builder
 *  content through an explicit user apply action (the user is the
 *  write path - assist never persists). */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import type { SummaryAssistResult } from "@/features/builder/api";
import { SummaryAssistResultView } from "@/features/builder/components/AssistPanel";
import { useAssist } from "@/features/builder/hooks";
import { apiPost } from "@/services/api/helpers";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const summaryResult: SummaryAssistResult = {
  assist_type: "IMPROVE_SUMMARY",
  schema_version: "content-assist-1.0.0",
  ai_model: "gemini-test",
  improved_summary: "Backend engineer who ships production FastAPI systems.",
  changes_explained: ["Tightened phrasing"],
  missing_fact_questions: ["Can you estimate the latency reduction?"],
  action_verb_suggestions: ["Engineered"],
  unsupported_numbers: ["40%"],
};

describe("useAssist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("posts the backend AssistRequest shape for bullet improvement", async () => {
    vi.mocked(apiPost).mockResolvedValue({ bullets: [], action_verb_suggestions: [] });
    const { result } = renderHook(() => useAssist("proj-1"), { wrapper });
    result.current.mutate({
      assist_type: "IMPROVE_BULLETS",
      section_type: "EXPERIENCE",
      entry_index: 2,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiPost).toHaveBeenCalledWith("/resume-builder/projects/proj-1/assist", {
      assist_type: "IMPROVE_BULLETS",
      section_type: "EXPERIENCE",
      entry_index: 2,
    });
  });

  it("exposes backend failures for inline retry UI", async () => {
    vi.mocked(apiPost).mockRejectedValue(new Error("AI service unavailable"));
    const { result } = renderHook(() => useAssist("proj-1"), { wrapper });
    result.current.mutate({ assist_type: "GENERATE_SUMMARY" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("AI service unavailable");
  });
});

describe("SummaryAssistResultView", () => {
  it("shows grounding checks and applies only on explicit user action", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    render(<SummaryAssistResultView result={summaryResult} onApply={onApply} />);

    // Fabrication-guard output is surfaced, never silently accepted.
    expect(screen.getByText(/Grounding check/i)).toBeInTheDocument();
    expect(screen.getByText(/40%/)).toBeInTheDocument();
    expect(screen.getByText(/latency reduction/i)).toBeInTheDocument();

    expect(onApply).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /use this/i }));
    expect(onApply).toHaveBeenCalledExactlyOnceWith(
      "Backend engineer who ships production FastAPI systems.",
    );
  });
});
