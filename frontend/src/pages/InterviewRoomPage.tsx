/**
 * The AI Interview Room. Orchestration is backend-owned: the room
 * renders the current backend question/stage, submits one answer at a
 * time, plays optional backend TTS audio, and shows the interviewer
 * observation after each cycle. Timers are display-only; the question
 * budget is the authoritative pacing mechanism. Transcript display: the
 * backend transcribes audio server-side but exposes no per-answer
 * transcript endpoint, so the room shows the submitted text verbatim
 * for typed answers and the backend speech summary for audio answers -
 * nothing is invented client-side.
 */
import { ArrowLeft, PauseCircle, PlayCircle, Volume2, Wifi, WifiOff, XCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import type { AnswerCycle } from "@/features/interviews/api";
import { AnswerComposer } from "@/features/interviews/components/AnswerComposer";
import { StageProgress } from "@/features/interviews/components/StageProgress";
import {
  useInterview,
  usePauseInterview,
  useResumeInterview,
  useCancelInterview,
  useStartInterview,
  useSubmitAnswer,
} from "@/features/interviews/hooks";
import { formatClock } from "@/features/interviews/time";
import { getApiErrorMessage } from "@/services/api/errors";
import { PATHS } from "@/routes/paths";

interface ExchangeEntry {
  kind: "question" | "answer" | "observation";
  text: string;
  meta?: string;
}

function useOnlineStatus(): boolean {
  const [online, setOnline] = useState<boolean>(() => navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

function ElapsedTimer({ running, durationMinutes }: { running: boolean; durationMinutes: number }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => setSeconds((current) => current + 1), 1000);
    return () => clearInterval(interval);
  }, [running]);
  return (
    <span className="text-sm tabular-nums text-muted-foreground" role="timer" aria-label="Elapsed time this visit">
      {formatClock(seconds)} / ~{durationMinutes} min
    </span>
  );
}

export default function InterviewRoomPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const interview = useInterview(sessionId);
  const startInterview = useStartInterview();
  const pauseInterview = usePauseInterview();
  const resumeInterview = useResumeInterview();
  const cancelInterview = useCancelInterview();
  const submitAnswer = useSubmitAnswer(sessionId);
  const online = useOnlineStatus();

  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [exchange, setExchange] = useState<ExchangeEntry[]>([]);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [lastCycle, setLastCycle] = useState<AnswerCycle | null>(null);
  const lastSubmissionRef = useRef<{ text?: string; audio?: Blob } | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const questionRef = useRef<HTMLDivElement | null>(null);

  const session = interview.data;
  const question = lastCycle?.next_question ?? session?.current_question ?? null;

  const audioSrc = useMemo(
    () =>
      lastCycle?.question_audio_base64
        ? `data:audio/wav;base64,${lastCycle.question_audio_base64}`
        : null,
    [lastCycle],
  );
  useEffect(() => {
    if (audioSrc && audioRef.current) {
      void audioRef.current.play().catch(() => undefined); // autoplay may be blocked; controls remain
    }
  }, [audioSrc]);
  useEffect(() => {
    questionRef.current?.focus(); // move focus to each new question for screen readers
  }, [question?.id]);

  const handleSubmit = (input: { text?: string; audio?: Blob }) => {
    lastSubmissionRef.current = input;
    setExchange((current) => [
      ...current,
      input.text !== undefined
        ? { kind: "answer", text: input.text, meta: "Typed answer" }
        : { kind: "answer", text: "Voice answer submitted for transcription.", meta: "Audio answer" },
    ]);
    submitAnswer.mutate(
      { ...input, includeAudio: voiceEnabled },
      {
        onSuccess: (cycle) => {
          setLastCycle(cycle);
          setExchange((current) => [
            ...current,
            { kind: "observation", text: cycle.interviewer_observation },
            ...(cycle.next_question
              ? [
                  {
                    kind: "question" as const,
                    text: cycle.next_question.question_text,
                    meta: `${cycle.next_question.stage} · ${cycle.next_question.question_type}`,
                  },
                ]
              : []),
          ]);
          if (cycle.interview_completed) {
            void navigate(`/interview/${sessionId}/report`);
          }
        },
      },
    );
  };

  if (interview.isLoading) {
    return (
      <div className="space-y-4" aria-busy>
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (interview.isError || !session) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>Could not load this interview.</span>
          <Button variant="outline" size="sm" onClick={() => void interview.refetch()}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const running = session.status === "RUNNING";

  return (
    <>
      <PageHeader
        title={session.target_role_snapshot ?? "AI Interview"}
        description={`${session.interview_type} · ${session.difficulty} · AI interviewer (not a human)`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1">
              {online ? <Wifi className="size-3" aria-hidden /> : <WifiOff className="size-3" aria-hidden />}
              {online ? "Connected" : "Offline"}
            </Badge>
            <ElapsedTimer running={running} durationMinutes={session.duration_minutes} />
            <Button asChild variant="ghost" size="sm">
              <Link to={PATHS.interview}>
                <ArrowLeft aria-hidden /> Dashboard
              </Link>
            </Button>
          </div>
        }
      />

      {!online ? (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            You are offline. Answers cannot be submitted until the connection returns; your
            interview state is safe on the server.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="mb-4">
        <StageProgress
          currentStage={lastCycle?.stage ?? session.current_stage}
          questionsUsed={lastCycle?.questions_used ?? session.question_budget_used}
          questionBudget={session.question_budget}
        />
      </div>

      {session.status === "PENDING" || session.status === "READY" ? (
        <Card>
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-muted-foreground">
              When you start, the AI interviewer generates its first question from your resume
              and target role.
            </p>
            <Button
              onClick={() => startInterview.mutate(sessionId)}
              disabled={startInterview.isPending}
            >
              {startInterview.isPending ? (
                <>
                  <Spinner className="text-primary-foreground" /> Preparing your interviewer…
                </>
              ) : (
                <>
                  <PlayCircle aria-hidden /> Start interview
                </>
              )}
            </Button>
            {startInterview.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{getApiErrorMessage(startInterview.error)}</AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {session.status === "PAUSED" ? (
        <Card>
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-muted-foreground">
              The interview is paused. Your progress is saved on the server.
            </p>
            <Button
              onClick={() => resumeInterview.mutate(sessionId)}
              disabled={resumeInterview.isPending}
            >
              <PlayCircle aria-hidden /> Resume interview
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {["COMPLETED", "FAILED", "CANCELLED"].includes(session.status) ? (
        <Alert>
          <AlertTitle>This interview is {session.status.toLowerCase()}.</AlertTitle>
          <AlertDescription>
            {session.status === "COMPLETED" ? (
              <Link className="underline underline-offset-4" to={`/interview/${sessionId}/report`}>
                View the report
              </Link>
            ) : (
              (session.failure_reason ?? "No further answers can be submitted.")
            )}
          </AlertDescription>
        </Alert>
      ) : null}

      {running ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">AI Interviewer</CardTitle>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-pressed={voiceEnabled}
                    onClick={() => setVoiceEnabled((current) => !current)}
                  >
                    <Volume2 aria-hidden /> Voice {voiceEnabled ? "on" : "off"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pauseInterview.isPending || submitAnswer.isPending}
                    onClick={() => pauseInterview.mutate(sessionId)}
                  >
                    <PauseCircle aria-hidden /> Pause
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => setConfirmEnd(true)}
                  >
                    <XCircle aria-hidden /> End
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {question ? (
                  <div
                    ref={questionRef}
                    tabIndex={-1}
                    aria-live="polite"
                    className="rounded-md bg-accent/50 p-4 outline-none"
                  >
                    <p className="text-xs text-muted-foreground">
                      Question {question.sequence_number} · {question.question_type} ·{" "}
                      {question.difficulty}
                    </p>
                    <p className="mt-1 text-base">{question.question_text}</p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Waiting for the next question…</p>
                )}
                {audioSrc ? (
                  <audio
                    ref={audioRef}
                    controls
                    src={audioSrc}
                    className="w-full"
                    aria-label="Interviewer voice for the current question"
                  />
                ) : null}
                {lastCycle?.tts_warning ? (
                  <p className="text-xs text-muted-foreground">{lastCycle.tts_warning}</p>
                ) : null}
              </CardContent>
            </Card>

            {submitAnswer.isPending ? (
              <Alert>
                <AlertDescription className="flex items-center gap-2">
                  <Spinner /> Evaluating your answer - transcription and evaluation run on the
                  server and can take up to a minute.
                </AlertDescription>
              </Alert>
            ) : null}

            {submitAnswer.isError ? (
              <Alert variant="destructive">
                <AlertDescription className="flex items-center justify-between gap-3">
                  <span>{getApiErrorMessage(submitAnswer.error)}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const last = lastSubmissionRef.current;
                      if (last) {
                        submitAnswer.mutate({ ...last, includeAudio: voiceEnabled });
                      }
                    }}
                  >
                    Retry
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}

            <AnswerComposer
              disabled={!running || !online || Boolean(lastCycle?.interview_completed)}
              submitting={submitAnswer.isPending}
              onSubmit={handleSubmit}
            />
          </div>

          <aside aria-label="Interview log" className="space-y-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">This session</CardTitle>
              </CardHeader>
              <CardContent className="max-h-[28rem] space-y-3 overflow-y-auto text-sm">
                {exchange.length === 0 ? (
                  <p className="text-muted-foreground">
                    Your answers and the interviewer's observations appear here.
                  </p>
                ) : (
                  exchange.map((entry, index) => (
                    <div key={index} className="space-y-0.5">
                      <p className="text-xs font-medium text-muted-foreground">
                        {entry.kind === "question"
                          ? "Interviewer"
                          : entry.kind === "answer"
                            ? (entry.meta ?? "You")
                            : "Interviewer observation"}
                      </p>
                      <p className={entry.kind === "observation" ? "italic" : undefined}>
                        {entry.text}
                      </p>
                    </div>
                  ))
                )}
                {lastCycle?.speech_summary ? (
                  <div className="rounded-md border p-2 text-xs text-muted-foreground">
                    Last answer speech metrics (server-computed):{" "}
                    {lastCycle.speech_summary.words_per_minute != null
                      ? `${Math.round(lastCycle.speech_summary.words_per_minute)} wpm · `
                      : ""}
                    {lastCycle.speech_summary.long_pause_count ?? 0} long pauses ·{" "}
                    {lastCycle.speech_summary.filler_word_count ?? 0} filler words
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </aside>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmEnd}
        onOpenChange={setConfirmEnd}
        title="End this interview?"
        description="The session will be cancelled and cannot be resumed. No report is generated for cancelled interviews."
        confirmLabel="End interview"
        destructive
        pending={cancelInterview.isPending}
        onConfirm={() =>
          cancelInterview.mutate(sessionId, {
            onSuccess: () => {
              setConfirmEnd(false);
              void navigate(PATHS.interview);
            },
          })
        }
      />
    </>
  );
}
