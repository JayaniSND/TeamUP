import { memo, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A click / drag-and-drop file picker. One file at a time — it hands the chosen
 * File to the parent, which decides what to do (here: send it for conversion).
 */
export const FileDrop = memo(function FileDrop({
  accept,
  onFile,
  disabled,
  title = "Drag & drop, or click to browse",
  hint,
}: {
  accept?: string;
  onFile: (file: File) => void;
  disabled?: boolean;
  title?: string;
  hint?: string;
}) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = (file?: File | null) => {
    if (file) onFile(file);
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!disabled) pick(e.dataTransfer.files?.[0]);
      }}
      className={cn(
        "flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-9 text-center transition-colors duration-200",
        disabled
          ? "pointer-events-none opacity-60"
          : "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
        over
          ? "border-accent bg-accent/10"
          : "border-accent/25 bg-surface-2 hover:border-accent/45 hover:bg-accent/5"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = ""; // allow re-picking the same file
        }}
      />
      <span className="grid size-11 place-items-center rounded-2xl bg-accent/12 text-accent ring-1 ring-accent/20">
        <UploadCloud className="size-5" strokeWidth={1.9} />
      </span>
      <p className="mt-3 text-sm font-semibold text-text">{title}</p>
      {hint && <p className="mt-1 text-xs text-text-dim">{hint}</p>}
    </div>
  );
});
