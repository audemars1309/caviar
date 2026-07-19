/**
 * Live structured preview approximating the caviar_classic template:
 * same section order, typography hierarchy, and content - rendered as
 * HTML at A4 proportions with zoom and responsive scaling. It updates
 * live from builder state. The authoritative document is ALWAYS the
 * backend-generated PDF; this preview never runs LaTeX in the browser.
 */
import { ZoomIn, ZoomOut } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { SectionContentMap, SectionType } from "@/features/builder/schemas";
import { SECTION_LABELS } from "@/features/builder/schemas";

const A4_WIDTH_PX = 794; // 210mm @ 96dpi
const A4_HEIGHT_PX = 1123;
const ZOOM_LEVELS = [0.5, 0.65, 0.8, 1, 1.25] as const;

type PartialContent = { [K in SectionType]?: SectionContentMap[K] };

const PREVIEW_ORDER: SectionType[] = [
  "SUMMARY",
  "EXPERIENCE",
  "INTERNSHIPS",
  "PROJECTS",
  "EDUCATION",
  "SKILLS",
  "CERTIFICATIONS",
  "ACHIEVEMENTS",
];

function DateRange({ start, end }: { start?: string | null; end?: string | null }) {
  if (!start && !end) return null;
  return (
    <span className="whitespace-nowrap text-[0.7rem] text-neutral-500">
      {[start, end].filter(Boolean).join(" – ")}
    </span>
  );
}

function PreviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h2 className="border-b border-neutral-300 pb-0.5 text-[0.75rem] font-bold uppercase tracking-wider text-neutral-800">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function ResumePreview({ content }: { content: PartialContent }) {
  const [zoomIndex, setZoomIndex] = useState(2);
  const zoom = ZOOM_LEVELS[zoomIndex] ?? 0.8;

  const personal = content.PERSONAL_INFO;
  const pageCountEstimate = useMemo(() => {
    // Rough content-volume estimate for the multi-page indicator; the
    // backend's PDF validator reports the real page count.
    const chars = JSON.stringify(content).length;
    return Math.max(1, Math.ceil(chars / 3200));
  }, [content]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Live preview (approximate) · ~{pageCountEstimate} page{pageCountEstimate > 1 ? "s" : ""} ·
          the generated PDF is authoritative
        </p>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom out"
            disabled={zoomIndex === 0}
            onClick={() => setZoomIndex((index) => Math.max(0, index - 1))}
          >
            <ZoomOut aria-hidden />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums text-muted-foreground">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom in"
            disabled={zoomIndex === ZOOM_LEVELS.length - 1}
            onClick={() => setZoomIndex((index) => Math.min(ZOOM_LEVELS.length - 1, index + 1))}
          >
            <ZoomIn aria-hidden />
          </Button>
        </div>
      </div>

      <div className="overflow-auto rounded-lg border bg-muted/40 p-4">
        <div
          className="origin-top-left"
          style={{ transform: `scale(${zoom})`, width: A4_WIDTH_PX, height: "fit-content" }}
        >
          <article
            aria-label="Resume preview"
            className="space-y-4 bg-white p-10 font-serif text-[0.8rem] leading-snug text-neutral-900 shadow-sm"
            style={{ width: A4_WIDTH_PX, minHeight: A4_HEIGHT_PX }}
          >
            <header className="space-y-1 text-center">
              <h1 className="text-2xl font-bold tracking-wide">
                {personal?.full_name || "Your Name"}
              </h1>
              <p className="text-[0.7rem] text-neutral-600">
                {[personal?.email, personal?.phone, personal?.location]
                  .filter(Boolean)
                  .join(" · ") || "email · phone · location"}
              </p>
              <p className="text-[0.7rem] text-neutral-600">
                {[personal?.linkedin_url, personal?.github_url, personal?.website_url]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </header>

            {PREVIEW_ORDER.map((sectionType) => {
              const data = content[sectionType];
              if (!data) return null;
              switch (sectionType) {
                case "SUMMARY": {
                  const summary = data as SectionContentMap["SUMMARY"];
                  if (!summary.text.trim()) return null;
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.SUMMARY}>
                      <p className="whitespace-pre-wrap">{summary.text}</p>
                    </PreviewSection>
                  );
                }
                case "EXPERIENCE":
                case "INTERNSHIPS": {
                  const experience = data as SectionContentMap["EXPERIENCE"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS[sectionType]}>
                      <div className="space-y-2.5">
                        {experience.entries.map((entry, index) => (
                          <div key={index}>
                            <div className="flex items-baseline justify-between gap-2">
                              <p>
                                <span className="font-semibold">{entry.title || "Title"}</span>
                                {entry.company ? `, ${entry.company}` : ""}
                                {entry.location ? (
                                  <span className="text-neutral-500"> — {entry.location}</span>
                                ) : null}
                              </p>
                              <DateRange start={entry.start_date} end={entry.end_date} />
                            </div>
                            {entry.bullets.filter((b) => b.trim()).length > 0 ? (
                              <ul className="mt-0.5 list-disc space-y-0.5 pl-5">
                                {entry.bullets
                                  .filter((bullet) => bullet.trim())
                                  .map((bullet, bulletIndex) => (
                                    <li key={bulletIndex}>{bullet}</li>
                                  ))}
                              </ul>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </PreviewSection>
                  );
                }
                case "PROJECTS": {
                  const projects = data as SectionContentMap["PROJECTS"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.PROJECTS}>
                      <div className="space-y-2.5">
                        {projects.entries.map((entry, index) => (
                          <div key={index}>
                            <p>
                              <span className="font-semibold">{entry.name || "Project"}</span>
                              {entry.technologies.length > 0 ? (
                                <span className="text-neutral-500">
                                  {" "}
                                  — {entry.technologies.join(", ")}
                                </span>
                              ) : null}
                            </p>
                            {entry.description ? <p>{entry.description}</p> : null}
                            {entry.bullets.filter((b) => b.trim()).length > 0 ? (
                              <ul className="mt-0.5 list-disc space-y-0.5 pl-5">
                                {entry.bullets
                                  .filter((bullet) => bullet.trim())
                                  .map((bullet, bulletIndex) => (
                                    <li key={bulletIndex}>{bullet}</li>
                                  ))}
                              </ul>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </PreviewSection>
                  );
                }
                case "EDUCATION": {
                  const education = data as SectionContentMap["EDUCATION"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.EDUCATION}>
                      <div className="space-y-2">
                        {education.entries.map((entry, index) => (
                          <div key={index} className="flex items-baseline justify-between gap-2">
                            <p>
                              <span className="font-semibold">{entry.degree || "Degree"}</span>
                              {entry.field_of_study ? `, ${entry.field_of_study}` : ""} —{" "}
                              {entry.institution || "Institution"}
                              {entry.gpa ? (
                                <span className="text-neutral-500"> · GPA {entry.gpa}</span>
                              ) : null}
                            </p>
                            <DateRange start={entry.start_date} end={entry.end_date} />
                          </div>
                        ))}
                      </div>
                    </PreviewSection>
                  );
                }
                case "SKILLS": {
                  const skills = data as SectionContentMap["SKILLS"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.SKILLS}>
                      <div className="space-y-0.5">
                        {skills.groups.map((group, index) => (
                          <p key={index}>
                            <span className="font-semibold">{group.name || "Group"}:</span>{" "}
                            {group.skills.join(", ")}
                          </p>
                        ))}
                      </div>
                    </PreviewSection>
                  );
                }
                case "CERTIFICATIONS": {
                  const certifications = data as SectionContentMap["CERTIFICATIONS"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.CERTIFICATIONS}>
                      <div className="space-y-1">
                        {certifications.entries.map((entry, index) => (
                          <div key={index} className="flex items-baseline justify-between gap-2">
                            <p>
                              <span className="font-semibold">{entry.name || "Certification"}</span>
                              {entry.issuer ? ` — ${entry.issuer}` : ""}
                            </p>
                            {entry.date ? (
                              <span className="text-[0.7rem] text-neutral-500">{entry.date}</span>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </PreviewSection>
                  );
                }
                case "ACHIEVEMENTS": {
                  const achievements = data as SectionContentMap["ACHIEVEMENTS"];
                  return (
                    <PreviewSection key={sectionType} title={SECTION_LABELS.ACHIEVEMENTS}>
                      <ul className="list-disc space-y-0.5 pl-5">
                        {achievements.entries.map((entry, index) => (
                          <li key={index}>
                            {entry.text}
                            {entry.date ? (
                              <span className="text-neutral-500"> ({entry.date})</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </PreviewSection>
                  );
                }
                default:
                  return null;
              }
            })}
          </article>
        </div>
      </div>
    </div>
  );
}
