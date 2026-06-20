"""Recovery agent — flags fatigue / soreness / overtraining patterns.

Pulls the athlete's recent recovery logs, training, and metrics, asks Claude
for an overtraining assessment, writes a visible insight to `agent_outputs`,
and replies. Framed as wellness/self-management, not medical diagnosis.

Speaks the Agent Chat Protocol (usable via ASI:One/Agentverse and callable by
the Orchestrator).

Run:  python -m agents.recovery   (from Backend/)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format(v: dict) -> str:
    if v.get("risk_level", "none") in ("none", "low") and not v.get("body_parts"):
        return "✅ Recovery: no overtraining pattern in your recent history."
    parts = ", ".join(v.get("body_parts") or []) or "an area"
    return (
        f"⚠️ Recovery flag — risk {v.get('risk_level', 'unknown')} ({parts}).\n"
        f"   {v.get('summary', '').strip()}\n"
        f"   👉 {v.get('recommended_action', '').strip()}"
    )


async def _recently_flagged(user_id: str, hours: int = 72) -> bool:
    """Agent-memory stand-in: was a recovery flag written in the last `hours`?

    Mirrors framework v4's Redis Agent Memory dedup using the backend's
    agent_outputs feed, so the passive sweep doesn't spam duplicate alerts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for o in await backend.recent_agent_outputs(user_id, section="recovery", limit=5):
        if o.get("severity", "none") in ("none", "info"):
            continue
        try:
            if datetime.fromisoformat(o["ts"]) > cutoff:
                return True
        except (KeyError, ValueError):
            continue
    return False


async def _assess(user_id: str, note: str) -> dict:
    # 14-day window across ALL sections for linguistic-drift detection.
    recent = await backend.recent_entries(user_id, limit=40)
    logs = await backend.recent_recovery_logs(user_id, limit=14)
    training = await backend.recent_training(user_id, limit=14)
    metrics = await backend.recent_metrics(user_id, limit=20)
    verdict = await claude.assess_recovery(note, recent, logs, training, metrics)
    # Only surface a dashboard insight for a genuine flag.
    if verdict.get("risk_level", "none") not in ("none", "low"):
        await backend.create_agent_output(
            user_id,
            agent_name="Recovery Agent",
            section="recovery",
            summary=verdict.get("summary", ""),
            severity=verdict.get("severity", "info"),
            recommended_action=verdict.get("recommended_action", ""),
        )
    return verdict


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Recovery agent ready. Send a soreness/fatigue note and I'll check "
            "for overtraining patterns."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    passive = env.get("kind") == "run"  # orchestrator-triggered background sweep

    # Passive sweep: skip if we already flagged this athlete in the last 72h.
    if passive and await _recently_flagged(user_id):
        summary = "✅ Recovery: already flagged within 72h — skipping a duplicate alert."
        ctx.logger.info("Recovery dedup-skip for %s", user_id)
    else:
        verdict = await _assess(user_id, env["text"])
        summary = _format(verdict)
        ctx.logger.info("Recovery risk=%s for %s", verdict.get("risk_level"), user_id)

    if passive and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            user_id, env["text"],
            kind="result", agent="recovery", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[recovery] address: {agent.address}")
    agent.run()
