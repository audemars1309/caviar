/**
 * AI Content Assist results panel. The user is always the write path:
 * results are suggestions the user explicitly applies. Missing-fact
 * questions and unsupported numbers from the backend fabrication guard
 * are surfaced prominently - the frontend never invents content.
 */
import { RotateCcw, Sparkles } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { BulletsAssistResult, SummaryAssistResult } from "@/features/builder/api";

export function AssistStatus({
  pending,
  error,
  onRetry,
}: {
  pending: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (pending) {
    return (
      <div className="flex items-center gap-2 rounded-md border p-3 text-sm text-muted-foreground">
        <Spinner /> Asking Caviar AI…
      </div>
    );
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCcw aria-hidden /> Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
  return null;
}

function FactIntegrityNotes({
  missingFactQuestions,
  unsupportedNumbers,
}: {
  missingFactQuestions: string[];
  unsupportedNumbers: string[];
}) {
  if (missingFactQuestions.length === 0 && unsupportedNumbers.length === 0) return null;
  return (
    <Alert>
      <AlertTitle>Grounding check</AlertTitle>
      <AlertDescription className="space-y-2">
        {unsupportedNumbers.length > 0 ? (
          <p>
            These numbers were not found in your original text — confirm them before using:{" "}
            {unsupportedNumbers.join(", ")}
          </p>
        ) : null}
        {missingFactQuestions.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5">
            {missingFactQuestions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ul>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

export function SummaryAssistResultView({
  result,
  onApply,
}: {
  result: SummaryAssistResult;
  onApply: (summary: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="whitespace-pre-wrap text-sm">{result.improved_summary}</p>
        <Button size="sm" onClick={() => onApply(result.improved_summary)}>
          <Sparkles aria-hidden /> Use this
        </Button>
      </div>
      {result.changes_explained.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {result.changes_explained.map((change, index) => (
            <li key={index}>{change}</li>
          ))}
        </ul>
      ) : null}
      {result.action_verb_suggestions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Action verbs:</span>
          {result.action_verb_suggestions.map((verb) => (
            <Badge key={verb} variant="outline">
              {verb}
            </Badge>
          ))}
        </div>
      ) : null}
      <FactIntegrityNotes
        missingFactQuestions={result.missing_fact_questions}
        unsupportedNumbers={result.unsupported_numbers}
      />
    </div>
  );
}

export function BulletsAssistResultView({
  result,
  onApply,
}: {
  result: BulletsAssistResult;
  onApply: (index: number, improved: string) => void;
}) {
  return (
    <div className="space-y-3">
      {result.bullets.map((bullet, index) => (
        <div key={index} className="space-y-2 rounded-md border p-3">
          <p className="text-xs text-muted-foreground line-through decoration-muted-foreground/50">
            {bullet.original}
          </p>
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm">{bullet.improved}</p>
            <Button size="sm" onClick={() => onApply(index, bullet.improved)}>
              <Sparkles aria-hidden /> Use
            </Button>
          </div>
          {bullet.changes_explained.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {bullet.changes_explained.map((change, changeIndex) => (
                <li key={changeIndex}>{change}</li>
              ))}
            </ul>
          ) : null}
          <FactIntegrityNotes
            missingFactQuestions={bullet.missing_fact_questions}
            unsupportedNumbers={bullet.unsupported_numbers}
          />
        </div>
      ))}
      {result.action_verb_suggestions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Action verbs:</span>
          {result.action_verb_suggestions.map((verb) => (
            <Badge key={verb} variant="outline">
              {verb}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}
