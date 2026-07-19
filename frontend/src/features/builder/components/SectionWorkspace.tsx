/**
 * One section's editing workspace: local draft state seeded from the
 * server section, editor by type, autosave status line, and section
 * removal. Empty (never-saved) sections start from a minimal valid
 * draft; autosave only fires once the draft passes the mirrored schema.
 */
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  AchievementsEditor,
  CertificationsEditor,
  EducationEditor,
  ExperienceEditor,
  InternshipsEditor,
  PersonalInfoEditor,
  ProjectsEditor,
  SkillsEditor,
  SummaryEditor,
} from "@/features/builder/components/SectionEditors";
import { useDeleteSection, useSectionAutosave } from "@/features/builder/hooks";
import {
  SECTION_LABELS,
  type SectionContentMap,
  type SectionType,
} from "@/features/builder/schemas";
import { cn } from "@/lib/utils";

export const EMPTY_CONTENT: { [K in SectionType]: SectionContentMap[K] } = {
  PERSONAL_INFO: { full_name: "" },
  SUMMARY: { text: "" },
  EDUCATION: {
    entries: [
      {
        institution: "",
        degree: "",
        field_of_study: null,
        location: null,
        start_date: null,
        end_date: null,
        gpa: null,
        highlights: [],
      },
    ],
  },
  SKILLS: { groups: [{ name: "", skills: [] }] },
  EXPERIENCE: {
    entries: [
      { company: "", title: "", location: null, start_date: null, end_date: null, bullets: [] },
    ],
  },
  INTERNSHIPS: {
    entries: [
      { company: "", title: "", location: null, start_date: null, end_date: null, bullets: [] },
    ],
  },
  PROJECTS: {
    entries: [{ name: "", description: null, technologies: [], url: null, bullets: [] }],
  },
  CERTIFICATIONS: {
    entries: [{ name: "", issuer: null, date: null, credential_url: null }],
  },
  ACHIEVEMENTS: { entries: [{ text: "", date: null }] },
};

function AutosaveLine({
  status,
  message,
}: {
  status: "idle" | "editing" | "saving" | "saved" | "invalid" | "error";
  message: string | null;
}) {
  const text =
    status === "saving"
      ? "Saving…"
      : status === "saved"
        ? "All changes saved"
        : status === "editing"
          ? "Editing…"
          : status === "invalid"
            ? (message ?? "Section incomplete - not saved yet")
            : status === "error"
              ? (message ?? "Autosave failed")
              : "";
  if (!text) return null;
  return (
    <p
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-1.5 text-xs",
        status === "error"
          ? "text-destructive"
          : status === "invalid"
            ? "text-muted-foreground"
            : "text-muted-foreground",
      )}
    >
      {status === "saving" ? <Spinner className="size-3" /> : null}
      {text}
    </p>
  );
}

export function SectionWorkspace<T extends SectionType>({
  projectId,
  sectionType,
  initialContent,
  exists,
  onDraftChange,
}: {
  projectId: string;
  sectionType: T;
  initialContent: SectionContentMap[T] | null;
  exists: boolean;
  onDraftChange: (sectionType: T, content: SectionContentMap[T]) => void;
}) {
  const [draft, setDraft] = useState<SectionContentMap[T]>(
    initialContent ?? EMPTY_CONTENT[sectionType],
  );
  const [confirmRemove, setConfirmRemove] = useState(false);
  const autosave = useSectionAutosave(projectId, sectionType);
  const deleteSection = useDeleteSection(projectId);

  const handleChange = (content: SectionContentMap[T]) => {
    setDraft(content);
    onDraftChange(sectionType, content);
    autosave.onChange(content);
  };

  const editor = (() => {
    switch (sectionType) {
      case "PERSONAL_INFO":
        return (
          <PersonalInfoEditor
            content={draft as SectionContentMap["PERSONAL_INFO"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "SUMMARY":
        return (
          <SummaryEditor
            projectId={projectId}
            content={draft as SectionContentMap["SUMMARY"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "EXPERIENCE":
        return (
          <ExperienceEditor
            projectId={projectId}
            content={draft as SectionContentMap["EXPERIENCE"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "INTERNSHIPS":
        return (
          <InternshipsEditor
            projectId={projectId}
            content={draft as SectionContentMap["INTERNSHIPS"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "PROJECTS":
        return (
          <ProjectsEditor
            projectId={projectId}
            content={draft as SectionContentMap["PROJECTS"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "EDUCATION":
        return (
          <EducationEditor
            content={draft as SectionContentMap["EDUCATION"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "SKILLS":
        return (
          <SkillsEditor
            content={draft as SectionContentMap["SKILLS"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "CERTIFICATIONS":
        return (
          <CertificationsEditor
            content={draft as SectionContentMap["CERTIFICATIONS"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      case "ACHIEVEMENTS":
        return (
          <AchievementsEditor
            content={draft as SectionContentMap["ACHIEVEMENTS"]}
            onChange={(content) => handleChange(content as SectionContentMap[T])}
          />
        );
      default:
        return null;
    }
  })();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{SECTION_LABELS[sectionType]}</CardTitle>
        <div className="flex items-center gap-3">
          <AutosaveLine status={autosave.state.status} message={autosave.state.message} />
          {exists ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Remove ${SECTION_LABELS[sectionType]} section`}
              onClick={() => setConfirmRemove(true)}
            >
              <Trash2 aria-hidden />
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent onBlur={() => autosave.flush()}>{editor}</CardContent>

      <ConfirmDialog
        open={confirmRemove}
        onOpenChange={setConfirmRemove}
        title={`Remove the ${SECTION_LABELS[sectionType]} section?`}
        description="The section's saved content will be deleted from this project."
        confirmLabel="Remove"
        destructive
        pending={deleteSection.isPending}
        onConfirm={() =>
          deleteSection.mutate(sectionType, { onSuccess: () => setConfirmRemove(false) })
        }
      />
    </Card>
  );
}
