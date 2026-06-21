import { memo, useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import { FileDrop } from "./FileDrop";

/**
 * Record from the mic (MediaRecorder) or upload an existing audio file. Either
 * way it hands a finished audio Blob to the parent, which sends it to the
 * backend for transcription. Recording is captured in full and transcribed
 * after stop — the browser MediaRecorder API isn't a live stream to Deepgram,
 * so the parent shows a loading state and then the transcript.
 */
function fmt(total: number) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export const VoiceRecorder = memo(function VoiceRecorder({
  onAudio,
  disabled,
}: {
  onAudio: (blob: Blob, filename: string) => void;
  disabled?: boolean;
}) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  const stopTimer = () => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const releaseStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  // Stop the mic + timer if the component unmounts mid-recording.
  useEffect(() => () => {
    stopTimer();
    releaseStream();
  }, []);

  const start = async () => {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Recording isn't supported in this browser — upload an audio file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        releaseStream();
        const ext = type.includes("mp4") || type.includes("aac") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        if (blob.size) onAudio(blob, `recording.${ext}`);
      };

      recorder.start();
      recorderRef.current = recorder;
      setSeconds(0);
      setRecording(true);
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      releaseStream();
      const denied = e instanceof DOMException && (e.name === "NotAllowedError" || e.name === "SecurityError");
      setError(denied ? "Microphone permission was denied." : "Could not start recording.");
    }
  };

  const stop = () => {
    stopTimer();
    setRecording(false);
    const r = recorderRef.current;
    if (r && r.state !== "inactive") r.stop();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="glass-inset flex flex-col items-center gap-3 rounded-2xl px-6 py-7 text-center">
        <button
          type="button"
          onClick={recording ? stop : start}
          disabled={disabled}
          aria-label={recording ? "Stop recording" : "Start recording"}
          className={cn(
            "grid size-16 place-items-center rounded-full text-white transition-all duration-200 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/30 disabled:pointer-events-none disabled:opacity-50",
            recording
              ? "animate-pulse bg-negative shadow-[0_0_0_8px_rgba(194,96,122,0.16)]"
              : "bg-accent shadow-[0_0_0_8px_rgba(47,160,132,0.14)] hover:bg-[#268b72]"
          )}
        >
          {recording ? <Square className="size-6" fill="currentColor" /> : <Mic className="size-7" strokeWidth={2} />}
        </button>
        <div>
          <div className="tnum text-lg font-semibold text-text">{fmt(seconds)}</div>
          <div className="text-xs text-text-dim">
            {recording ? "Recording… tap to stop & transcribe" : "Tap to record"}
          </div>
        </div>
      </div>

      {error && (
        <p className="rounded-xl bg-negative/10 px-3 py-2 text-xs font-medium text-negative ring-1 ring-negative/20">
          {error}
        </p>
      )}

      <div className="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-wider text-text-dim">
        <span className="h-px flex-1 bg-line" />
        or upload audio
        <span className="h-px flex-1 bg-line" />
      </div>

      <FileDrop
        accept="audio/*,.webm,.wav,.mp3,.m4a,.ogg,.flac,.aac"
        disabled={disabled || recording}
        onFile={(file) => onAudio(file, file.name || "audio.webm")}
        title="Drop an audio file, or click to browse"
        hint="webm · wav · mp3 · m4a · ogg · flac"
      />
    </div>
  );
});
