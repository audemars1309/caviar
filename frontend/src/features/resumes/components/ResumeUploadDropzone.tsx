import { FileUp, RotateCcw, X } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { UploadState } from "@/features/resumes/hooks";
import { cn } from "@/lib/utils";

export function ResumeUploadDropzone({
  state,
  onFile,
  onCancel,
  onRetry,
}: {
  state: UploadState;
  onFile: (file: File) => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <section aria-label="Upload resume" className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a PDF resume: drag and drop or press Enter to browse"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          dragActive ? "border-ring bg-accent/50" : "border-border hover:bg-accent/30",
        )}
      >
        <FileUp className="size-6 text-muted-foreground" aria-hidden />
        <p className="text-sm font-medium">Drag a PDF here, or click to browse</p>
        <p className="text-xs text-muted-foreground">PDF only, up to 10 MB.</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          aria-hidden
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {state.phase === "uploading" ? (
        <div className="flex items-center gap-3 rounded-md border p-3">
          <div className="min-w-0 flex-1 space-y-1.5">
            <p className="truncate text-sm">{state.fileName}</p>
            <Progress value={state.progress} label="Upload progress" />
          </div>
          <span className="text-xs tabular-nums text-muted-foreground">{state.progress}%</span>
          <Button variant="ghost" size="icon" aria-label="Cancel upload" onClick={onCancel}>
            <X aria-hidden />
          </Button>
        </div>
      ) : null}

      {state.phase === "cancelled" ? (
        <Alert>
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>Upload of “{state.fileName}” cancelled.</span>
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RotateCcw aria-hidden /> Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {state.phase === "error" ? (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>{state.error}</span>
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RotateCcw aria-hidden /> Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
