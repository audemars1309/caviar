import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "@/store/auth";
import { useNotificationsStore } from "@/store/notifications";
import { applyThemeClass, resolveTheme, useThemeStore } from "@/store/theme";
import { useUiStore } from "@/store/ui";

describe("auth store", () => {
  beforeEach(() => useAuthStore.setState({ status: "loading", user: null }));

  it("starts in loading and transitions through auth states", () => {
    expect(useAuthStore.getState().status).toBe("loading");
    useAuthStore.getState().setAuthenticated({ id: "u1", email: "a@b.co" });
    expect(useAuthStore.getState()).toMatchObject({
      status: "authenticated",
      user: { id: "u1", email: "a@b.co" },
    });
    useAuthStore.getState().setUnauthenticated();
    expect(useAuthStore.getState()).toMatchObject({ status: "unauthenticated", user: null });
  });
});

describe("ui store", () => {
  it("toggles the sidebar and tracks modals", () => {
    const { toggleSidebar, openModal, closeModal } = useUiStore.getState();
    expect(useUiStore.getState().sidebarOpen).toBe(false);
    toggleSidebar();
    expect(useUiStore.getState().sidebarOpen).toBe(true);
    openModal("confirm-delete");
    expect(useUiStore.getState().activeModal).toBe("confirm-delete");
    closeModal();
    expect(useUiStore.getState().activeModal).toBeNull();
  });
});

describe("notifications store", () => {
  beforeEach(() => useNotificationsStore.getState().clear());

  it("adds newest-first, marks read, dismisses", () => {
    const store = useNotificationsStore.getState();
    store.add({ title: "First", kind: "info" });
    store.add({ title: "Second", kind: "success" });
    const items = useNotificationsStore.getState().notifications;
    expect(items.map((n) => n.title)).toEqual(["Second", "First"]);
    expect(items.every((n) => !n.read)).toBe(true);
    useNotificationsStore.getState().markAllRead();
    expect(useNotificationsStore.getState().notifications.every((n) => n.read)).toBe(true);
    const first = useNotificationsStore.getState().notifications[0];
    useNotificationsStore.getState().dismiss(first!.id);
    expect(useNotificationsStore.getState().notifications).toHaveLength(1);
  });
});

describe("theme", () => {
  it("resolves preferences deterministically", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("applies the dark class to the root element", () => {
    const root = document.createElement("html");
    applyThemeClass(root, "dark");
    expect(root.classList.contains("dark")).toBe(true);
    applyThemeClass(root, "light");
    expect(root.classList.contains("dark")).toBe(false);
  });

  it("persists preference changes", () => {
    useThemeStore.getState().setPreference("dark");
    expect(useThemeStore.getState().preference).toBe("dark");
    expect(localStorage.getItem("caviar-theme")).toContain('"dark"');
  });
});
