"""Sponsorship agent — finds brand fit and drafts cold outreach.

Reads the athlete profile, recent results, metrics, and media notes, asks
Claude for one realistic sponsor fit and a short draft email, and records a
`sponsorship_opportunities` row with status "drafted". APPROVAL-GATED: it only
ever drafts — it never sends.

Speaks the Agent Chat Protocol (usable via ASI:One/Agentverse and callable by
the Orchestrator).

Run:  python -m agents.sponsorship   (from Backend/)
"""

from __future__ import annotations

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from .common import backend_client as backend
from .common import claude, config
from .common.chat import (
    decode_envelope,
    encode_envelope,
    is_start,
    make_ack,
    make_chat,
    text_of,
)

agent = Agent(
    name="sponsorship",
    seed=config.SPONSORSHIP_SEED,
    port=config.SPONSORSHIP_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format(v: dict) -> str:
    return (
        f"🤝 Sponsor match: {v.get('brand_name', '—')} "
        f"({v.get('category', '—')}, fit {v.get('fit_score', 0):.2f}).\n"
        f"   {v.get('reason', '').strip()}\n"
        f"   ✉️ Draft ready for your review (status: drafted — not sent):\n"
        f"   {v.get('draft_email', '').strip()}"
    )


async def _suggest(user_id: str, note: str) -> dict:
    profile = await backend.athlete_profile(user_id)
    matches = await backend.recent_match_results(user_id, limit=10)
    metrics = await backend.recent_metrics(user_id, limit=20)
    media = await backend.recent_entries(user_id, section="media_notes", limit=10)
    v = await claude.suggest_sponsorship(note, profile, matches, metrics, media)
    await backend.create_sponsorship_opportunity(user_id, {
        "brand_name": v.get("brand_name", ""),
        "category": v.get("category", ""),
        "fit_score": v.get("fit_score", 0),
        "reason": v.get("reason", ""),
        "draft_email": v.get("draft_email", ""),
        "status": "drafted",
    })
    await backend.create_agent_output(
        user_id,
        agent_name="Sponsorship Agent",
        section="sponsorship",
        summary=f"Suggested {v.get('brand_name', '')} (fit {v.get('fit_score', 0):.2f}).",
        severity="info",
        recommended_action="Review and approve the draft email before sending.",
    )
    return v


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Sponsorship agent ready. Tell me about a recent win or achievement "
            "and I'll suggest a brand fit and draft an outreach email for your review."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    v = await _suggest(env["user_id"], env["text"])
    summary = _format(v)
    ctx.logger.info("Sponsorship suggested %s for %s", v.get("brand_name"), env["user_id"])

    if env.get("kind") == "run" and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            env["user_id"], env["text"],
            kind="result", agent="sponsorship", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[sponsorship] address: {agent.address}")
    agent.run()
