"""Performance agent — summarizes win/loss and skill trends.

Reads recent match results, training, and metrics, asks Claude for a grounded
performance summary, and writes a visible insight to `agent_outputs`.

Speaks the Agent Chat Protocol (usable via ASI:One/Agentverse and callable by
the Orchestrator).

Run:  python -m agents.performance   (from Backend/)
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
    name="performance",
    seed=config.PERFORMANCE_SEED,
    port=config.PERFORMANCE_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format(v: dict) -> str:
    return (
        f"📈 Performance ({v.get('trend', 'unknown')}).\n"
        f"   {v.get('summary', '').strip()}\n"
        f"   Strongest: {v.get('strongest_area', '—')} | "
        f"Weakest: {v.get('weakest_area', '—')}\n"
        f"   👉 Focus: {v.get('recommended_focus', '').strip()}"
    )


async def _analyze(user_id: str, note: str) -> dict:
    matches = await backend.recent_match_results(user_id, limit=10)
    training = await backend.recent_training(user_id, limit=10)
    metrics = await backend.recent_metrics(user_id, limit=20)
    v = await claude.analyze_performance(note, matches, training, metrics)
    await backend.create_agent_output(
        user_id,
        agent_name="Performance Agent",
        section="performance",
        summary=v.get("summary", ""),
        severity="info",
        recommended_action=v.get("recommended_focus", ""),
    )
    return v


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Performance agent ready. Log a match or training note and I'll "
            "track your form and trends."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    v = await _analyze(env["user_id"], env["text"])
    summary = _format(v)
    ctx.logger.info("Performance trend=%s for %s", v.get("trend"), env["user_id"])

    if env.get("kind") == "run" and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            env["user_id"], env["text"],
            kind="result", agent="performance", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[performance] address: {agent.address}")
    agent.run()
