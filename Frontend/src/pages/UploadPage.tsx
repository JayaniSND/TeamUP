import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  Copy,
  FileText,
  ImagePlus,
  Info,
  Loader2,
  Mic,
  PenLine,
  Send,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Button } from "@/components/ui/Button";
import { FileDrop } from "@/components/upload/FileDrop";
import { VoiceRecorder } from "@/components/upload/VoiceRecorder";
import { convertPhoto, convertVoice, submitUploadEntry, type IngestInputType } from "@/lib/api";
import { athleteData } from "@/data/mockAthleteData";
import { cn } from "@/lib/utils";

type Method = "photo" | "voice" | "text";
type Status = "idle" | "loading" | "done" | "error";
type SubmitStatus = "idle" | "submitting" | "submitted" | "error";

const METHODS: { id: Method; label: string; icon: typeof Mic; desc: string }[] = [
  { id: "photo", label: "Note / Photo", icon: ImagePlus, desc: "Image or .txt note" },
  { id: "voice", label: "Voice", icon: Mic, desc: "Record or upload audio" },
  { id: "text", label: "Text", icon: PenLine, desc: "Type or paste" },
];

const methodFromLocation = (pathname: string, search: string): Method => {
  const requested = new URLSearchParams(search).get("method");
  if (pathname.endsWith("/voice") || requested === "voice") return "voice";
  if (requested === "text") return "text";
  return "photo";
};

// Sidebar is shared with the dashboard; section clicks self-navigate via the
// router, so its onSelect is a no-op here. Module-level keeps the identity
// stable for the memoized Sidebar.
const NOOP = () => {};

export default function UploadPage() {
  const location = useLocation();
  const routeMethod = useMemo(
    () => methodFromLocation(location.pathname, location.search),
    [location.pathname, location.search]
  );
  const [method, setMethod] = useState<Method>(routeMethod);
  const [result, setResult] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [source, setSource] = useState("");
  const [sourceInputType, setSourceInputType] = useState<IngestInputType>("text");
  const [copied, setCopied] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<SubmitStatus>("idle");
  const [submitError, setSubmitError] = useState("");
  const [submittedSummary, setSubmittedSummary] = useState("");

  const busy = status === "loading";
  const submitting = submitStatus === "submitting";
  const canSubmit = !!result.trim() && !busy && !submitting && submitStatus !== "submitted";

  useEffect(() => {
    setMethod(routeMethod);
  }, [routeMethod]);

  const runConvert = useCallback(async (fn: () => Promise<string>, label: string, inputType: IngestInputType) => {
    setStatus("loading");
    setError("");
    setSource(label);
    setSourceInputType(inputType);
    setCopied(false);
    setSubmitStatus("idle");
    setSubmitError("");
    setSubmittedSummary("");
    try {
      const text = await fn();
      setResult(text);
      if (text.trim()) {
        setStatus("done");
      } else {
        setStatus("error");
        setError("No text was detected. Try a clearer photo or a longer, louder recording.");
      }
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Conversion failed. Please try again.");
    }
  }, []);

  const onPhoto = useCallback(
    (file: File) => runConvert(() => convertPhoto(file), `Photo · ${file.name}`, "text"),
    [runConvert]
  );
  const onVoice = useCallback(
    (blob: Blob, name: string) => runConvert(() => convertVoice(blob, name), `Voice · ${name}`, "voice"),
    [runConvert]
  );

  const onText = (v: string) => {
    setResult(v);
    setSource("Typed note");
    setSourceInputType("text");
    setError("");
    setCopied(false);
    setSubmitStatus("idle");
    setSubmitError("");
    setSubmittedSummary("");
    setStatus(v.trim() ? "done" : "idle");
  };

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — ignore */
    }
  };

  const clear = () => {
    setResult("");
    setStatus("idle");
    setError("");
    setSource("");
    setSourceInputType("text");
    setCopied(false);
    setSubmitStatus("idle");
    setSubmitError("");
    setSubmittedSummary("");
  };

  const submit = async () => {
    const text = result.trim();
    if (!text || submitting) return;

    setSubmitStatus("submitting");
    setSubmitError("");
    setSubmittedSummary("");

    try {
      const response = await submitUploadEntry({ text, inputType: sourceInputType });
      const sections = response.sections.map((section) => section.replace(/_/g, " ")).join(", ");
      const count = response.entriesCount || response.entries.length || 1;
      setSubmittedSummary(
        `Filed ${count} ${count === 1 ? "entry" : "entries"}${sections ? ` to ${sections}` : ""}.`
      );
      setSubmitStatus("submitted");
    } catch (e) {
      setSubmitStatus("error");
      setSubmitError(e instanceof Error ? e.message : "Submit failed. Please try again.");
    }
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden p-3 text-text sm:p-4 lg:p-4">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex min-h-[calc(100vh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:min-h-[calc(100vh-2rem)]">
        <Sidebar active="" onSelect={NOOP} profile={athleteData.profile} />

        <div className="min-w-0 flex-1">
          {/* mobile top bar (sidebar is hidden < lg) */}
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-white/85 px-4 py-2.5 backdrop-blur-md lg:hidden">
            <Link
              to="/dashboard"
              className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-accent"
              aria-label="Back to dashboard"
            >
              <ArrowLeft className="size-4" />
            </Link>
            <span className="text-sm font-semibold text-text">Upload Entry</span>
          </div>

          <main className="px-3 py-4 sm:px-5 lg:px-6 lg:py-6">
            <div className="mx-auto max-w-[1080px]">
              {/* header */}
              <header className="fade-up mb-4 flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent/12 text-accent ring-1 ring-accent/20">
                    <UploadCloud className="size-5" strokeWidth={1.9} />
                  </span>
                  <div className="min-w-0">
                    <h1 className="text-xl font-semibold tracking-tight text-text">Upload Entry</h1>
                    <p className="mt-0.5 text-sm text-text-muted">Add training notes by photo, voice, or text.</p>
                  </div>
                </div>
                <Link to="/dashboard" className="hidden lg:block">
                  <Button variant="outline" size="sm">
                    <ArrowLeft className="size-4" strokeWidth={1.9} />
                    Dashboard
                  </Button>
                </Link>
              </header>

              {/* no-database notice */}
              <div className="fade-up mb-4 flex items-start gap-2 rounded-xl bg-accent/[0.06] px-3 py-2 text-xs leading-relaxed text-text-muted ring-1 ring-accent/14">
                <Info className="mt-px size-3.5 shrink-0 text-accent" />
                Capture stays in preview until you submit it. Submit files the note through the backend librarian flow.
              </div>

              <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
                {/* left — method + input */}
                <div className="fade-up flex flex-col gap-4">
                  <div className="grid grid-cols-3 gap-2">
                    {METHODS.map((m) => {
                      const activeTab = method === m.id;
                      return (
                        <button
                          key={m.id}
                          onClick={() => setMethod(m.id)}
                          aria-pressed={activeTab}
                          className={cn(
                            "card-hover flex flex-col items-start gap-1.5 rounded-2xl border p-3 text-left",
                            activeTab
                              ? "border-accent/40 bg-accent/10 ring-1 ring-accent/30"
                              : "glass-card hover:bg-accent/[0.04]"
                          )}
                        >
                          <span
                            className={cn(
                              "grid size-8 place-items-center rounded-xl transition-colors",
                              activeTab ? "bg-accent text-white" : "glass-chip text-text-muted"
                            )}
                          >
                            <m.icon className="size-4" strokeWidth={1.9} />
                          </span>
                          <span className="text-[13px] font-semibold text-text">{m.label}</span>
                          <span className="text-[11px] leading-tight text-text-dim">{m.desc}</span>
                        </button>
                      );
                    })}
                  </div>

                  <section className="glass-card rounded-[1.45rem] p-4">
                    {method === "photo" && (
                      <div className="flex flex-col gap-3">
                        <FileDrop
                          accept="image/*,.txt,.md,.markdown,.text"
                          disabled={busy}
                          onFile={onPhoto}
                          title="Drop a photo or note, or click to browse"
                          hint="PNG · JPG · HEIC · or .txt / .md notes"
                        />
                        <p className="text-xs leading-relaxed text-text-dim">
                          A photo of handwritten or printed notes is transcribed with AI vision. Plain-text note files
                          are read directly.
                        </p>
                      </div>
                    )}

                    {method === "voice" && <VoiceRecorder onAudio={onVoice} disabled={busy} />}

                    {method === "text" && (
                      <div className="flex flex-col gap-2">
                        <label
                          htmlFor="upload-text"
                          className="text-[11px] font-semibold uppercase tracking-wider text-text-dim"
                        >
                          Type or paste your notes
                        </label>
                        <textarea
                          id="upload-text"
                          value={result}
                          onChange={(e) => onText(e.target.value)}
                          rows={9}
                          placeholder="Worked on my serve today, felt sharp. Right knee a little sore after the long session…"
                          className="scroll-thin w-full resize-y rounded-2xl border border-line bg-surface-2 p-3 text-sm leading-relaxed text-text outline-none transition-colors placeholder:text-text-dim focus:border-accent/45 focus:ring-2 focus:ring-accent/20"
                        />
                        <p className="text-xs leading-relaxed text-text-dim">
                          Your text appears in the preview as you type. It stays on this page — nothing is saved.
                        </p>
                      </div>
                    )}
                  </section>
                </div>

                {/* right — preview */}
                <section className="glass-card fade-up flex min-h-[340px] flex-col rounded-[1.45rem] p-4 lg:sticky lg:top-6 lg:self-start">
                  <header className="mb-3 flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-text-muted">
                        <FileText className="size-4" strokeWidth={1.8} />
                      </span>
                      <div className="min-w-0">
                        <h2 className="text-sm font-semibold text-text">Preview</h2>
                        <p className="truncate text-[11px] text-text-dim">{source || "Extracted / entered text"}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <span className="tnum mr-1 hidden text-[11px] text-text-dim sm:inline">{result.length} chars</span>
                      <Button variant="subtle" size="sm" onClick={copy} disabled={!result}>
                        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                        {copied ? "Copied" : "Copy"}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={clear} disabled={!result && status === "idle"}>
                        <Trash2 className="size-3.5" />
                        Clear
                      </Button>
                    </div>
                  </header>

                  <div className="glass-inset scroll-thin max-h-[58vh] min-h-[230px] flex-1 overflow-y-auto rounded-2xl p-4">
                    {busy ? (
                      <div className="flex h-full min-h-[190px] flex-col items-center justify-center gap-3 text-center text-text-muted">
                        <Loader2 className="size-6 animate-spin text-accent" />
                        <div className="text-sm font-medium">Converting…</div>
                        {source && <div className="text-xs text-text-dim">{source}</div>}
                      </div>
                    ) : status === "error" ? (
                      <div className="flex h-full min-h-[190px] flex-col items-center justify-center gap-2 px-2 text-center">
                        <AlertCircle className="size-6 text-negative" />
                        <div className="text-sm font-semibold text-negative">Couldn’t convert</div>
                        <div className="max-w-sm text-xs leading-relaxed text-text-muted">{error}</div>
                      </div>
                    ) : result ? (
                      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-text">{result}</p>
                    ) : (
                      <div className="flex h-full min-h-[190px] flex-col items-center justify-center gap-2 text-center text-text-dim">
                        <FileText className="size-6 opacity-50" />
                        <div className="max-w-[16rem] text-sm leading-relaxed">
                          Your converted or typed text will appear here.
                        </div>
                      </div>
                    )}
                  </div>

                  <footer className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-h-5 text-xs leading-relaxed">
                      {submitStatus === "submitted" && (
                        <span className="inline-flex items-center gap-1.5 font-medium text-accent">
                          <Check className="size-3.5" />
                          {submittedSummary}
                        </span>
                      )}
                      {submitStatus === "error" && (
                        <span className="inline-flex items-center gap-1.5 font-medium text-negative">
                          <AlertCircle className="size-3.5" />
                          {submitError}
                        </span>
                      )}
                    </div>

                    <Button
                      variant="primary"
                      size="md"
                      onClick={submit}
                      disabled={!canSubmit}
                      className="shrink-0"
                    >
                      {submitting ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : submitStatus === "submitted" ? (
                        <Check className="size-4" />
                      ) : (
                        <Send className="size-4" />
                      )}
                      {submitting ? "Submitting" : submitStatus === "submitted" ? "Submitted" : "Submit entry"}
                    </Button>
                  </footer>
                </section>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
