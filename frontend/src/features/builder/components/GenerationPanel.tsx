/**
 * PDF generation + history panel. LaTeX compilation happens ONLY on the
 * backend; this panel selects an approved template, triggers a
 * generation, shows the lifecycle result (status, warnings like page
 * overflow or unsupported glyphs, sanitized failure reasons), downloads
 * via short-lived signed URLs, and lists previous generations as
 * version history. Restore and compare have no backend endpoints, so
 * those actions are shown disabled rather than faked.
 */
import { Download, FileText, RotateCcw } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { generationFilename, type Generation } from "@/features/builder/api";
import {
  useCreateGeneration,
  useDownloadGeneration,
  useGenerations,
  useTemplates,
} from "@/features/builder/hooks";
import { formatDateTime, formatFileSize } from "@/utils/format";

function warningText(warning: Record<string, unknown>): string {
  if (typeof warning.message === "string") return warning.message;
  if (typeof warning.code === "string") return warning.code;
  return JSON.stringify(warning);
}

function GenerationRow({
  generation,
  projectTitle,
}: {
  generation: Generation;
  projectTitle: string;
}) {
  const download = useDownloadGeneration();
  const completed = generation.status === "COMPLETED";
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border p-3">
      <FileText className="size-4 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-sm">
          {generation.template_id} v{generation.template_version}
          {generation.page_count !== null ? ` · ${generation.page_count} page(s)` : ""}
          {generation.file_size_bytes !== null
            ? ` · ${formatFileSize(generation.file_size_bytes)}`
            : ""}
        </p>
        <p className="text-xs text-muted-foreground">
          {generation.created_at ? formatDateTime(generation.created_at) : ""}
        </p>
      </div>
      <Badge variant={completed ? "default" : generation.status === "FAILED" ? "destructive" : "secondary"}>
        {generation.status}
      </Badge>
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="outline"
          disabled={!completed || download.isPending}
          onClick={() =>
            download.mutate({
              generationId: generation.id,
              filename: generationFilename(projectTitle),
            })
          }
        >
          <Download aria-hidden /> Download
        </Button>
        <Button size="sm" variant="ghost" disabled title="Restore is not supported by the backend yet">
          Restore
        </Button>
        <Button size="sm" variant="ghost" disabled title="Compare is not supported by the backend yet">
          Compare
        </Button>
      </div>
    </div>
  );
}

export function GenerationPanel({
  projectId,
  projectTitle,
}: {
  projectId: string;
  projectTitle: string;
}) {
  const templates = useTemplates();
  const generations = useGenerations(projectId);
  const createGeneration = useCreateGeneration(projectId);
  const download = useDownloadGeneration();
  const [chosenTemplateId, setChosenTemplateId] = useState<string | null>(null);
  // Derived default: first approved template unless the user chose one.
  const templateId = chosenTemplateId ?? templates.data?.[0]?.template_id ?? "";

  const latest = createGeneration.data ?? generations.data?.[0];
  const selectedTemplate = templates.data?.find((t) => t.template_id === templateId);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Generate PDF</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="template-select">Template</Label>
            {templates.isLoading ? (
              <Skeleton className="h-9 w-full" />
            ) : (
              <Select value={templateId} onValueChange={setChosenTemplateId}>
                <SelectTrigger id="template-select" aria-label="Resume template">
                  <SelectValue placeholder="Choose a template" />
                </SelectTrigger>
                <SelectContent>
                  {(templates.data ?? []).map((template) => (
                    <SelectItem key={template.template_id} value={template.template_id}>
                      {template.name} (v{template.template_version})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {selectedTemplate ? (
              <p className="text-xs text-muted-foreground">
                {selectedTemplate.description} · ATS: {selectedTemplate.ats_classification} · max{" "}
                {selectedTemplate.max_pages} page(s)
              </p>
            ) : null}
          </div>

          <Button
            disabled={!templateId || createGeneration.isPending}
            onClick={() => createGeneration.mutate(templateId)}
          >
            {createGeneration.isPending ? (
              <>
                <Spinner className="text-primary-foreground" /> Compiling on the server…
              </>
            ) : (
              "Generate PDF"
            )}
          </Button>

          {createGeneration.isError ? (
            <Alert variant="destructive">
              <AlertDescription className="flex items-center justify-between gap-3">
                <span>{createGeneration.error.message}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => templateId && createGeneration.mutate(templateId)}
                >
                  <RotateCcw aria-hidden /> Retry
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {latest && latest.status === "FAILED" ? (
            <Alert variant="destructive">
              <AlertTitle>Generation failed ({latest.failure_category ?? "unknown"})</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{latest.failure_reason ?? "The document could not be generated."}</p>
                <p className="text-xs">
                  Your resume content is safe - fix the issue above (or pick another template) and
                  retry.
                </p>
              </AlertDescription>
            </Alert>
          ) : null}

          {latest && latest.status === "COMPLETED" ? (
            <Alert>
              <AlertTitle>PDF ready</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>
                  {latest.page_count} page(s)
                  {latest.file_size_bytes !== null
                    ? ` · ${formatFileSize(latest.file_size_bytes)}`
                    : ""}
                  {latest.compilation_duration_ms !== null
                    ? ` · compiled in ${latest.compilation_duration_ms} ms`
                    : ""}
                </p>
                {latest.warnings.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-5 text-xs">
                    {latest.warnings.map((warning, index) => (
                      <li key={index}>{warningText(warning)}</li>
                    ))}
                  </ul>
                ) : null}
                <Button
                  size="sm"
                  disabled={download.isPending}
                  onClick={() =>
                    download.mutate({
                      generationId: latest.id,
                      filename: generationFilename(projectTitle),
                    })
                  }
                >
                  <Download aria-hidden /> Download PDF
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">History</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {generations.isLoading ? (
            <div className="space-y-2" aria-busy>
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : (generations.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No PDFs generated yet.</p>
          ) : (
            (generations.data ?? []).map((generation) => (
              <GenerationRow
                key={generation.id}
                generation={generation}
                projectTitle={projectTitle}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
