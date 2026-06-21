import { useEffect, useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function CheckoutReturnPage({ status }: { status: "success" | "cancelled" }) {
  const location = useLocation();
  const sessionId = useMemo(() => new URLSearchParams(location.search).get("session_id"), [location.search]);
  const success = status === "success";

  useEffect(() => {
    window.opener?.postMessage(
      {
        type: "teamup:stripe-checkout",
        status,
        sessionId: sessionId ?? undefined,
      },
      window.location.origin
    );

    const id = window.setTimeout(() => {
      if (window.opener) window.close();
    }, 750);
    return () => window.clearTimeout(id);
  }, [sessionId, status]);

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden p-4 text-text">
      <div className="app-aurora" />
      <section className="glass-card relative z-10 w-full max-w-[420px] rounded-[1.7rem] p-5 text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/18">
          {success ? <CheckCircle2 className="size-6" /> : <XCircle className="size-6" />}
        </span>
        <h1 className="mt-4 text-lg font-semibold text-text">
          {success ? "Payment received" : "Checkout cancelled"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-text-muted">
          {window.opener
            ? "Returning you to TeamUP now. You can close this window if it does not close automatically."
            : "Return to TeamUP to continue. If payment succeeded, the app will verify it from the original window."}
        </p>
        <div className="mt-4 flex justify-center">
          {window.opener ? (
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-text-dim">
              <Loader2 className="size-3.5 animate-spin" /> Closing window
            </span>
          ) : (
            <Link to="/dashboard">
              <Button variant="primary" size="sm">
                Back to dashboard
              </Button>
            </Link>
          )}
        </div>
      </section>
    </div>
  );
}
