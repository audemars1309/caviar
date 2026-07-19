/** API-integration test for the download flow: signed URL fetched from
 *  the backend, then a browser download is triggered with the slugified
 *  filename. The apiClient is mocked - no network. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import { useDownloadGeneration } from "@/features/builder/hooks";
import { apiGet } from "@/services/api/helpers";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useDownloadGeneration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches the signed URL and clicks a download anchor", async () => {
    vi.mocked(apiGet).mockResolvedValue({ url: "https://signed.example/x.pdf", expires_in_seconds: 60 });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const { result } = renderHook(() => useDownloadGeneration(), { wrapper });
    result.current.mutate({ generationId: "gen-1", filename: "backend-engineer.pdf" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith("/resume-generations/gen-1/download");
    expect(clickSpy).toHaveBeenCalledTimes(1);
    clickSpy.mockRestore();
  });

  it("surfaces backend errors without triggering a download", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("Generation is not COMPLETED"));
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const { result } = renderHook(() => useDownloadGeneration(), { wrapper });
    result.current.mutate({ generationId: "gen-2", filename: "resume.pdf" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});
