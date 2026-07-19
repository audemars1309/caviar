/**
 * Zod mirrors of the backend section content schemas (Phase 6
 * section_schemas.py) - same field names, same limits, so client
 * validation matches server validation and autosave never sends
 * payloads the backend would reject. The backend remains authoritative.
 */
import { z } from "zod";

export const SECTION_TYPES = [
  "PERSONAL_INFO",
  "SUMMARY",
  "EDUCATION",
  "SKILLS",
  "EXPERIENCE",
  "INTERNSHIPS",
  "PROJECTS",
  "CERTIFICATIONS",
  "ACHIEVEMENTS",
] as const;

export type SectionType = (typeof SECTION_TYPES)[number];

const short = z.string().max(200);
const shortOpt = short.nullable().optional();
const dateOpt = z.string().max(50).nullable().optional();

export const personalInfoSchema = z.object({
  full_name: z.string().min(1, "Name is required.").max(200),
  email: z.string().max(320).nullable().optional(),
  phone: z.string().max(50).nullable().optional(),
  location: shortOpt,
  linkedin_url: z.string().max(500).nullable().optional(),
  github_url: z.string().max(500).nullable().optional(),
  website_url: z.string().max(500).nullable().optional(),
});

export const summarySchema = z.object({
  text: z.string().min(1, "Summary cannot be empty.").max(2000),
});

export const educationEntrySchema = z.object({
  institution: z.string().min(1, "Institution is required.").max(200),
  degree: z.string().min(1, "Degree is required.").max(200),
  field_of_study: shortOpt,
  location: shortOpt,
  start_date: dateOpt,
  end_date: dateOpt,
  gpa: z.string().max(20).nullable().optional(),
  highlights: z.array(z.string().min(1)).max(10).default([]),
});

export const educationSchema = z.object({
  entries: z.array(educationEntrySchema).min(1).max(10),
});

export const skillGroupSchema = z.object({
  name: z.string().min(1, "Group name is required.").max(100),
  skills: z.array(z.string().min(1)).min(1, "Add at least one skill.").max(40),
});

export const skillsSchema = z.object({
  groups: z.array(skillGroupSchema).min(1).max(15),
});

export const experienceEntrySchema = z.object({
  company: z.string().min(1, "Company is required.").max(200),
  title: z.string().min(1, "Title is required.").max(200),
  location: shortOpt,
  start_date: dateOpt,
  end_date: dateOpt,
  bullets: z.array(z.string().min(1)).max(20).default([]),
});

export const experienceSchema = z.object({
  entries: z.array(experienceEntrySchema).min(1).max(20),
});

export const projectEntrySchema = z.object({
  name: z.string().min(1, "Project name is required.").max(200),
  description: z.string().max(1000).nullable().optional(),
  technologies: z.array(z.string().min(1)).max(30).default([]),
  url: z.string().max(500).nullable().optional(),
  bullets: z.array(z.string().min(1)).max(20).default([]),
});

export const projectsSchema = z.object({
  entries: z.array(projectEntrySchema).min(1).max(20),
});

export const certificationEntrySchema = z.object({
  name: z.string().min(1, "Certification name is required.").max(200),
  issuer: shortOpt,
  date: dateOpt,
  credential_url: z.string().max(500).nullable().optional(),
});

export const certificationsSchema = z.object({
  entries: z.array(certificationEntrySchema).min(1).max(20),
});

export const achievementEntrySchema = z.object({
  text: z.string().min(1, "Achievement text is required.").max(500),
  date: dateOpt,
});

export const achievementsSchema = z.object({
  entries: z.array(achievementEntrySchema).min(1).max(20),
});

export const SECTION_SCHEMAS = {
  PERSONAL_INFO: personalInfoSchema,
  SUMMARY: summarySchema,
  EDUCATION: educationSchema,
  SKILLS: skillsSchema,
  EXPERIENCE: experienceSchema,
  INTERNSHIPS: experienceSchema, // same shape by backend design
  PROJECTS: projectsSchema,
  CERTIFICATIONS: certificationsSchema,
  ACHIEVEMENTS: achievementsSchema,
} as const satisfies Record<SectionType, z.ZodTypeAny>;

export type PersonalInfoContent = z.infer<typeof personalInfoSchema>;
export type SummaryContent = z.infer<typeof summarySchema>;
export type EducationContent = z.infer<typeof educationSchema>;
export type SkillsContent = z.infer<typeof skillsSchema>;
export type ExperienceContent = z.infer<typeof experienceSchema>;
export type ProjectsContent = z.infer<typeof projectsSchema>;
export type CertificationsContent = z.infer<typeof certificationsSchema>;
export type AchievementsContent = z.infer<typeof achievementsSchema>;

export type SectionContentMap = {
  PERSONAL_INFO: PersonalInfoContent;
  SUMMARY: SummaryContent;
  EDUCATION: EducationContent;
  SKILLS: SkillsContent;
  EXPERIENCE: ExperienceContent;
  INTERNSHIPS: ExperienceContent;
  PROJECTS: ProjectsContent;
  CERTIFICATIONS: CertificationsContent;
  ACHIEVEMENTS: AchievementsContent;
};

export const SECTION_LABELS: Record<SectionType, string> = {
  PERSONAL_INFO: "Personal Information",
  SUMMARY: "Summary",
  EXPERIENCE: "Experience",
  INTERNSHIPS: "Internships",
  PROJECTS: "Projects",
  EDUCATION: "Education",
  SKILLS: "Skills",
  CERTIFICATIONS: "Certifications",
  ACHIEVEMENTS: "Achievements",
};

/** Sections whose bullets are eligible for AI bullet assistance
 *  (mirrors backend BULLET_SECTION_TYPES). */
export const BULLET_SECTION_TYPES: readonly SectionType[] = [
  "EXPERIENCE",
  "INTERNSHIPS",
  "PROJECTS",
];

export function validateSectionContent(
  sectionType: SectionType,
  content: unknown,
): { ok: true; content: Record<string, unknown> } | { ok: false; message: string } {
  const parsed = SECTION_SCHEMAS[sectionType].safeParse(content);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    return { ok: false, message: first ? first.message : "Invalid section content." };
  }
  return { ok: true, content: parsed.data };
}
