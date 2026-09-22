"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const VISUALIZER_BARS = 7;

/**
 * Records microphone audio in the browser (native MediaRecorder API -
 * free, built into every modern browser) and hands back a Blob you can
 * upload to your own backend for transcription. This is what lets us
 * use the free, self-hosted Whisper model instead of any paid speech
 * API or browser-vendor speech service.
 *
 * Also exposes real-time audio levels (via the Web Audio API's
 * AnalyserNode) while recording, so the UI can react to your actual
 * voice volume instead of playing a canned CSS animation loop.
 */
export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  // Start optimistic (true) so server-rendered HTML and the client's
  // first render match exactly - `navigator` doesn't exist during SSR,
  // so checking it eagerly here would render differently on the server
  // vs. the client and trigger a hydration mismatch. We correct this
  // in an effect right after mount instead.
  const [isSupported, setIsSupported] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Live audio levels, updated every animation frame while recording.
  // audioLevel: single 0-1 number (overall loudness) - good for driving
  // one scalar (e.g. how much the mic button/ring "breathes").
  // frequencyBars: an array of 0-1 values across the spectrum - good
  // for a multi-bar waveform visualizer that actually reflects the
  // sound being picked up, not a repeating animation.
  const [audioLevel, setAudioLevel] = useState(0);
  const [frequencyBars, setFrequencyBars] = useState<number[]>(
    new Array(VISUALIZER_BARS).fill(0)
  );

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    setIsSupported(!!navigator.mediaDevices?.getUserMedia);
  }, []);

  const stopVisualizer = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    setAudioLevel(0);
    setFrequencyBars(new Array(VISUALIZER_BARS).fill(0));
  }, []);

  const startVisualizer = useCallback((stream: MediaStream) => {
    const AudioCtx =
      window.AudioContext || (window as any).webkitAudioContext;
    const audioContext = new AudioCtx();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 128; // small + fast; plenty of resolution for a UI meter
    analyser.smoothingTimeConstant = 0.75; // smooths frame-to-frame jitter

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    audioContextRef.current = audioContext;
    analyserRef.current = analyser;

    const freqData = new Uint8Array(analyser.frequencyBinCount);
    const binsPerBar = Math.floor(freqData.length / VISUALIZER_BARS) || 1;

    const tick = () => {
      analyser.getByteFrequencyData(freqData);

      let sum = 0;
      for (let i = 0; i < freqData.length; i++) sum += freqData[i];
      setAudioLevel(sum / freqData.length / 255);
      const bars: number[] = [];
      for (let b = 0; b < VISUALIZER_BARS; b++) {
        let barSum = 0;
        const start = b * binsPerBar;
        const end = start + binsPerBar;
        for (let i = start; i < end && i < freqData.length; i++) {
          barSum += freqData[i];
        }
        bars.push(barSum / binsPerBar / 255);
      }
      setFrequencyBars(bars);
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.start();
      setIsRecording(true);
      startVisualizer(stream);
    } catch (e: any) {
      setError(e.message || "Microphone access denied");
    }
  }, [startVisualizer]);

  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const mediaRecorder = mediaRecorderRef.current;
      stopVisualizer();
      if (!mediaRecorder) {
        resolve(null);
        return;
      }
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        streamRef.current?.getTracks().forEach((track) => track.stop());
        setIsRecording(false);
        resolve(blob);
      };
      mediaRecorder.stop();
    });
  }, [stopVisualizer]);

  useEffect(() => {
    return () => stopVisualizer();
  }, []);

  return {
    isRecording,
    isSupported,
    error,
    startRecording,
    stopRecording,
    audioLevel,
    frequencyBars,
  };
}

