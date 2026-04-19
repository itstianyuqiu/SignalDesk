"use client";

import { useCallback, useRef, useState } from "react";

export type VoiceCaptureStatus = "idle" | "recording" | "error";

export type VoiceRecordingResult = {
  blob: Blob;
  mimeType: string;
  durationSec: number;
  /**
   * Max absolute waveform sample in [-1, 1] while recording.
   * `-1` if metering was unavailable (skip client-side silence check).
   */
  peakLevel: number;
};

function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
  ];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "audio/webm";
}

function getAudioContextClass(): (typeof AudioContext) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

/**
 * Push-to-talk style capture: start → stop returns a Blob for server-side STT.
 * Extensible toward streaming: swap MediaRecorder for AudioWorklet + WebSocket later.
 */
export function useVoiceCapture() {
  const [status, setStatus] = useState<VoiceCaptureStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const startedAtRef = useRef<number>(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const meterRafRef = useRef<number | null>(null);
  const maxPeakRef = useRef<number>(0);
  const peakMeterActiveRef = useRef<boolean>(false);

  const stopMeter = useCallback(() => {
    if (meterRafRef.current !== null) {
      cancelAnimationFrame(meterRafRef.current);
      meterRafRef.current = null;
    }
    try {
      sourceNodeRef.current?.disconnect();
    } catch {
      /* ignore */
    }
    sourceNodeRef.current = null;
    analyserRef.current = null;
    const ctx = audioContextRef.current;
    audioContextRef.current = null;
    void ctx?.close().catch(() => undefined);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Microphone is not available in this browser.");
      setStatus("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      const mimeType = pickMimeType();
      const rec = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      rec.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onerror = () => {
        setError("Recording failed.");
        setStatus("error");
      };
      const AC = getAudioContextClass();
      maxPeakRef.current = 0;
      peakMeterActiveRef.current = false;
      if (AC) {
        peakMeterActiveRef.current = true;
        const actx = new AC();
        audioContextRef.current = actx;
        const source = actx.createMediaStreamSource(stream);
        sourceNodeRef.current = source;
        const analyser = actx.createAnalyser();
        analyser.fftSize = 4096;
        analyserRef.current = analyser;
        source.connect(analyser);
        const sample = () => {
          const a = analyserRef.current;
          if (!a) return;
          const buf = new Float32Array(a.fftSize);
          a.getFloatTimeDomainData(buf);
          let m = 0;
          for (let i = 0; i < buf.length; i++) {
            const v = Math.abs(buf[i]);
            if (v > m) m = v;
          }
          if (m > maxPeakRef.current) maxPeakRef.current = m;
          meterRafRef.current = requestAnimationFrame(sample);
        };
        meterRafRef.current = requestAnimationFrame(sample);
      }
      // Periodic chunks + final chunk on stop; avoids empty blobs on some Windows/Chrome builds.
      rec.start(250);
      streamRef.current = stream;
      recorderRef.current = rec;
      startedAtRef.current = Date.now();
      setStatus("recording");
    } catch (e) {
      stopMeter();
      setError(e instanceof Error ? e.message : "Could not access microphone.");
      setStatus("error");
    }
  }, [stopMeter]);

  const stopRecording = useCallback((): Promise<VoiceRecordingResult | null> => {
    return new Promise((resolve) => {
      const rec = recorderRef.current;
      if (!rec || rec.state === "inactive") {
        resolve(null);
        return;
      }
      rec.onstop = () => {
        stopMeter();
        const mime = rec.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mime });
        const durationSec = Math.max(0, (Date.now() - startedAtRef.current) / 1000);
        const peakLevel = peakMeterActiveRef.current ? maxPeakRef.current : -1;
        peakMeterActiveRef.current = false;
        chunksRef.current = [];
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setStatus("idle");
        resolve({ blob, mimeType: mime, durationSec, peakLevel });
      };
      if (rec.state === "recording") {
        try {
          rec.requestData();
        } catch {
          /* ignore */
        }
      }
      rec.stop();
    });
  }, [stopMeter]);

  const cancelRecording = useCallback(() => {
    stopMeter();
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.onstop = () => {
        chunksRef.current = [];
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setStatus("idle");
      };
      rec.stop();
    } else {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      recorderRef.current = null;
      setStatus("idle");
    }
  }, [stopMeter]);

  return {
    status,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
    isSupported:
      typeof window !== "undefined" &&
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== "undefined",
  };
}
