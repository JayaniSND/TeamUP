import type { ReactNode } from "react";

/**
 * Tiny dependency-free Markdown renderer for chat answers.
 *
 * The orchestrator/RAG replies come back as Markdown (## headings, **bold**,
 * bullet/numbered lists, ---, `code`, [links]). The chat bubble used to print
 * the raw text, so it looked unformatted. This handles the subset the backend
 * actually emits — no react-markdown dependency (node_modules is committed).
 */

const INLINE = /(\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*([^*]+)\*|_([^_]+)_)/g;

function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[2] ?? m[3]) {
      out.push(
        <strong key={key++} className="font-semibold text-text">
          {m[2] ?? m[3]}
        </strong>
      );
    } else if (m[4]) {
      out.push(
        <code key={key++} className="rounded bg-line/60 px-1 py-0.5 font-mono text-[0.85em]">
          {m[4]}
        </code>
      );
    } else if (m[5]) {
      out.push(
        <a
          key={key++}
          href={m[6]}
          target="_blank"
          rel="noreferrer"
          className="text-accent underline underline-offset-2"
        >
          {m[5]}
        </a>
      );
    } else if (m[7] ?? m[8]) {
      out.push(
        <em key={key++} className="italic">
          {m[7] ?? m[8]}
        </em>
      );
    }
    last = INLINE.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const isHr = (s: string) => /^([-*_])\1{2,}$/.test(s.replace(/\s/g, ""));
const isHeading = (s: string) => /^#{1,6}\s+/.test(s);
const isUl = (s: string) => /^\s*[-*]\s+/.test(s);
const isOl = (s: string) => /^\s*\d+[.)]\s+/.test(s);
const isStructural = (s: string) => isHeading(s) || isUl(s) || isOl(s) || isHr(s.trim());

export function Markdown({ text }: { text: string }) {
  const lines = (text ?? "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    if (isHr(trimmed)) {
      blocks.push(<hr key={key++} className="my-2 border-line" />);
      i++;
      continue;
    }

    const h = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (h) {
      const big = h[1].length <= 2;
      blocks.push(
        <p
          key={key++}
          className={
            big
              ? "mt-2.5 mb-1 text-sm font-semibold text-text first:mt-0"
              : "mt-2 mb-0.5 text-[13px] font-semibold text-text first:mt-0"
          }
        >
          {renderInline(h[2])}
        </p>
      );
      i++;
      continue;
    }

    if (isUl(raw)) {
      const items: ReactNode[] = [];
      while (i < lines.length && isUl(lines[i])) {
        items.push(
          <li key={items.length} className="leading-snug">
            {renderInline(lines[i].replace(/^\s*[-*]\s+/, ""))}
          </li>
        );
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-1.5 list-disc space-y-0.5 pl-4 marker:text-text-dim">
          {items}
        </ul>
      );
      continue;
    }

    if (isOl(raw)) {
      const items: ReactNode[] = [];
      while (i < lines.length && isOl(lines[i])) {
        items.push(
          <li key={items.length} className="leading-snug">
            {renderInline(lines[i].replace(/^\s*\d+[.)]\s+/, ""))}
          </li>
        );
        i++;
      }
      blocks.push(
        <ol key={key++} className="my-1.5 list-decimal space-y-0.5 pl-4 marker:text-text-dim">
          {items}
        </ol>
      );
      continue;
    }

    // paragraph — gather wrapped lines until a blank or structural line
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !isStructural(lines[i])) {
      para.push(lines[i].trim());
      i++;
    }
    blocks.push(
      <p key={key++} className="my-1.5 first:mt-0 last:mb-0">
        {para.flatMap((line, idx) =>
          idx === 0 ? renderInline(line) : [<br key={`br-${idx}`} />, ...renderInline(line)]
        )}
      </p>
    );
  }

  return (
    <div className="text-left [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">{blocks}</div>
  );
}
