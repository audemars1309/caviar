/**
 * Browser microphone recording for interview answers. The browser ONLY
 * captures audio (MediaRecorder -> webm/opus or ogg/opus blob) and
 * visualizes input level; all speech processing (transcription, speech
 * metrics) happens on the backend. Handles permission denial, missing
 * devices, mid-recording device failures, and retry.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderPhase =
  | "idle"
  | "requesting"
  | "recording"
  | "paused"
  | "stopped"
  | "error";

export interface RecorderState {
  phase: RecorderPhase;
  /** 0..1 smoothed input level for the meter. */
  level: number;
  elapsedSeconds: number;
  error: string | null;
  blob: Blob | null;
}

const IDLE: RecorderState = { phase: "idle", level: 0, elapsedSeconds: 0, error: null, blob: null };

function pickMimeType(): string | undefined {
  // Both containers are accepted by the backend audio validator.
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
  if (typeof MediaRecorder === "undefined") return undefined;
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function describeMediaError(error: unknown): string {
  if (error instanceof DOMException) {
    switch (error.name) {
      case "NotAllowedError":
        return "Microphone access was denied. Allow microphone access in your browser and retry.";
      case "NotFoundError":
        return "No microphone was found. Connect a microphone and retry.";
      case "NotReadableError":
        return "The microphone is in use by another application. Close it and retry.";
      case "SecurityError":
        return "Microphone access is blocked in this context (HTTPS is required).";
      default:
        return `Microphone error: ${error.name}. Check your device and retry.`;
    }
  }
  return "Could not access the microphone. Check your device and retry.";
}

export function useAudioRecorder() {
  const [state, setState] = useState<RecorderState>(IDLE);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (tickRef.current !== null) clearInterval(tickRef.current);
    tickRef.current = null;
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setState({ ...IDLE, phase: "requesting" });
    chunksRef.current = [];
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new DOMException("mediaDevices unavailable", "SecurityError");
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        cleanup();
        setState((current) => ({
          ...current,
          phase: "error",
          error: "Recording failed mid-way (device error). Retry when ready.",
        }));
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        cleanup();
        setState((current) => ({ ...current, phase: "stopped", level: 0, blob }));
      };

      // Input level meter (visualization only - no speech processing).
      const AudioContextCtor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (AudioContextCtor) {
        const audioContext = new AudioContextCtor();
        audioContextRef.current = audioContext;
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        const samples = new Uint8Array(analyser.frequencyBinCount);
        const loop = () => {
          analyser.getByteTimeDomainData(samples);
          let sumSquares = 0;
          for (const sample of samples) {
            const centered = (sample - 128) / 128;
            sumSquares += centered * centered;
          }
          const rms = Math.sqrt(sumSquares / samples.length);
          // Quantize to the meter's 12 visual steps and skip no-op state
          // updates so the ~60fps analyser loop doesn't re-render the UI.
          const level = Math.round(Math.min(1, rms * 3) * 12) / 12;
          setState((current) =>
            current.phase === "recording" && current.level !== level
              ? { ...current, level }
              : current,
          );
          rafRef.current = requestAnimationFrame(loop);
        };
        rafRef.current = requestAnimationFrame(loop);
      }

      recorder.start(1000); // periodic chunks so data survives device loss
      tickRef.current = setInterval(() => {
        setState((current) =>
          current.phase === "recording"
            ? { ...current, elapsedSeconds: current.elapsedSeconds + 1 }
            : current,
        );
      }, 1000);
      setState({ phase: "recording", level: 0, elapsedSeconds: 0, error: null, blob: null });
    } catch (error) {
      cleanup();
      setState({ ...IDLE, phase: "error", error: describeMediaError(error) });
    }
  }, [cleanup]);

  const pause = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") {
      recorder.pause();
      setState((current) => ({ ...current, phase: "paused" }));
    }
  }, []);

  const resume = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder?.state === "paused") {
      recorder.resume();
      setState((current) => ({ ...current, phase: "recording" }));
    }
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setState(IDLE);
  }, [cleanup]);

  return { state, start, pause, resume, stop, reset };
}
