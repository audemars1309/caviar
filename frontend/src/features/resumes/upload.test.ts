import { describe, expect, it } from "vitest";

import {
  RESUME_MAX_FILE_SIZE_BYTES,
  validateResumeFile,
  type Resume,
} from "@/features/resumes/api";

function makeFile(name: string, size: number, type = "application/pdf"): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

const existing: Resume[] = [
  {
    id: "r1",
    original_filename: "old.pdf",
    file_size_bytes: 1234,
    mime_type: "application/pdf",
    extraction_status: "EXTRACTED",
    extraction_failure_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("validateResumeFile", () => {
  it("accepts a normal PDF", () => {
    expect(validateResumeFile(makeFile("cv.pdf", 5000), existing)).toEqual({ ok: true });
  });

  it("accepts a PDF identified by extension when MIME is generic", () => {
    expect(
      validateResumeFile(makeFile("cv.PDF", 5000, "application/octet-stream"), existing).ok,
    ).toBe(true);
  });

  it("rejects non-PDF files (DOCX not supported by the backend)", () => {
    const verdict = validateResumeFile(
      makeFile("cv.docx", 5000, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
      existing,
    );
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) expect(verdict.reason).toMatch(/PDF/);
  });

  it("rejects empty files", () => {
    expect(validateResumeFile(makeFile("cv.pdf", 0), existing).ok).toBe(false);
  });

  it("rejects files over the 10 MB limit", () => {
    expect(
      validateResumeFile(makeFile("cv.pdf", RESUME_MAX_FILE_SIZE_BYTES + 1), existing).ok,
    ).toBe(false);
  });

  it("accepts a file exactly at the limit", () => {
    expect(
      validateResumeFile(makeFile("cv.pdf", RESUME_MAX_FILE_SIZE_BYTES), existing).ok,
    ).toBe(true);
  });

  it("rejects duplicates by name + size", () => {
    const verdict = validateResumeFile(makeFile("old.pdf", 1234), existing);
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) expect(verdict.reason).toMatch(/already uploaded/);
  });

  it("allows same name with different size (a genuinely new version)", () => {
    expect(validateResumeFile(makeFile("old.pdf", 9999), existing).ok).toBe(true);
  });
});
