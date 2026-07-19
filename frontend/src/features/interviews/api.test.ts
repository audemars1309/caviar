/** API-integration tests: request shapes match the Phase 8 backend
 *  contract exactly (multipart with exactly one modality; include_audio
 *  query flag), plus the client-side audio pre-validation mirror. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/api/client", () => ({
  apiClient: { post: vi.fn() },
}));
vi.mock("@/services/api/helpers", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

import {
  ANSWER_AUDIO_MAX_BYTES,
  interviewsApi,
  validateAnswerAudio,
} from "@/features/interviews/api";
import { apiClient } from "@/services/api/client";
import { apiGet, apiPost } from "@/services/api/helpers";

describe("interviewsApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.post).mockResolvedValue({ data: { interview_completed: false } });
  });

  it("creates interviews with the backend InterviewCreateRequest shape", async () => {
    vi.mocked(apiPost).mockResolvedValue({ id: "s1" });
    await interviewsApi.create({
      resume_id: "r1",
      job_context_id: null,
      interview_type: "TECHNICAL",
      difficulty: "HARD",
      duration_minutes: 30,
    });
    expect(apiPost).toHaveBeenCalledWith("/interviews", {
      resume_id: "r1",
      job_context_id: null,
      interview_type: "TECHNICAL",
      difficulty: "HARD",
      duration_minutes: 30,
    });
  });

  it("submits text answers as form data with text_answer only", async () => {
    await interviewsApi.submitAnswer("s1", { text: "My answer" });
    const [url, body, config] = vi.mocked(apiClient.post).mock.calls[0]!;
    expect(url).toBe("/interviews/s1/answers");
    expect(body).toBeInstanceOf(FormData);
    const formData = body as FormData;
    expect(formData.get("text_answer")).toBe("My answer");
    expect(formData.get("audio")).toBeNull();
    expect(config).toMatchObject({ params: { include_audio: false } });
  });

  it("submits audio answers as an audio file with include_audio for TTS", async () => {
    const blob = new Blob(["bytes"], { type: "audio/webm" });
    await interviewsApi.submitAnswer("s1", { audio: blob }, { includeAudio: true });
    const [, body, config] = vi.mocked(apiClient.post).mock.calls[0]!;
    const formData = body as FormData;
    expect(formData.get("audio")).toBeInstanceOf(File);
    expect(formData.get("text_answer")).toBeNull();
    expect(config).toMatchObject({ params: { include_audio: true } });
  });

  it("fetches the report from the session-scoped endpoint", async () => {
    vi.mocked(apiGet).mockResolvedValue({ id: "rep1" });
    await interviewsApi.report("s1");
    expect(apiGet).toHaveBeenCalledWith("/interviews/s1/report");
  });
});

describe("validateAnswerAudio", () => {
  it("rejects empty recordings", () => {
    expect(validateAnswerAudio(new Blob([])).ok).toBe(false);
  });

  it("rejects recordings over the backend 25 MB limit", () => {
    const blob = new Blob(["x"]);
    Object.defineProperty(blob, "size", { value: ANSWER_AUDIO_MAX_BYTES + 1 });
    expect(validateAnswerAudio(blob).ok).toBe(false);
  });

  it("accepts a normal recording", () => {
    expect(validateAnswerAudio(new Blob(["audio-bytes"])).ok).toBe(true);
  });
});
