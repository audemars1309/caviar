/** Report + transcript-adjacent rendering: everything shown comes from
 *  the backend report payload verbatim; the frontend computes nothing. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InterviewReport } from "@/features/interviews/api";
import { ReportView } from "@/features/interviews/components/ReportView";

const report: InterviewReport = {
  id: "rep1",
  session_id: "s1",
  overall_score: 71,
  readiness_level: "READY",
  scoring_algorithm_version: "interview-readiness-1.0.0",
  key_strengths: ["FastAPI depth"],
  key_weaknesses: ["Vague ownership claims"],
  improvement_priorities: ["Structure project answers around personal contribution."],
  narrative_model: "gemini-test",
  report_payload: {
    schema_version: "interview-report-1.0.0",
    evaluation_schema_version: "answer-evaluation-1.0.0",
    timeline: [
      { sequence: 1, stage: "INTRODUCTION", question_type: "INTRODUCTORY", topic: null, difficulty: "EASY" },
      { sequence: 2, stage: "PROJECT_DEEP_DIVE", question_type: "PROJECT", topic: "Caviar", difficulty: "MEDIUM" },
    ],
    topic_coverage: ["Caviar", "PostgreSQL"],
    question_history: [
      {
        sequence: 2,
        question: "Walk me through the Caviar architecture.",
        observation: "Explained the stack but not the personal contribution.",
        strengths: ["Clear stack overview"],
        weaknesses: ["Ownership unclear"],
      },
    ],
    speech_metrics_summary: {
      answers_with_audio: 3,
      avg_words_per_minute: 128.4,
      avg_filler_word_count: 2.3,
      total_long_pauses: 4,
      avg_speech_completeness: 0.91,
    },
    narrative: {
      overview: "A steady interview with solid technical grounding.",
      technical_observations: ["Strong FastAPI specifics."],
      behavioral_observations: ["Answers lacked STAR structure."],
      strongest_answers: [{ question: "Deployment question", reason: "Concrete and specific." }],
      weakest_answers: [{ question: "Conflict question", reason: "Generic response." }],
      improvement_roadmap: ["Practice STAR structure because answers drifted."],
    },
    narrative_unavailable: false,
  },
  created_at: "2026-07-01T10:00:00Z",
  categories: [
    { category: "TECHNICAL_DEPTH", score: 74, weight: 0.2, evidence: ["Aggregated from 6 evaluated answers."] },
    { category: "COMMUNICATION", score: 65, weight: 0.2, evidence: [] },
  ],
};

describe("ReportView", () => {
  it("renders backend scores, readiness, and categories verbatim", () => {
    render(<ReportView report={report} />);
    expect(screen.getByText("71")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText(/interview-readiness-1.0.0/)).toBeInTheDocument();
    expect(screen.getByText("Technical depth")).toBeInTheDocument();
    expect(screen.getByText(/74\/100/)).toBeInTheDocument();
  });

  it("renders speech metrics from the backend summary only", () => {
    render(<ReportView report={report} />);
    expect(screen.getByText("128 wpm")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    // total_long_pauses appears exactly as provided
    expect(screen.getByText(/total long pauses/i)).toBeInTheDocument();
  });

  it("renders the timeline, topic coverage, and question history", () => {
    render(<ReportView report={report} />);
    expect(screen.getByText("PROJECT_DEEP_DIVE")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText(/Walk me through the Caviar architecture/)).toBeInTheDocument();
    expect(screen.getByText(/not the personal contribution/)).toBeInTheDocument();
  });

  it("handles a report whose narrative was unavailable", () => {
    const withoutNarrative: InterviewReport = {
      ...report,
      report_payload: { ...report.report_payload!, narrative: null, narrative_unavailable: true },
      improvement_priorities: null,
    };
    render(<ReportView report={withoutNarrative} />);
    expect(screen.getByText(/narrative was unavailable/i)).toBeInTheDocument();
    expect(screen.getByText("71")).toBeInTheDocument(); // deterministic scores still shown
  });
});
