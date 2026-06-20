"""Recovery agent — flags overtraining / injury-risk patterns.

Job: given an injury or fitness note, pull the athlete's recent injury log
and metrics from Dev 2's backend, ask Claude whether there's an
overtraining pattern, write a flag the dashboard surfaces, and reply.

Speaks the standardized Agent Chat Protocol so it is discoverable and
directly usable through ASI:One and Agentverse, and so the Orchestrator can
call it as part of multi-agent orchestration.

  • Human (plain text via ASI:One) → assess and reply with a readable verdict.
  • Orchestrator (envelope with kind="assess") → reply a structured
    envelope (kind="assess_result") so the conductor can compose one answer.

Run:  python -m agents.recovery   (from the Backend/ directory)
On boot it prints its address — paste that into .env as RECOVERY_ADDRESS.
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
    name="recovery",
    seed=config.RECOVERY_SEED,
    port=config.RECOVERY_PORT,
    mailbox=True,  # reachable through Agentverse
)

chat_proto = Protocol(spec=chat_protocol_spec)


def _format_verdict(v: dict) -> str:
    """Render an assessment dict as a human-readable chat reply."""
    if not v.get("overtraining_risk"):
        return (
            "✅ No overtraining pattern detected in your recent history. "
            "Keep logging and I'll keep watching."
        )
    parts = ", ".join(v.get("body_parts") or []) or "unspecified area"
    return (
        f"⚠️ Overtraining risk ({v.get('severity', 'unknown')}) — {parts}.\n"
        f"{v.get('rationale', '').strip()}\n"
        f"👉 {v.get('recommendation', '').strip()}"
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # Every incoming message must be acknowledged (protocol requirement).
    await ctx.send(sender, make_ack(msg))

    if is_start(msg):
        await ctx.send(
            sender,
            make_chat(
                "👋 Recovery agent ready. Send an injury or fitness note "
                "(e.g. 'knee sore again after intervals') and I'll check for "
                "overtraining patterns."
            ),
        )
        return

    raw = text_of(msg)
    if not raw.strip():
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    note = env["text"]

    # Pull the athlete's recent injury history + metrics for context.
    injury = await backend.recent_entries(user_id, "injury_log", limit=10)
    metrics = await backend.recent_metrics(user_id, limit=20)

    verdict = await claude.assess_overtraining(note, injury, metrics)

    # Surface the flag on the dashboard via the backend.
    await backend.create_recovery_flag(user_id, verdict)

    ctx.logger.info(
        "Assessed note for %s -> risk=%s severity=%s",
        user_id,
        verdict.get("overtraining_risk"),
        verdict.get("severity"),
    )

    if env.get("kind") == "assess" and env.get("req_id"):
        # Called by the Orchestrator: reply with a structured result it can
        # fold into a single user-facing answer.
        await ctx.send(
            sender,
            make_chat(
                encode_envelope(
                    user_id,
                    note,
                    kind="assess_result",
                    req_id=env["req_id"],
                    verdict=verdict,
                )
            ),
        )
    else:
        # Direct human use via ASI:One / Agentverse: reply in plain language.
        await ctx.send(sender, make_chat(_format_verdict(verdict), end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print(f"[recovery] address: {agent.address}")
    agent.run()
