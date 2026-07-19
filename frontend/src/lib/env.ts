/**
 * Validated frontend environment (Phase 9A).
 *
 * The ONLY values allowed here are public by design: the API base URL
 * and the Supabase URL + anon (publishable) key. Backend secrets never
 * appear in frontend env. Validation fails fast at startup with a clear
 * message instead of producing undefined-URL requests at runtime.
 */
import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_SUPABASE_URL: z.string().url(),
  VITE_SUPABASE_ANON_KEY: z.string().min(1),
});

const testDefaults = {
  VITE_API_BASE_URL: "http://localhost:8000/api/v1",
  VITE_SUPABASE_URL: "https://test-project.supabase.co",
  VITE_SUPABASE_ANON_KEY: "test-anon-key",
} satisfies z.infer<typeof envSchema>;

export function loadEnv(
  raw: Record<string, string | undefined> = import.meta.env,
  mode: string = import.meta.env.MODE,
): z.infer<typeof envSchema> {
  const source = mode === "test" ? { ...testDefaults, ...stripEmpty(raw) } : raw;
  const parsed = envSchema.safeParse(source);
  if (!parsed.success) {
    const missing = parsed.error.issues.map((issue) => issue.path.join(".")).join(", ");
    throw new Error(
      `Invalid frontend environment. Check .env.local against .env.example (problem with: ${missing}).`,
    );
  }
  return parsed.data;
}

function stripEmpty(raw: Record<string, string | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(raw).filter(([, value]) => typeof value === "string" && value.length > 0),
  ) as Record<string, string>;
}

export const env = loadEnv();
