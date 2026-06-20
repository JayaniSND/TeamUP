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
    lines: list[str] = []
    # Physical recovery read.
    if v.get("risk_level", "none") in ("none", "low") and not v.get("body_parts"):
        lines.append("✅ Recovery: no overtraining pattern in your recent history.")
    else:
        parts = ", ".join(v.get("body_parts") or []) or "an area"
        lines.append(f"⚠️ Recovery flag — risk {v.get('risk_level', 'unknown')} ({parts}).")
        if v.get("summary"):
            lines.append(f"   {v['summary'].strip()}")
        if v.get("recommended_action"):
            lines.append(f"   👉 {v['recommended_action'].strip()}")
    # Behavioral / emotional arc (longer window).
    pt = v.get("pattern_type", "none")
    if pt and pt != "none":
        lines.append(f"🔎 Pattern — {pt.replace('_', ' ')}: {v.get('pattern_summary', '').strip()}")
        if v.get("chain_message", "").strip():
            lines.append(f"   ➡️ {v['chain_message'].strip()}")
    return "\n".join(lines)


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
    # Wider window (~60 days of entries) so the longer behavioral arcs surface;
    # physical drift still reads from the most recent slice.
    recent = await backend.recent_entries(user_id, limit=60)
    logs = await backend.recent_recovery_logs(user_id, limit=14)
    training = await backend.recent_training(user_id, limit=14)
    metrics = await backend.recent_metrics(user_id, limit=20)
    verdict = await claude.assess_recovery(note, recent, logs, training, metrics)
    # Surface a physical flag insight.
    if verdict.get("risk_level", "none") not in ("none", "low"):
        await backend.create_agent_output(
            user_id,
            agent_name="Recovery Agent",
            section="recovery",
            summary=verdict.get("summary", ""),
            severity=verdict.get("severity", "info"),
            recommended_action=verdict.get("recommended_action", ""),
        )
    # Surface a behavioral/emotional pattern insight (separate card).
    if verdict.get("pattern_type", "none") not in ("none", ""):
        await backend.create_agent_output(
            user_id,
            agent_name="Recovery Agent",
            section="recovery",
            summary=f"[{verdict['pattern_type']}] {verdict.get('pattern_summary', '')}",
            severity="info",
            recommended_action=verdict.get("chain_message", ""),
        )
    return verdict


async def _chain(ctx: Context, user_id: str, verdict: dict):
    """Agent chaining (v5 §6.2): a detected arc fires the next agent."""
    target = verdict.get("chain_to", "none")
    if target in ("none", ""):
        return
    addr = config.address_for(target)
    if not addr:
        return  # target agent not configured — chain note still shows in the reply
    msg = verdict.get("chain_message") or verdict.get("pattern_summary", "")
    ctx.logger.info("Recovery chaining %s → %s", verdict.get("pattern_type"), target)
    try:
        await ctx.send(addr, make_chat(encode_envelope(user_id, msg)))
    except Exception as e:  # noqa: BLE001 - chaining is best-effort, never block the reply
        ctx.logger.warning("chain to %s failed: %s", target, e)


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
        ctx.logger.info(
            "Recovery risk=%s pattern=%s for %s",
            verdict.get("risk_level"), verdict.get("pattern_type"), user_id,
        )
        await _chain(ctx, user_id, verdict)  # fire the next agent on a detected arc

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
