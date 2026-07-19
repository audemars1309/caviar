import { describe, expect, it } from "vitest";

import { loadEnv } from "@/lib/env";

describe("loadEnv", () => {
  it("accepts a complete environment", () => {
    const env = loadEnv(
      {
        VITE_API_BASE_URL: "https://api.caviar.example/api/v1",
        VITE_SUPABASE_URL: "https://ref.supabase.co",
        VITE_SUPABASE_ANON_KEY: "anon-key",
      },
      "production",
    );
    expect(env.VITE_API_BASE_URL).toBe("https://api.caviar.example/api/v1");
  });

  it("rejects missing or invalid values outside test mode", () => {
    expect(() => loadEnv({ VITE_API_BASE_URL: "not-a-url" }, "production")).toThrow(
      /Invalid frontend environment/,
    );
  });

  it("falls back to safe defaults in test mode", () => {
    const env = loadEnv({}, "test");
    expect(env.VITE_SUPABASE_URL).toContain("supabase.co");
  });
});
