/** AuthProvider tests: session restoration and auth-event syncing into
 *  the store, with supabase-js fully mocked. */
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/store/auth";

const getSession = vi.fn();
const onAuthStateChange = vi.fn();

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: { get getSession() { return getSession; }, get onAuthStateChange() { return onAuthStateChange; } } },
}));

const { AuthProvider } = await import("@/providers/AuthProvider");

describe("AuthProvider", () => {
  beforeEach(() => {
    useAuthStore.setState({ status: "loading", user: null });
    getSession.mockReset();
    onAuthStateChange.mockReset();
    onAuthStateChange.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    });
  });

  it("restores an existing session into the store", async () => {
    getSession.mockResolvedValue({
      data: { session: { user: { id: "u1", email: "a@b.co" } } },
    });
    render(<AuthProvider>{null}</AuthProvider>);
    await waitFor(() =>
      expect(useAuthStore.getState()).toMatchObject({
        status: "authenticated",
        user: { id: "u1", email: "a@b.co" },
      }),
    );
  });

  it("marks unauthenticated when no session exists", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    render(<AuthProvider>{null}</AuthProvider>);
    await waitFor(() =>
      expect(useAuthStore.getState().status).toBe("unauthenticated"),
    );
  });

  it("follows sign-in and sign-out auth events", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    render(<AuthProvider>{null}</AuthProvider>);
    await waitFor(() => expect(onAuthStateChange).toHaveBeenCalled());
    const callback = onAuthStateChange.mock.calls[0]?.[0] as (
      event: string,
      session: { user: { id: string; email: string | null } } | null,
    ) => void;
    callback("SIGNED_IN", { user: { id: "u2", email: "c@d.co" } });
    expect(useAuthStore.getState().status).toBe("authenticated");
    callback("SIGNED_OUT", null);
    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });
});
