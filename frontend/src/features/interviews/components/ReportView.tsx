/** Read-only visualization of a backend interview report. Every score,
 *  category weight, readiness level, and speech metric is backend-
 *  computed; the frontend renders and never aggregates. */
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { InterviewReport } from "@/features/interviews/api";
import { READINESS_LABELS } from "@/features/interviews/api";

const CATEGORY_LABELS: Record<string, string> = {
  TECHNICAL_DEPTH: "Technical depth",
  COMMUNICATION: "Communication",
  RELEVANCE: "Relevance",
  PROBLEM_SOLVING: "Problem solving",
  SPECIFICITY: "Specificity",
  EVIDENCE: "Evidence",
  ANSWER_STRUCTURE: "Answer structure",
};

function StringListCard({ title, items }: { title: string; items: string[] | null | undefined }) {
  if (!items || items.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function ReportView({ report }: { report: InterviewReport }) {
  const payload = report.report_payload;
  const narrative = payload?.narrative ?? null;
  const speech = payload?.speech_metrics_summary;

  return (
    <div className="space-y-6 print:space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 p-6">
          <div>
            <p className="text-sm text-muted-foreground">Overall interview score</p>
            <p className="text-4xl font-semibold tabular-nums">
              {report.overall_score ?? "—"}
              <span className="text-lg font-normal text-muted-foreground">/100</span>
            </p>
          </div>
          <div className="space-y-1 text-sm text-muted-foreground">
            {report.readiness_level ? (
              <p>
                Readiness:{" "}
                <Badge>{READINESS_LABELS[report.readiness_level] ?? report.readiness_level}</Badge>
              </p>
            ) : null}
            <p>Scoring algorithm: {report.scoring_algorithm_version}</p>
            {speech ? <p>Answers with audio: {speech.answers_with_audio}</p> : null}
          </div>
        </CardContent>
      </Card>

      {narrative?.overview ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{narrative.overview}</p>
          </CardContent>
        </Card>
      ) : payload?.narrative_unavailable ? (
        <Alert>
          <AlertDescription>
            The AI narrative was unavailable for this report; the deterministic scores and
            evidence below are complete.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Category scores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {report.categories.map((category) => (
            <div key={category.category} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{CATEGORY_LABELS[category.category] ?? category.category}</span>
                <span className="tabular-nums text-muted-foreground">
                  {category.score ?? "n/a"}
                  {category.score !== null ? "/100" : ""} · weight{" "}
                  {Math.round(category.weight * 1000) / 10}%
                </span>
              </div>
              <Progress
                value={category.score ?? 0}
                label={`${CATEGORY_LABELS[category.category] ?? category.category} score`}
              />
              {category.evidence.length > 0 ? (
                <p className="text-xs text-muted-foreground">{category.evidence.join(" ")}</p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      {speech ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Speech performance (server-computed)</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Avg speaking speed</dt>
                <dd className="tabular-nums">
                  {speech.avg_words_per_minute != null
                    ? `${Math.round(speech.avg_words_per_minute)} wpm`
                    : "n/a"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Total long pauses</dt>
                <dd className="tabular-nums">{speech.total_long_pauses}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Avg filler words / answer</dt>
                <dd className="tabular-nums">{speech.avg_filler_word_count ?? "n/a"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Avg speech completeness</dt>
                <dd className="tabular-nums">
                  {speech.avg_speech_completeness != null
                    ? `${Math.round(speech.avg_speech_completeness * 100)}%`
                    : "n/a"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Answers with audio</dt>
                <dd className="tabular-nums">{speech.answers_with_audio}</dd>
              </div>
            </dl>
            {speech.answers_with_audio === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                No audio answers were submitted, so per-speech metrics are unavailable.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {payload && payload.timeline.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2">
              {payload.timeline.map((item) => (
                <li key={item.sequence} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="w-6 tabular-nums text-muted-foreground">{item.sequence}.</span>
                  <Badge variant="outline">{item.stage}</Badge>
                  <span className="text-muted-foreground">{item.question_type}</span>
                  {item.topic ? <span>· {item.topic}</span> : null}
                  <span className="text-xs text-muted-foreground">({item.difficulty})</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      ) : null}

      {payload && payload.topic_coverage.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Topic coverage</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {payload.topic_coverage.map((topic) => (
              <Badge key={topic} variant="secondary">
                {topic}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <StringListCard title="Key strengths" items={report.key_strengths} />
        <StringListCard title="Key weaknesses" items={report.key_weaknesses} />
        <StringListCard title="Technical observations" items={narrative?.technical_observations} />
        <StringListCard title="Behavioral observations" items={narrative?.behavioral_observations} />
      </div>

      {narrative && (narrative.strongest_answers.length > 0 || narrative.weakest_answers.length > 0) ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {narrative.strongest_answers.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Strongest answers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {narrative.strongest_answers.map((highlight, index) => (
                  <div key={index} className="space-y-0.5 border-l-2 pl-3 text-sm">
                    <p className="font-medium">{highlight.question}</p>
                    <p className="text-muted-foreground">{highlight.reason}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
          {narrative.weakest_answers.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Weakest answers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {narrative.weakest_answers.map((highlight, index) => (
                  <div key={index} className="space-y-0.5 border-l-2 pl-3 text-sm">
                    <p className="font-medium">{highlight.question}</p>
                    <p className="text-muted-foreground">{highlight.reason}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}

      {payload && payload.question_history.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Question history</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {payload.question_history.map((item) => (
              <div key={item.sequence} className="space-y-1 border-l-2 pl-3">
                <p className="text-sm font-medium">
                  {item.sequence}. {item.question}
                </p>
                {item.observation ? (
                  <p className="text-sm italic text-muted-foreground">{item.observation}</p>
                ) : null}
                {item.strengths && item.strengths.length > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Strengths: {item.strengths.join("; ")}
                  </p>
                ) : null}
                {item.weaknesses && item.weaknesses.length > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Weaknesses: {item.weaknesses.join("; ")}
                  </p>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <StringListCard
        title="Improvement roadmap"
        items={report.improvement_priorities ?? narrative?.improvement_roadmap}
      />

      {report.overall_score === null ? (
        <Alert>
          <AlertTitle>Scores unavailable</AlertTitle>
          <AlertDescription>
            Not enough evaluated answers were available to compute readiness scores.
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
