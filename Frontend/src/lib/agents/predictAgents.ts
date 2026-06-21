/**
 * Client-side, instant prediction of which agents the orchestrator will use for a
 * message — so the Live Agent graph can render the planned network the moment the
 * user hits send, with zero backend round-trip.
 *
 * This is a deliberately LIGHTWEIGHT mirror of the backend's authority
 * (`Backend/agents/common/domain_router.py`). It only needs to be roughly right:
 * the real backend `agent_trace` streams in within ~a second and reconciles the
 * graph (advancing planned nodes to in_progress/completed, adding any it missed),
 * so a slightly-off guess self-corrects. Keep it simple; don't chase exact parity.
 */
import type { AgentId } from "./backendAgentRegistry";

const KEYWORDS: Record<"recovery" | "performance" | "logistics" | "sponsorship", string[]> = {
  recovery: [
    "tired", "exhaust", "fatigue", "sore", "ache", "aching", "pain", "hurt", "injur",
    "strain", "recover", "rest", "sleep", "slept", "stress", "burnout", "overtrain",
    "knee", "shoulder", "wrist", "ankle", "elbow", "hamstring", "stiff", "cramp", "drained",
  ],
  performance: [
    "perform", "stats", "statistic", "progress", "trend", "improv", "winning", "won ",
    "loss", "losing", "lost", "result", "score", "weak", "strong", "how am i doing",
    "how am i performing", "playing well", "my form",
  ],
  logistics: [
    "flight", "fly", "plane", "airfare", "airport", "travel", "trip", "hotel", "stay",
    "accommodation", "lodging", "book", "tournament", "commute", "transport", "packing",
  ],
  sponsorship: ["sponsor", "brand", "deal", "endorse", "outreach", "partnership", "marketing"],
};

const PRIORITY = ["recovery", "performance", "logistics", "sponsorship"] as const;

const SMALLTALK = new Set([
  "hi", "hii", "hey", "heya", "hello", "yo", "sup", "howdy", "thanks", "thank you",
  "thx", "ty", "cheers", "ok", "okay", "k", "cool", "nice", "great", "awesome",
  "perfect", "got it", "gotcha", "gm", "morning", "yes", "yep", "yeah", "no", "bye",
  "np", "no problem", "sounds good", "good morning", "good evening", "good afternoon",
]);

function detect(message: string): (typeof PRIORITY)[number][] {
  const text = ` ${message.toLowerCase()} `;
  return PRIORITY.filter((domain) => KEYWORDS[domain].some((kw) => text.includes(kw)));
}

function isSmalltalk(message: string): boolean {
  const text = message.toLowerCase().trim().replace(/[!.?]+$/g, "");
  if (!text) return true;
  if (message.includes("?")) return false;
  if (detect(message).length) return false;
  if (SMALLTALK.has(text)) return true;
  const words = text.split(/\s+/).filter(Boolean);
  return words.length > 0 && words.length <= 3 && words.every((w) => SMALLTALK.has(w));
}

/** Predicted agents for the planned graph (always includes athlete_context). */
export function predictAgents(message: string): AgentId[] {
  const planned: AgentId[] = ["athlete_context"];
  if (isSmalltalk(message)) return [...planned, "assistant"];
  const domains = detect(message);
  if (!domains.length) return [...planned, "assistant"];
  planned.push(domains[0]);
  for (const d of domains.slice(1)) {
    if ((d === "recovery" || d === "performance") && !planned.includes(d)) planned.push(d);
  }
  return planned;
}
