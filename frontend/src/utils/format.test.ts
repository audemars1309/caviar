import { describe, expect, it } from "vitest";

import { formatDate, formatDuration, formatFileSize } from "@/utils/format";

describe("formatFileSize", () => {
  it("formats across units", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
    expect(formatFileSize(5_242_880)).toBe("5 MB");
  });

  it("handles invalid input safely", () => {
    expect(formatFileSize(-1)).toBe("0 B");
    expect(formatFileSize(Number.NaN)).toBe("0 B");
  });
});

describe("formatDate", () => {
  it("formats ISO dates and rejects garbage", () => {
    expect(formatDate("2026-07-15T10:00:00Z", "en-US")).toMatch(/Jul 15, 2026/);
    expect(formatDate("not-a-date")).toBe("—");
  });
});

describe("formatDuration", () => {
  it("formats mm:ss with padding", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(600)).toBe("10:00");
    expect(formatDuration(-5)).toBe("0:00");
  });
});
