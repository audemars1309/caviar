/** Builder autosave integration: validate-before-send (invalid drafts
 *  never hit the API), debounce collapses keystrokes into one PUT, and
 *  server failures surface as a retryable error state. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import { useSectionAutosave } from "@/features/builder/hooks";
import { apiPut } from "@/services/api/helpers";
import { ApiError } from "@/types/api";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useSectionAutosave", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it("never sends invalid drafts and reports the schema message", async () => {
    const { result } = renderHook(() => useSectionAutosave("proj-1", "SUMMARY"), { wrapper });
    act(() => result.current.onChange({ text: "" }));
    void act(() => vi.advanceTimersByTime(900));
    await waitFor(() => expect(result.current.state.status).toBe("invalid"));
    expect(apiPut).not.toHaveBeenCalled();
    expect(result.current.state.message).toMatch(/empty/i);
  });

  it("debounces keystrokes into a single PUT with the final content", async () => {
    vi.mocked(apiPut).mockResolvedValue({
      id: "s1",
      section_type: "SUMMARY",
      sort_order: 1,
      content: { text: "Final draft" },
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    const { result } = renderHook(() => useSectionAutosave("proj-1", "SUMMARY"), { wrapper });
    act(() => {
      result.current.onChange({ text: "F" });
      result.current.onChange({ text: "Final" });
      result.current.onChange({ text: "Final draft" });
    });
    void act(() => vi.advanceTimersByTime(900));
    await waitFor(() => expect(result.current.state.status).toBe("saved"));
    expect(apiPut).toHaveBeenCalledTimes(1);
    expect(apiPut).toHaveBeenCalledWith("/resume-builder/projects/proj-1/sections/SUMMARY", {
      content: { text: "Final draft" },
    });
  });

  it("surfaces server failures as a retryable error state", async () => {
    vi.mocked(apiPut).mockRejectedValue(
      new ApiError({ status: 403, code: "forbidden", message: "RLS denied" }),
    );
    const { result } = renderHook(() => useSectionAutosave("proj-1", "SUMMARY"), { wrapper });
    act(() => result.current.onChange({ text: "Valid summary" }));
    void act(() => vi.advanceTimersByTime(900));
    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(result.current.state.message).toBe("RLS denied");
  });
});
