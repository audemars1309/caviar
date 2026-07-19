/** Readiness trend chart: plots backend-computed report scores over
 *  time as an accessible inline SVG. No client-side score math beyond
 *  pixel mapping. */
import type { InterviewReport } from "@/features/interviews/api";
import { READINESS_LABELS } from "@/features/interviews/api";
import { formatDate } from "@/utils/format";

export function ReadinessTrend({ points }: { points: InterviewReport[] }) {
  if (points.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Complete an interview to start tracking readiness over time.
      </p>
    );
  }

  const width = 560;
  const height = 160;
  const padding = { left: 34, right: 12, top: 12, bottom: 24 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const x = (index: number) =>
    padding.left + (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
  const y = (score: number) => padding.top + innerHeight - (score / 100) * innerHeight;
  const path = points
    .map((report, index) => `${index === 0 ? "M" : "L"}${x(index)},${y(report.overall_score ?? 0)}`)
    .join(" ");

  const latest = points[points.length - 1];

  return (
    <figure className="space-y-2">
      <figcaption className="sr-only">
        Interview readiness scores over time, most recent score{" "}
        {latest?.overall_score ?? "unknown"} out of 100.
      </figcaption>
      <svg
        role="img"
        aria-label={`Readiness trend across ${points.length} completed interview${points.length > 1 ? "s" : ""}`}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full max-w-xl"
      >
        {[0, 50, 100].map((tick) => (
          <g key={tick}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y(tick)}
              y2={y(tick)}
              className="stroke-border"
              strokeWidth={1}
            />
            <text
              x={padding.left - 6}
              y={y(tick) + 3}
              textAnchor="end"
              className="fill-muted-foreground text-[9px]"
            >
              {tick}
            </text>
          </g>
        ))}
        {points.length > 1 ? (
          <path d={path} fill="none" className="stroke-primary" strokeWidth={2} />
        ) : null}
        {points.map((report, index) => (
          <circle
            key={report.id}
            cx={x(index)}
            cy={y(report.overall_score ?? 0)}
            r={3.5}
            className="fill-primary"
          >
            <title>
              {formatDate(report.created_at)}: {report.overall_score}/100
              {report.readiness_level
                ? ` (${READINESS_LABELS[report.readiness_level] ?? report.readiness_level})`
                : ""}
            </title>
          </circle>
        ))}
      </svg>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {points.map((report) => (
          <li key={report.id}>
            {formatDate(report.created_at)}: <span className="tabular-nums">{report.overall_score}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
