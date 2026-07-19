import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import type { BuilderProject } from "@/features/builder/api";
import { useBuilderProjects, useCreateProject, useDeleteProject } from "@/features/builder/hooks";
import { formatDateTime } from "@/utils/format";

export default function ResumeBuilderPage() {
  const projects = useBuilderProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [deleting, setDeleting] = useState<BuilderProject | null>(null);

  const create = () => {
    if (title.trim().length === 0) return;
    createProject.mutate(title.trim(), {
      onSuccess: () => {
        setCreateOpen(false);
        setTitle("");
      },
    });
  };

  return (
    <>
      <PageHeader
        title="Resume Builder"
        description="Build structured, ATS-safe resumes with AI assistance."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden /> New resume
          </Button>
        }
      />

      {projects.isLoading ? (
        <div className="space-y-3" aria-busy>
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : projects.isError ? (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>Could not load your resume projects.</span>
            <Button variant="outline" size="sm" onClick={() => void projects.refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : (projects.data ?? []).length === 0 ? (
        <EmptyState
          title="No resume projects yet"
          description="Create a project to start building a structured resume."
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus aria-hidden /> New resume
            </Button>
          }
        />
      ) : (
        <ul className="space-y-3">
          {(projects.data ?? []).map((project) => (
            <li key={project.id}>
              <Card>
                <CardContent className="flex flex-wrap items-center gap-4 p-4">
                  <div className="min-w-0 flex-1 space-y-1">
                    <Link
                      to={`/resume-builder/${project.id}`}
                      className="truncate font-medium underline-offset-4 hover:underline"
                    >
                      {project.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      Modified {formatDateTime(project.updated_at)}
                    </p>
                  </div>
                  <Badge variant={project.status === "FINALIZED" ? "default" : "secondary"}>
                    {project.status}
                  </Badge>
                  <div className="flex items-center gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/resume-builder/${project.id}`}>Open</Link>
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Delete ${project.title}`}
                      onClick={() => setDeleting(project)}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New resume project</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="project-title">Project title</Label>
            <Input
              id="project-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Backend Engineer 2026"
              onKeyDown={(event) => {
                if (event.key === "Enter") create();
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={create} disabled={createProject.isPending || title.trim() === ""}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this project?"
        description={
          deleting ? `"${deleting.title}" and its generated PDFs will be removed.` : undefined
        }
        confirmLabel="Delete"
        destructive
        pending={deleteProject.isPending}
        onConfirm={() => {
          if (deleting) {
            deleteProject.mutate(deleting.id, { onSuccess: () => setDeleting(null) });
          }
        }}
      />
    </>
  );
}
