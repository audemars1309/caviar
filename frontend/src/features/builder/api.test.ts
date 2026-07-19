import { describe, expect, it } from "vitest";

import { generationFilename } from "@/features/builder/api";

describe("generationFilename", () => {
  it("slugifies the project title", () => {
    expect(generationFilename("Backend Engineer 2026")).toBe("backend-engineer-2026.pdf");
  });

  it("collapses punctuation and whitespace", () => {
    expect(generationFilename("  C++ / ML — Résumé!  ")).toBe("c-ml-r-sum.pdf");
  });

  it("falls back to resume.pdf for empty or symbol-only titles", () => {
    expect(generationFilename("")).toBe("resume.pdf");
    expect(generationFilename("###")).toBe("resume.pdf");
  });

  it("caps the base name at 60 characters", () => {
    const name = generationFilename("x".repeat(200));
    expect(name.length).toBeLessThanOrEqual(64); // 60 + ".pdf"
    expect(name.endsWith(".pdf")).toBe(true);
  });
});
