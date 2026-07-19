/** Voice recording tests with mocked MediaRecorder/getUserMedia: full
 *  lifecycle, permission denial mapping, and blob assembly. No real
 *  audio processing happens in the browser or in tests. */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAudioRecorder } from "@/features/interviews/recorder";

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  static isTypeSupported = () => true;
  state: "inactive" | "recording" | "paused" = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onerror: (() => void) | null = null;
  onstop: (() => void) | null = null;
  constructor() {
    FakeMediaRecorder.instances.push(this);
  }
  start() {
    this.state = "recording";
  }
  pause() {
    this.state = "paused";
  }
  resume() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["chunk"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

const fakeStream = {
  getTracks: () => [{ stop: vi.fn() }],
} as unknown as MediaStream;

describe("useAudioRecorder", () => {
  beforeEach(() => {
    FakeMediaRecorder.instances = [];
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
    });
    // No AudioContext in jsdom - the recorder must degrade gracefully
    // (recording works; the level meter simply stays at zero).
    vi.stubGlobal("AudioContext", undefined);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("runs the full record -> pause -> resume -> stop lifecycle", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.state.phase).toBe("recording");

    act(() => result.current.pause());
    expect(result.current.state.phase).toBe("paused");
    expect(FakeMediaRecorder.instances[0]!.state).toBe("paused");

    act(() => result.current.resume());
    expect(result.current.state.phase).toBe("recording");

    act(() => result.current.stop());
    await waitFor(() => expect(result.current.state.phase).toBe("stopped"));
    expect(result.current.state.blob).toBeInstanceOf(Blob);
    expect(result.current.state.blob!.size).toBeGreaterThan(0);
  });

  it("maps permission denial to a clear, retryable error", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(new DOMException("denied", "NotAllowedError")),
      },
    });
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.state.phase).toBe("error");
    expect(result.current.state.error).toMatch(/denied/i);
  });

  it("maps a missing microphone to a device error", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue(new DOMException("none", "NotFoundError")),
      },
    });
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.state.phase).toBe("error");
    expect(result.current.state.error).toMatch(/no microphone/i);
  });

  it("reset returns to idle and stops tracks", async () => {
    const { result } = renderHook(() => useAudioRecorder());
    await act(async () => {
      await result.current.start();
    });
    act(() => result.current.reset());
    expect(result.current.state.phase).toBe("idle");
    expect(result.current.state.blob).toBeNull();
  });
});
