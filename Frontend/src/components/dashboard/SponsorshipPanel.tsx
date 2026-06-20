import { memo, useState } from "react";
import { Handshake, Mail, ShieldCheck, Send } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { SponsorshipLead, Status } from "@/types/athlete";

const statusMap: Record<SponsorshipLead["status"], Status> = {
  Suggested: "neutral",
  Drafted: "ai",
  "In review": "warning",
};

/**
 * Sponsorship flow is strictly: Find sponsor → Draft email → user approves → Send.
 * Drafting never sends. The "Send" step only appears after an explicit approve,
 * enforcing the product rule in the UI. The per-lead "Draft email" is this
 * section's contextual AI action.
 */
export const SponsorshipPanel = memo(function SponsorshipPanel({
  leads,
  onDraft,
}: {
  leads: SponsorshipLead[];
  onDraft: (lead: SponsorshipLead) => void;
}) {
  // local per-lead flow state: idle → drafted → approved (ready to send)
  const [flow, setFlow] = useState<Record<string, "idle" | "drafted" | "approved">>({});

  const stateOf = (l: SponsorshipLead) =>
    flow[l.id] ?? (l.status === "Drafted" ? "drafted" : "idle");

  return (
    <SectionCard
      id="sponsorship"
      title="Sponsorship"
      subtitle="Agent-matched brand leads"
      icon={Handshake}
      delay={0.2}
    >
      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {leads.map((l) => {
          const state = stateOf(l);
          return (
            <li key={l.id} className="glass-inset card-hover flex flex-col rounded-[1.35rem] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <span className="text-sm font-semibold text-text">{l.brand}</span>
                  <Badge status={statusMap[l.status]} dot={false} className="ml-2">
                    {l.category}
                  </Badge>
                </div>
                <div className="glass-chip shrink-0 rounded-2xl px-3 py-2 text-right">
                  <div className="text-[10px] uppercase tracking-wider text-text-dim">Fit</div>
                  <div
                    className={cn(
                      "tnum text-lg font-bold",
                      l.fitScore >= 85 ? "text-positive" : l.fitScore >= 75 ? "text-accent" : "text-warning"
                    )}
                  >
                    {l.fitScore}
                  </div>
                </div>
              </div>
              <p className="mt-1.5 flex-1 text-[11px] leading-relaxed text-text-muted">{l.reason}</p>

              <div className="mt-3 flex items-center gap-2">
                {state === "idle" && (
                  <Button
                    variant="ai"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      setFlow((f) => ({ ...f, [l.id]: "drafted" }));
                      onDraft(l);
                    }}
                  >
                    <Mail className="size-3.5" />
                    Draft email
                  </Button>
                )}
                {state === "drafted" && (
                  <>
                    <span className="flex items-center gap-1 text-[11px] text-text-muted">
                      <Mail className="size-3.5 text-ai" /> Draft ready
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-auto"
                      onClick={() => setFlow((f) => ({ ...f, [l.id]: "approved" }))}
                    >
                      <ShieldCheck className="size-3.5 text-positive" />
                      Approve
                    </Button>
                  </>
                )}
                {state === "approved" && (
                  <>
                    <span className="flex items-center gap-1 text-[11px] text-positive">
                      <ShieldCheck className="size-3.5" /> Approved
                    </span>
                    <Button variant="primary" size="sm" className="ml-auto">
                      <Send className="size-3.5" />
                      Send
                    </Button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-3 flex items-center gap-1.5 text-[11px] text-text-dim">
        <ShieldCheck className="size-3.5" />
        Emails are never sent automatically — you approve every send.
      </p>
    </SectionCard>
  );
});
