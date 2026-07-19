/**
 * Section editors for all nine backend section types. Each editor is a
 * controlled component over the typed content shape; every change flows
 * to the parent's autosave pipeline (validate -> debounce -> PUT).
 * Custom sections are not part of the backend contract (nine fixed
 * types with strict schemas), so no fabricated "custom section" UI is
 * offered.
 */
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  AssistStatus,
  BulletsAssistResultView,
  SummaryAssistResultView,
} from "@/features/builder/components/AssistPanel";
import {
  BulletListField,
  DateField,
  EntryList,
  TagListField,
  TextAreaField,
  TextField,
} from "@/features/builder/components/fields";
import { useAssist } from "@/features/builder/hooks";
import type {
  AchievementsContent,
  CertificationsContent,
  EducationContent,
  ExperienceContent,
  PersonalInfoContent,
  ProjectsContent,
  SectionType,
  SkillsContent,
  SummaryContent,
} from "@/features/builder/schemas";

export function PersonalInfoEditor({
  content,
  onChange,
}: {
  content: PersonalInfoContent;
  onChange: (content: PersonalInfoContent) => void;
}) {
  const set = <K extends keyof PersonalInfoContent>(key: K, value: string) =>
    onChange({ ...content, [key]: value === "" && key !== "full_name" ? null : value });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <TextField label="Full name" value={content.full_name} onChange={(v) => set("full_name", v)} />
      <TextField label="Email" type="email" value={content.email ?? ""} onChange={(v) => set("email", v)} />
      <TextField label="Phone" value={content.phone ?? ""} onChange={(v) => set("phone", v)} />
      <TextField label="Location" value={content.location ?? ""} onChange={(v) => set("location", v)} />
      <TextField label="LinkedIn URL" value={content.linkedin_url ?? ""} onChange={(v) => set("linkedin_url", v)} />
      <TextField label="GitHub URL" value={content.github_url ?? ""} onChange={(v) => set("github_url", v)} />
      <TextField label="Website URL" value={content.website_url ?? ""} onChange={(v) => set("website_url", v)} />
    </div>
  );
}

export function SummaryEditor({
  projectId,
  content,
  onChange,
}: {
  projectId: string;
  content: SummaryContent;
  onChange: (content: SummaryContent) => void;
}) {
  const assist = useAssist(projectId);
  const [lastRequest, setLastRequest] = useState<"GENERATE_SUMMARY" | "IMPROVE_SUMMARY" | null>(null);

  const run = (assistType: "GENERATE_SUMMARY" | "IMPROVE_SUMMARY") => {
    setLastRequest(assistType);
    assist.mutate({ assist_type: assistType });
  };

  const result = assist.data && "improved_summary" in assist.data ? assist.data : null;

  return (
    <div className="space-y-4">
      <TextAreaField
        label="Professional summary"
        value={content.text}
        onChange={(text) => onChange({ text })}
        rows={6}
        maxLength={2000}
        placeholder="A concise, factual summary of your profile"
      />
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={assist.isPending}
          onClick={() => run("GENERATE_SUMMARY")}
        >
          Generate from my sections
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={assist.isPending || content.text.trim().length === 0}
          onClick={() => run("IMPROVE_SUMMARY")}
        >
          Improve current summary
        </Button>
      </div>
      <AssistStatus
        pending={assist.isPending}
        error={assist.isError ? assist.error.message : null}
        onRetry={() => lastRequest && run(lastRequest)}
      />
      {result ? (
        <SummaryAssistResultView result={result} onApply={(text) => onChange({ text })} />
      ) : null}
    </div>
  );
}

function ExperienceLikeEditor({
  projectId,
  sectionType,
  content,
  onChange,
  entryLabel,
}: {
  projectId: string;
  sectionType: SectionType;
  content: ExperienceContent;
  onChange: (content: ExperienceContent) => void;
  entryLabel: string;
}) {
  const assist = useAssist(projectId);
  const [assistIndex, setAssistIndex] = useState<number | null>(null);

  const runAssist = (entryIndex: number) => {
    setAssistIndex(entryIndex);
    assist.mutate({ assist_type: "IMPROVE_BULLETS", section_type: sectionType, entry_index: entryIndex });
  };

  const bulletsResult = assist.data && "bullets" in assist.data ? assist.data : null;

  return (
    <div className="space-y-4">
      <EntryList
        entries={content.entries}
        onChange={(entries) => onChange({ entries })}
        entryLabel={entryLabel}
        makeEmpty={() => ({
          company: "",
          title: "",
          location: null,
          start_date: null,
          end_date: null,
          bullets: [],
        })}
        renderEntry={(entry, update, index) => (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Company" value={entry.company} onChange={(v) => update({ ...entry, company: v })} />
              <TextField label="Title" value={entry.title} onChange={(v) => update({ ...entry, title: v })} />
              <TextField
                label="Location"
                value={entry.location ?? ""}
                onChange={(v) => update({ ...entry, location: v || null })}
              />
              <div className="grid grid-cols-2 gap-3">
                <DateField
                  label="Start"
                  value={entry.start_date ?? ""}
                  onChange={(v) => update({ ...entry, start_date: v || null })}
                />
                <DateField
                  label="End"
                  value={entry.end_date ?? ""}
                  onChange={(v) => update({ ...entry, end_date: v || null })}
                />
              </div>
            </div>
            <BulletListField
              label="Bullets"
              bullets={entry.bullets}
              onChange={(bullets) => update({ ...entry, bullets })}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={assist.isPending || entry.bullets.filter((b) => b.trim()).length === 0}
              onClick={() => runAssist(index)}
            >
              Improve bullets with AI
            </Button>
            {assistIndex === index ? (
              <>
                <AssistStatus
                  pending={assist.isPending}
                  error={assist.isError ? assist.error.message : null}
                  onRetry={() => runAssist(index)}
                />
                {bulletsResult ? (
                  <BulletsAssistResultView
                    result={bulletsResult}
                    onApply={(bulletIndex, improved) =>
                      update({
                        ...entry,
                        bullets: entry.bullets.map((bullet, i) =>
                          i === bulletIndex ? improved : bullet,
                        ),
                      })
                    }
                  />
                ) : null}
              </>
            ) : null}
          </div>
        )}
      />
    </div>
  );
}

export function ExperienceEditor(props: {
  projectId: string;
  content: ExperienceContent;
  onChange: (content: ExperienceContent) => void;
}) {
  return <ExperienceLikeEditor {...props} sectionType="EXPERIENCE" entryLabel="Role" />;
}

export function InternshipsEditor(props: {
  projectId: string;
  content: ExperienceContent;
  onChange: (content: ExperienceContent) => void;
}) {
  return <ExperienceLikeEditor {...props} sectionType="INTERNSHIPS" entryLabel="Internship" />;
}

export function ProjectsEditor({
  projectId,
  content,
  onChange,
}: {
  projectId: string;
  content: ProjectsContent;
  onChange: (content: ProjectsContent) => void;
}) {
  const assist = useAssist(projectId);
  const [assistIndex, setAssistIndex] = useState<number | null>(null);
  const runAssist = (entryIndex: number) => {
    setAssistIndex(entryIndex);
    assist.mutate({ assist_type: "IMPROVE_BULLETS", section_type: "PROJECTS", entry_index: entryIndex });
  };
  const bulletsResult = assist.data && "bullets" in assist.data ? assist.data : null;

  return (
    <EntryList
      entries={content.entries}
      onChange={(entries) => onChange({ entries })}
      entryLabel="Project"
      makeEmpty={() => ({ name: "", description: null, technologies: [], url: null, bullets: [] })}
      renderEntry={(entry, update, index) => (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Project name" value={entry.name} onChange={(v) => update({ ...entry, name: v })} />
            <TextField
              label="URL"
              value={entry.url ?? ""}
              onChange={(v) => update({ ...entry, url: v || null })}
            />
          </div>
          <TextAreaField
            label="Description"
            value={entry.description ?? ""}
            onChange={(v) => update({ ...entry, description: v || null })}
            rows={3}
            maxLength={1000}
          />
          <TagListField
            label="Technologies"
            values={entry.technologies}
            onChange={(technologies) => update({ ...entry, technologies })}
            maxItems={30}
          />
          <BulletListField
            label="Bullets"
            bullets={entry.bullets}
            onChange={(bullets) => update({ ...entry, bullets })}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={assist.isPending || entry.bullets.filter((b) => b.trim()).length === 0}
            onClick={() => runAssist(index)}
          >
            Improve bullets with AI
          </Button>
          {assistIndex === index ? (
            <>
              <AssistStatus
                pending={assist.isPending}
                error={assist.isError ? assist.error.message : null}
                onRetry={() => runAssist(index)}
              />
              {bulletsResult ? (
                <BulletsAssistResultView
                  result={bulletsResult}
                  onApply={(bulletIndex, improved) =>
                    update({
                      ...entry,
                      bullets: entry.bullets.map((bullet, i) =>
                        i === bulletIndex ? improved : bullet,
                      ),
                    })
                  }
                />
              ) : null}
            </>
          ) : null}
        </div>
      )}
    />
  );
}

export function EducationEditor({
  content,
  onChange,
}: {
  content: EducationContent;
  onChange: (content: EducationContent) => void;
}) {
  return (
    <EntryList
      entries={content.entries}
      onChange={(entries) => onChange({ entries })}
      entryLabel="Education"
      maxItems={10}
      makeEmpty={() => ({
        institution: "",
        degree: "",
        field_of_study: null,
        location: null,
        start_date: null,
        end_date: null,
        gpa: null,
        highlights: [],
      })}
      renderEntry={(entry, update) => (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Institution" value={entry.institution} onChange={(v) => update({ ...entry, institution: v })} />
            <TextField label="Degree" value={entry.degree} onChange={(v) => update({ ...entry, degree: v })} />
            <TextField
              label="Field of study"
              value={entry.field_of_study ?? ""}
              onChange={(v) => update({ ...entry, field_of_study: v || null })}
            />
            <TextField label="GPA" value={entry.gpa ?? ""} onChange={(v) => update({ ...entry, gpa: v || null })} />
            <DateField label="Start" value={entry.start_date ?? ""} onChange={(v) => update({ ...entry, start_date: v || null })} />
            <DateField label="End" value={entry.end_date ?? ""} onChange={(v) => update({ ...entry, end_date: v || null })} />
          </div>
          <BulletListField
            label="Highlights"
            bullets={entry.highlights}
            onChange={(highlights) => update({ ...entry, highlights })}
            maxItems={10}
          />
        </div>
      )}
    />
  );
}

export function SkillsEditor({
  content,
  onChange,
}: {
  content: SkillsContent;
  onChange: (content: SkillsContent) => void;
}) {
  return (
    <EntryList
      entries={content.groups}
      onChange={(groups) => onChange({ groups })}
      entryLabel="Skill group"
      maxItems={15}
      makeEmpty={() => ({ name: "", skills: [] })}
      renderEntry={(group, update) => (
        <div className="space-y-3">
          <TextField
            label="Group name"
            value={group.name}
            onChange={(v) => update({ ...group, name: v })}
            placeholder="e.g. Languages, Frameworks"
          />
          <TagListField
            label="Skills"
            values={group.skills}
            onChange={(skills) => update({ ...group, skills })}
            maxItems={40}
          />
        </div>
      )}
    />
  );
}

export function CertificationsEditor({
  content,
  onChange,
}: {
  content: CertificationsContent;
  onChange: (content: CertificationsContent) => void;
}) {
  return (
    <EntryList
      entries={content.entries}
      onChange={(entries) => onChange({ entries })}
      entryLabel="Certification"
      makeEmpty={() => ({ name: "", issuer: null, date: null, credential_url: null })}
      renderEntry={(entry, update) => (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label="Name" value={entry.name} onChange={(v) => update({ ...entry, name: v })} />
          <TextField label="Issuer" value={entry.issuer ?? ""} onChange={(v) => update({ ...entry, issuer: v || null })} />
          <DateField label="Date" value={entry.date ?? ""} onChange={(v) => update({ ...entry, date: v || null })} />
          <TextField
            label="Credential URL"
            value={entry.credential_url ?? ""}
            onChange={(v) => update({ ...entry, credential_url: v || null })}
          />
        </div>
      )}
    />
  );
}

export function AchievementsEditor({
  content,
  onChange,
}: {
  content: AchievementsContent;
  onChange: (content: AchievementsContent) => void;
}) {
  return (
    <EntryList
      entries={content.entries}
      onChange={(entries) => onChange({ entries })}
      entryLabel="Achievement"
      makeEmpty={() => ({ text: "", date: null })}
      renderEntry={(entry, update) => (
        <div className="space-y-3">
          <TextAreaField
            label="Achievement"
            value={entry.text}
            onChange={(v) => update({ ...entry, text: v })}
            rows={2}
            maxLength={500}
          />
          <DateField label="Date" value={entry.date ?? ""} onChange={(v) => update({ ...entry, date: v || null })} />
        </div>
      )}
    />
  );
}
