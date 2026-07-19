/**
 * In-app notification center state (distinct from transient toasts,
 * which sonner renders directly). Bounded list, newest first.
 */
import { create } from "zustand";

export interface AppNotification {
  id: string;
  title: string;
  description?: string;
  kind: "info" | "success" | "warning" | "error";
  createdAt: number;
  read: boolean;
}

const MAX_NOTIFICATIONS = 50;

interface NotificationsState {
  notifications: AppNotification[];
  add: (notification: Omit<AppNotification, "id" | "createdAt" | "read">) => void;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  clear: () => void;
}

export const useNotificationsStore = create<NotificationsState>((set) => ({
  notifications: [],
  add: (notification) =>
    set((state) => ({
      notifications: [
        { ...notification, id: crypto.randomUUID(), createdAt: Date.now(), read: false },
        ...state.notifications,
      ].slice(0, MAX_NOTIFICATIONS),
    })),
  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((item) => ({ ...item, read: true })),
    })),
  dismiss: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((item) => item.id !== id),
    })),
  clear: () => set({ notifications: [] }),
}));
