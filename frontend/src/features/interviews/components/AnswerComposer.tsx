/**
 * Answer input: voice recording (default) with level meter, pause /
 * resume / stop, playback review, retry on device errors - or a typed
 * text answer. Exactly one modality is submitted per answer, matching
 * the backend contract. The browser never processes speech.
 */
import { Keyboard, Mic, Pause, Play, RotateCcw, Send, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { validateAnswerAudio } from "@/features/interviews/api";
import { useAudioRecorder } from "@/features/interviews/recorder";
import { formatClock } from "@/features/interviews/time";
import { cn } from "@/lib/utils";

function LevelMeter({ level, active }: { level: number; active: boolean }) {
  const bars = 12;
  const lit = Math.round(level * bars);
  return (
    <div
      role="img"
      aria-label={active ? `Microphone level ${Math.round(level * 100)} percent` : "Microphone idle"}
      className="flex h-6 items-end gap-0.5"
    >
      {Array.from({ length: bars }, (_, index) => (
        <span
          key={index}
          className={cn(
            "w-1.5 rounded-sm transition-colors",
            index < lit && active ? "bg-primary" : "bg-muted",
          )}
          style={{ height: `${((index + 1) / bars) * 100}%` }}
        />
      ))}
    </div>
  );
}

export function AnswerComposer({
  disabled,
  submitting,
  onSubmit,
}: {
  disabled: boolean;
  submitting: boolean;
  onSubmit: (input: { text?: string; audio?: Blob }) => void;
}) {
  const recorder = useAudioRecorder();
  const [mode, setMode] = useState<"voice" | "text">("voice");
  const [text, setText] = useState("");

  // Object URL lifecycle: created per blob; the effect revokes each URL
  // when the blob changes or the composer unmounts (no leaks).
  const audioUrl = useMemo(
    () => (recorder.state.blob ? URL.createObjectURL(recorder.state.blob) : null),
    [recorder.state.blob],
  );
  useEffect(() => {
    if (!audioUrl) return;
    return () => URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  const submitAudio = () => {
    const blob = recorder.state.blob;
    if (!blob) return;
    const verdict = validateAnswerAudio(blob);
    if (!verdict.ok) {
      // Keep the recording - tell the user why it can't be sent so they
      // can deliberately re-record; never silently discard their answer.
      toast.error(verdict.reason);
      return;
    }
    onSubmit({ audio: blob });
    recorder.reset();
  };

  const submitText = () => {
    if (text.trim().length === 0) return;
    onSubmit({ text: text.trim() });
    setText("");
  };

  return (
    <section aria-label="Your answer" className="space-y-3">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={mode === "voice" ? "default" : "outline"}
          onClick={() => setMode("voice")}
          aria-pressed={mode === "voice"}
        >
          <Mic aria-hidden /> Voice
        </Button>
        <Button
          type="button"
          size="sm"
          variant={mode === "text" ? "default" : "outline"}
          onClick={() => setMode("text")}
          aria-pressed={mode === "text"}
        >
          <Keyboard aria-hidden /> Type
        </Button>
      </div>

      {mode === "voice" ? (
        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex flex-wrap items-center gap-3">
            {recorder.state.phase === "idle" || recorder.state.phase === "error" ? (
              <Button
                onClick={() => void recorder.start()}
                disabled={disabled || submitting}
              >
                <Mic aria-hidden /> {recorder.state.phase === "error" ? "Retry recording" : "Start recording"}
              </Button>
            ) : null}
            {recorder.state.phase === "requesting" ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner /> Requesting microphone access…
              </p>
            ) : null}
            {recorder.state.phase === "recording" || recorder.state.phase === "paused" ? (
              <>
                {recorder.state.phase === "recording" ? (
                  <Button variant="outline" onClick={recorder.pause}>
                    <Pause aria-hidden /> Pause
                  </Button>
                ) : (
                  <Button variant="outline" onClick={recorder.resume}>
                    <Play aria-hidden /> Resume
                  </Button>
                )}
                <Button variant="destructive" onClick={recorder.stop}>
                  <Square aria-hidden /> Stop
                </Button>
                <span
                  className="text-sm tabular-nums text-muted-foreground"
                  role="timer"
                  aria-label="Recording duration"
                >
                  {formatClock(recorder.state.elapsedSeconds)}
                </span>
                <LevelMeter
                  level={recorder.state.level}
                  active={recorder.state.phase === "recording"}
                />
                {recorder.state.phase === "paused" ? (
                  <span className="text-xs text-muted-foreground">Recording paused</span>
                ) : null}
              </>
            ) : null}
          </div>

          {recorder.state.phase === "error" && recorder.state.error ? (
            <Alert variant="destructive">
              <AlertDescription>{recorder.state.error}</AlertDescription>
            </Alert>
          ) : null}

          {recorder.state.phase === "stopped" && recorder.state.blob ? (
            <div className="space-y-2">
              {audioUrl ? (
                <audio controls src={audioUrl} className="w-full" aria-label="Review your recorded answer" />
              ) : null}
              <div className="flex gap-2">
                <Button onClick={submitAudio} disabled={submitting}>
                  {submitting ? <Spinner className="text-primary-foreground" /> : <Send aria-hidden />}
                  Submit answer
                </Button>
                <Button variant="outline" onClick={recorder.reset} disabled={submitting}>
                  <RotateCcw aria-hidden /> Re-record
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-2">
          <Textarea
            rows={5}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Type your answer"
            aria-label="Typed answer"
            disabled={disabled || submitting}
          />
          <Button onClick={submitText} disabled={disabled || submitting || text.trim() === ""}>
            {submitting ? <Spinner className="text-primary-foreground" /> : <Send aria-hidden />}
            Submit answer
          </Button>
        </div>
      )}
    </section>
  );
}
