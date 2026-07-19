/**
 * The builder workspace for one project: section navigation (fixed
 * canonical order - section-level ordering is owned by the backend
 * template system, so reordering sections is intentionally not offered;
 * entries WITHIN sections reorder freely), the active section editor
 * with autosave, live preview, and the generation/history panel.
 */
import { ArrowLeft, Eye, FileDown, PencilLine } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GenerationPanel } from "@/features/builder/components/GenerationPanel";
import { ResumePreview } from "@/features/builder/components/ResumePreview";
import { SectionWorkspace } from "@/features/builder/components/SectionWorkspace";
import { useBuilderProject, useUpdateProject } from "@/features/builder/hooks";
import {
  SECTION_LABELS,
  SECTION_TYPES,
  type SectionContentMap,
  type SectionType,
} from "@/features/builder/schemas";
import { cn } from "@/lib/utils";
import { PATHS } from "@/routes/paths";

type Panel = "edit" | "preview" | "generate";
type DraftMap = { [K in SectionType]?: SectionContentMap[K] };

export default function BuilderProjectPage() {
  const { projectId = "" } = useParams();
  const project = useBuilderProject(projectId);
  const updateProject = useUpdateProject(projectId);
  const [activeSection, setActiveSection] = useState<SectionType>("PERSONAL_INFO");
  const [panel, setPanel] = useState<Panel>("edit");
  const [drafts, setDrafts] = useState<DraftMap>({});

  const savedByType = useMemo(() => {
    const map: DraftMap = {};
    for (const section of project.data?.sections ?? []) {
      const sectionType = section.section_type as SectionType;
      if ((SECTION_TYPES as readonly string[]).includes(sectionType)) {
        map[sectionType] = section.content as never;
      }
    }
    return map;
  }, [project.data]);

  // Preview prefers unsaved drafts (live updates) over server state.
  const previewContent = useMemo(() => ({ ...savedByType, ...drafts }), [savedByType, drafts]);

  if (project.isLoading) {
    return (
      <div className="space-y-4" aria-busy>
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (project.isError || !project.data) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>Could not load this resume project.</span>
          <Button variant="outline" size="sm" onClick={() => void project.refetch()}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const detail = project.data;

  return (
    <>
      <PageHeader
        title={detail.title}
        description="Autosaves as you type. Section order follows the Caviar template system."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={detail.status === "FINALIZED" ? "default" : "secondary"}>
              {detail.status}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              disabled={updateProject.isPending}
              onClick={() =>
                updateProject.mutate({
                  status: detail.status === "FINALIZED" ? "DRAFT" : "FINALIZED",
                })
              }
            >
              {detail.status === "FINALIZED" ? "Reopen as draft" : "Mark finalized"}
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link to={PATHS.resumeBuilder}>
                <ArrowLeft aria-hidden /> All projects
              </Link>
            </Button>
          </div>
        }
      />

      <div
        role="tablist"
        aria-label="Builder view"
        className="mb-4 inline-flex rounded-md border p-0.5"
      >
        {(
          [
            { id: "edit", label: "Edit", icon: PencilLine },
            { id: "preview", label: "Preview", icon: Eye },
            { id: "generate", label: "Generate", icon: FileDown },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={panel === id}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              panel === id ? "bg-accent text-accent-foreground" : "text-muted-foreground",
            )}
            onClick={() => setPanel(id)}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {panel === "edit" ? (
        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <nav aria-label="Resume sections">
            <ul className="space-y-1">
              {SECTION_TYPES.map((sectionType) => {
                const saved = savedByType[sectionType] !== undefined;
                return (
                  <li key={sectionType}>
                    <button
                      className={cn(
                        "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        activeSection === sectionType
                          ? "bg-accent font-medium text-accent-foreground"
                          : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                      )}
                      aria-current={activeSection === sectionType ? "true" : undefined}
                      onClick={() => setActiveSection(sectionType)}
                    >
                      {SECTION_LABELS[sectionType]}
                      {saved ? (
                        <span
                          className="size-1.5 rounded-full bg-primary"
                          aria-label="Section has saved content"
                        />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="mt-3 px-3 text-xs text-muted-foreground">
              Section order is defined by the selected template - only entries within a section can
              be reordered.
            </p>
          </nav>

          <SectionWorkspace
            key={`${projectId}-${activeSection}`}
            projectId={projectId}
            sectionType={activeSection}
            initialContent={drafts[activeSection] ?? savedByType[activeSection] ?? null}
            exists={savedByType[activeSection] !== undefined}
            onDraftChange={(sectionType, content) =>
              setDrafts((current) => ({ ...current, [sectionType]: content }))
            }
          />
        </div>
      ) : null}

      {panel === "preview" ? <ResumePreview content={previewContent} /> : null}

      {panel === "generate" ? (
        <GenerationPanel projectId={projectId} projectTitle={detail.title} />
      ) : null}
    </>
  );
}
