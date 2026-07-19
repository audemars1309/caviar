/**
 * The centralized API client (Phase 9A). Every backend call in the
 * application goes through this axios instance - never scatter fetch
 * calls in components.
 *
 * Request interceptor: injects the caller's current Supabase access
 * token (supabase-js refreshes it automatically before expiry).
 * Response interceptor: on 401, attempts ONE explicit session refresh
 * and retries the original request once; a second 401 signs the user
 * out (the AuthProvider reacts to the SIGNED_OUT event). All errors are
 * normalized to the typed ApiError shape.
 */
import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";

import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { toApiError } from "@/services/api/errors";

interface AuthGateway {
  getAccessToken(): Promise<string | null>;
  refreshAccessToken(): Promise<string | null>;
  signOut(): Promise<void>;
}

export const supabaseAuthGateway: AuthGateway = {
  async getAccessToken() {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  },
  async refreshAccessToken() {
    const { data, error } = await supabase.auth.refreshSession();
    return error ? null : (data.session?.access_token ?? null);
  },
  async signOut() {
    await supabase.auth.signOut();
  },
};

interface RetriableConfig extends InternalAxiosRequestConfig {
  caviarRetried?: boolean;
}

export function createApiClient(
  gateway: AuthGateway = supabaseAuthGateway,
  baseURL: string = env.VITE_API_BASE_URL,
): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 120_000 });

  client.interceptors.request.use(async (config) => {
    const token = await gateway.getAccessToken();
    if (token) config.headers.set("Authorization", `Bearer ${token}`);
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const config = error.config as RetriableConfig | undefined;
      if (error.response?.status === 401 && config && !config.caviarRetried) {
        const token = await gateway.refreshAccessToken();
        if (token) {
          config.caviarRetried = true;
          // The retry re-enters the request interceptor, which injects
          // the gateway's CURRENT (post-refresh) token - no manual
          // header write that the interceptor would overwrite anyway.
          return client.request(config);
        }
        await gateway.signOut();
      }
      return Promise.reject(toApiError(error));
    },
  );

  return client;
}

export const apiClient = createApiClient();
