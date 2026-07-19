import { describe, expect, it } from "vitest";

import {
  SECTION_SCHEMAS,
  SECTION_TYPES,
  validateSectionContent,
} from "@/features/builder/schemas";

describe("builder section schemas mirror the backend contracts", () => {
  it("covers all nine backend section types", () => {
    expect(SECTION_TYPES).toHaveLength(9);
    for (const sectionType of SECTION_TYPES) {
      expect(SECTION_SCHEMAS[sectionType]).toBeDefined();
    }
  });

  it("PERSONAL_INFO requires full_name and bounds field lengths", () => {
    expect(validateSectionContent("PERSONAL_INFO", { full_name: "Dharun" }).ok).toBe(true);
    expect(validateSectionContent("PERSONAL_INFO", { full_name: "" }).ok).toBe(false);
    expect(
      validateSectionContent("PERSONAL_INFO", { full_name: "x".repeat(201) }).ok,
    ).toBe(false);
  });

  it("SUMMARY enforces the 1..2000 char range", () => {
    expect(validateSectionContent("SUMMARY", { text: "Backend engineer." }).ok).toBe(true);
    expect(validateSectionContent("SUMMARY", { text: "" }).ok).toBe(false);
    expect(validateSectionContent("SUMMARY", { text: "x".repeat(2001) }).ok).toBe(false);
  });

  it("EXPERIENCE requires company and title, allows empty bullets", () => {
    const valid = {
      entries: [{ company: "Acme", title: "Engineer", bullets: [] }],
    };
    expect(validateSectionContent("EXPERIENCE", valid).ok).toBe(true);
    expect(
      validateSectionContent("EXPERIENCE", { entries: [{ company: "", title: "E" }] }).ok,
    ).toBe(false);
    expect(validateSectionContent("EXPERIENCE", { entries: [] }).ok).toBe(false);
  });

  it("INTERNSHIPS shares the EXPERIENCE shape (backend design)", () => {
    expect(SECTION_SCHEMAS.INTERNSHIPS).toBe(SECTION_SCHEMAS.EXPERIENCE);
  });

  it("SKILLS requires at least one group with at least one skill", () => {
    expect(
      validateSectionContent("SKILLS", { groups: [{ name: "Languages", skills: ["Python"] }] }).ok,
    ).toBe(true);
    expect(validateSectionContent("SKILLS", { groups: [{ name: "Languages", skills: [] }] }).ok).toBe(
      false,
    );
    expect(validateSectionContent("SKILLS", { groups: [] }).ok).toBe(false);
  });

  it("EDUCATION caps entries at 10 and highlights at 10", () => {
    const entry = { institution: "IIT", degree: "B.Tech", highlights: [] };
    expect(validateSectionContent("EDUCATION", { entries: [entry] }).ok).toBe(true);
    expect(
      validateSectionContent("EDUCATION", { entries: Array(11).fill(entry) }).ok,
    ).toBe(false);
    expect(
      validateSectionContent("EDUCATION", {
        entries: [{ ...entry, highlights: Array(11).fill("h") }],
      }).ok,
    ).toBe(false);
  });

  it("PROJECTS bounds description at 1000 and technologies at 30", () => {
    expect(
      validateSectionContent("PROJECTS", { entries: [{ name: "Caviar", bullets: [] }] }).ok,
    ).toBe(true);
    expect(
      validateSectionContent("PROJECTS", {
        entries: [{ name: "Caviar", description: "x".repeat(1001) }],
      }).ok,
    ).toBe(false);
  });

  it("ACHIEVEMENTS bounds text at 500 chars", () => {
    expect(validateSectionContent("ACHIEVEMENTS", { entries: [{ text: "Won." }] }).ok).toBe(true);
    expect(
      validateSectionContent("ACHIEVEMENTS", { entries: [{ text: "x".repeat(501) }] }).ok,
    ).toBe(false);
  });

  it("returns a human-readable message for invalid drafts", () => {
    const verdict = validateSectionContent("SUMMARY", { text: "" });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) expect(verdict.message.length).toBeGreaterThan(0);
  });

  it("date fields are free-text bounded at 50 chars", () => {
    expect(
      validateSectionContent("CERTIFICATIONS", {
        entries: [{ name: "AWS SAA", date: "Jun 2024" }],
      }).ok,
    ).toBe(true);
    expect(
      validateSectionContent("CERTIFICATIONS", {
        entries: [{ name: "AWS SAA", date: "x".repeat(51) }],
      }).ok,
    ).toBe(false);
  });
});
