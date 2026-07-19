/** Read-only visualization of a backend resume analysis. Every number
 *  and judgement shown here comes from the backend; the frontend never
 *  computes or adjusts scores. */
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { AnalysisDetail } from "@/features/resumes/api";

function asText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function StringList({ title, items, tone = "default" }: {
  title: string;
  items: string[] | null | undefined;
  tone?: "default" | "destructive";
}) {
  if (!items || items.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          {items.map((item, index) => (
            <li key={index} className={tone === "destructive" ? "text-destructive" : undefined}>
              {item}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  CONTENT_QUALITY: "Content Quality",
  EXPERIENCE_IMPACT: "Experience Impact",
  SKILLS_RELEVANCE: "Skills Relevance",
  PROJECT_QUALITY: "Project Quality",
  RESUME_STRUCTURE: "Resume Structure",
  ATS_COMPATIBILITY: "ATS Compatibility",
  EVIDENCE_QUANTIFICATION: "Evidence & Quantification",
};

export function AnalysisReport({ analysis }: { analysis: AnalysisDetail }) {
  const scored = analysis.categories.filter((category) => category.adjusted_score !== null);
  const atsCategory = analysis.categories.find((c) => c.category === "ATS_COMPATIBILITY");

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 p-6">
          <div>
            <p className="text-sm text-muted-foreground">Overall score</p>
            <p className="text-4xl font-semibold tabular-nums">
              {analysis.overall_score ?? "—"}
              <span className="text-lg font-normal text-muted-foreground">/100</span>
            </p>
          </div>
          <div className="space-y-1 text-sm text-muted-foreground">
            {analysis.target_role_snapshot ? (
              <p>
                Target role: <span className="text-foreground">{analysis.target_role_snapshot}</span>
              </p>
            ) : (
              <p>General analysis (no target role)</p>
            )}
            <p>Scoring algorithm: {analysis.scoring_algorithm_version}</p>
            {atsCategory?.adjusted_score !== null && atsCategory !== undefined ? (
              <p>
                ATS readiness:{" "}
                <span className="text-foreground">{atsCategory.adjusted_score}/100</span>
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Category scores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {scored.map((category) => (
            <div key={category.category} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{CATEGORY_LABELS[category.category] ?? category.category}</span>
                <span className="tabular-nums text-muted-foreground">
                  {category.adjusted_score}/100 · weight {Math.round(category.weight * 100)}%
                </span>
              </div>
              <Progress
                value={category.adjusted_score ?? 0}
                label={`${CATEGORY_LABELS[category.category] ?? category.category} score`}
              />
              {category.penalties.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Noted: {category.penalties.join("; ")}
                </p>
              ) : null}
            </div>
          ))}
          {analysis.categories.some((category) => category.adjusted_score === null) ? (
            <p className="text-xs text-muted-foreground">
              Categories not applicable to this resume are excluded and weights renormalized by
              the backend.
            </p>
          ) : null}
        </CardContent>
      </Card>

      {analysis.critical_issues && analysis.critical_issues.length > 0 ? (
        <Alert variant="destructive">
          <AlertTitle>Critical issues</AlertTitle>
          <AlertDescription>
            <ul className="list-disc space-y-1 pl-5">
              {analysis.critical_issues.map((issue, index) => (
                <li key={index}>{issue}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <StringList title="Strengths" items={analysis.strengths} />
        <StringList title="Weaknesses" items={analysis.weaknesses} />
        <StringList title="Priority improvements" items={analysis.priority_improvements} />
        <StringList title="ATS observations" items={analysis.ats_observations} />
      </div>

      {analysis.missing_sections && analysis.missing_sections.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Missing sections</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {analysis.missing_sections.map((section) => (
              <Badge key={section} variant="secondary">
                {section}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {analysis.role_relevance ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Role relevance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {"matched_skills" in analysis.role_relevance &&
            Array.isArray(analysis.role_relevance.matched_skills) ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Matched skills:</span>
                {analysis.role_relevance.matched_skills.map((skill, index) => (
                  <Badge key={index}>{asText(skill)}</Badge>
                ))}
              </div>
            ) : null}
            {"missing_keywords" in analysis.role_relevance &&
            Array.isArray(analysis.role_relevance.missing_keywords) ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Missing keywords:</span>
                {analysis.role_relevance.missing_keywords.map((keyword, index) => (
                  <Badge key={index} variant="outline">
                    {asText(keyword)}
                  </Badge>
                ))}
              </div>
            ) : null}
            {"summary" in analysis.role_relevance &&
            typeof analysis.role_relevance.summary === "string" ? (
              <p>{analysis.role_relevance.summary}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {analysis.section_feedback && analysis.section_feedback.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Section feedback</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {analysis.section_feedback.map((feedback, index) => (
              <div key={index} className="space-y-1 border-l-2 pl-3">
                <p className="text-sm font-medium">
                  {asText(feedback.section_type ?? feedback.section ?? `Section ${index + 1}`)}
                </p>
                {typeof feedback.feedback === "string" ? (
                  <p className="text-sm text-muted-foreground">{feedback.feedback}</p>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {analysis.bullet_improvements && analysis.bullet_improvements.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bullet improvements</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {analysis.bullet_improvements.map((item, index) => (
              <div key={index} className="space-y-1.5 rounded-md border p-3 text-sm">
                {typeof item.original === "string" ? (
                  <p className="text-muted-foreground line-through decoration-muted-foreground/50">
                    {item.original}
                  </p>
                ) : null}
                {typeof item.improved === "string" ? <p>{item.improved}</p> : null}
                {typeof item.reason === "string" ? (
                  <p className="text-xs text-muted-foreground">Why: {item.reason}</p>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {scored.some((category) => category.evidence.length > 0) ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evidence</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {scored
              .filter((category) => category.evidence.length > 0)
              .map((category) => (
                <div key={category.category} className="space-y-1.5">
                  <p className="text-sm font-medium">
                    {CATEGORY_LABELS[category.category] ?? category.category}
                  </p>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                    {category.evidence.map((item, index) => (
                      <li key={index}>
                        {typeof item.quote === "string"
                          ? `“${item.quote}”`
                          : asText(item.observation ?? item)}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
