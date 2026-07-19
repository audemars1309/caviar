import { describe, expect, it } from "vitest";

import { loginSchema, signupSchema } from "@/features/auth/schemas";

describe("loginSchema", () => {
  it("accepts valid credentials", () => {
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true);
  });

  it("rejects invalid email and empty password", () => {
    const result = loginSchema.safeParse({ email: "nope", password: "" });
    expect(result.success).toBe(false);
  });
});

describe("signupSchema", () => {
  const base = { email: "a@b.co", password: "longenough", confirmPassword: "longenough" };

  it("accepts matching valid values", () => {
    expect(signupSchema.safeParse(base).success).toBe(true);
  });

  it("rejects short passwords", () => {
    expect(signupSchema.safeParse({ ...base, password: "short", confirmPassword: "short" }).success).toBe(false);
  });

  it("rejects mismatched confirmation with the error on confirmPassword", () => {
    const result = signupSchema.safeParse({ ...base, confirmPassword: "different1" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.path.includes("confirmPassword"))).toBe(true);
    }
  });
});
