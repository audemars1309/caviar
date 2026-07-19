/**
 * API client tests: token injection, 401 -> single refresh -> retry,
 * sign-out on failed refresh, typed error normalization. The axios
 * instance runs against an injected fake adapter - no network.
 */
import type { AxiosRequestConfig } from "axios";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/services/api/client";
import type { ApiError } from "@/types/api";

function makeGateway(tokens: { initial: string | null; refreshed: string | null }) {
  // Stateful, like supabase-js: after a successful refresh,
  // getAccessToken returns the refreshed token.
  let current = tokens.initial;
  return {
    getAccessToken: vi.fn(async () => current),
    refreshAccessToken: vi.fn(async () => {
      if (tokens.refreshed) current = tokens.refreshed;
      return tokens.refreshed;
    }),
    signOut: vi.fn(async () => undefined),
  };
}

function installAdapter(
  client: ReturnType<typeof createApiClient>,
  handler: (config: AxiosRequestConfig, attempt: number) => { status: number; data: unknown },
) {
  let attempts = 0;
  client.defaults.adapter = (config) => {
    attempts += 1;
    const { status, data } = handler(config, attempts);
    const response = { data, status, statusText: String(status), headers: {}, config };
    if (status >= 400) {
      const error = Object.assign(new Error(`Request failed with status code ${status}`), {
        isAxiosError: true,
        config,
        response,
        toJSON: () => ({}),
      });
      return Promise.reject(error);
    }
    return Promise.resolve(response);
  };
  return () => attempts;
}

describe("createApiClient", () => {
  it("injects the bearer token on requests", async () => {
    const gateway = makeGateway({ initial: "token-1", refreshed: null });
    const client = createApiClient(gateway, "http://test.local");
    let seenAuth: string | undefined;
    installAdapter(client, (config) => {
      seenAuth = (config.headers as Record<string, string>).Authorization;
      return { status: 200, data: { ok: true } };
    });
    const response = await client.get("/ping");
    expect(response.data).toEqual({ ok: true });
    expect(seenAuth).toBe("Bearer token-1");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    const gateway = makeGateway({ initial: "stale", refreshed: "fresh" });
    const client = createApiClient(gateway, "http://test.local");
    const auths: Array<string | undefined> = [];
    installAdapter(client, (config, attempt) => {
      auths.push((config.headers as Record<string, string>).Authorization);
      if (attempt === 1) return { status: 401, data: {} };
      return { status: 200, data: { ok: true } };
    });
    const response = await client.get("/protected");
    expect(response.status).toBe(200);
    expect(gateway.refreshAccessToken).toHaveBeenCalledTimes(1);
    expect(auths).toEqual(["Bearer stale", "Bearer fresh"]);
    expect(gateway.signOut).not.toHaveBeenCalled();
  });

  it("signs out when the refresh fails and surfaces a typed error", async () => {
    const gateway = makeGateway({ initial: "stale", refreshed: null });
    const client = createApiClient(gateway, "http://test.local");
    installAdapter(client, () => ({
      status: 401,
      data: { error: { code: "invalid_token", message: "Token expired." } },
    }));
    const failure = (await client.get("/protected").catch((error) => error)) as ApiError;
    expect(gateway.signOut).toHaveBeenCalledTimes(1);
    expect(failure.status).toBe(401);
    expect(failure.code).toBe("invalid_token");
    expect(failure.message).toBe("Token expired.");
  });

  it("normalizes backend error envelopes without retrying non-401s", async () => {
    const gateway = makeGateway({ initial: "token", refreshed: "never" });
    const client = createApiClient(gateway, "http://test.local");
    const attempts = installAdapter(client, () => ({
      status: 409,
      data: { error: { code: "illegal_interview_transition", message: "Cannot pause." } },
    }));
    const failure = (await client.post("/interviews/x/pause").catch((error) => error)) as ApiError;
    expect(failure).toMatchObject({ status: 409, code: "illegal_interview_transition" });
    expect(attempts()).toBe(1);
    expect(gateway.refreshAccessToken).not.toHaveBeenCalled();
  });
});
