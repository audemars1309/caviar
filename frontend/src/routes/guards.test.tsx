/** Route guard tests: protected redirects, loading hold, public-only
 *  redirect for signed-in users. */
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";

import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { PublicOnlyRoute } from "@/routes/PublicOnlyRoute";
import { useAuthStore } from "@/store/auth";

function renderGuarded(initialPath: string) {
  const router = createMemoryRouter(
    [
      {
        element: <ProtectedRoute />,
        children: [{ path: "/dashboard", element: <p>Private dashboard</p> }],
      },
      {
        element: <PublicOnlyRoute />,
        children: [{ path: "/login", element: <p>Login page</p> }],
      },
    ],
    { initialEntries: [initialPath] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("route guards", () => {
  beforeEach(() => useAuthStore.setState({ status: "loading", user: null }));

  it("holds on a loading state while the session restores", () => {
    renderGuarded("/dashboard");
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Private dashboard")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", async () => {
    useAuthStore.setState({ status: "unauthenticated", user: null });
    const router = renderGuarded("/dashboard");
    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("renders protected content for authenticated users", async () => {
    useAuthStore.setState({
      status: "authenticated",
      user: { id: "u1", email: "a@b.co" },
    });
    renderGuarded("/dashboard");
    expect(await screen.findByText("Private dashboard")).toBeInTheDocument();
  });

  it("keeps signed-in users out of login", async () => {
    useAuthStore.setState({
      status: "authenticated",
      user: { id: "u1", email: "a@b.co" },
    });
    const router = renderGuarded("/login");
    expect(router.state.location.pathname).toBe("/dashboard");
  });
});
