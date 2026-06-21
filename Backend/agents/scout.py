"""Scout agent — researches an opponent and writes a coaching note.

On a logged match (or an opponent query): scrapes the opponent's recent
results (Browserbase, with a cached fallback), uses Claude to summarize their
patterns and a tactical edge, writes the result as a `coaching` entry +
dashboard insight, and replies.

Speaks the Agent Chat Protocol (usable via ASI:One/Agentverse and callable by
the Orchestrator).

Run:  python -m agents.scout   (from Backend/)
"""

from __future__ import annotations

import asyncio

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
from .integrations import tournaments

agent = Agent(
    name="scout",
    seed=config.SCOUT_SEED,
    port=config.SCOUT_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format(s: dict, source: str) -> str:
    opp = s.get("opponent") or "your opponent"
    return (
        f"🔭 Scout on {opp} ({source} data):\n"
        f"   Patterns: {s.get('patterns', '').strip()}\n"
        f"   Strengths: {s.get('strengths', '').strip()}\n"
        f"   Weaknesses: {s.get('weaknesses', '').strip()}\n"
        f"   👉 Edge: {s.get('tactical_recommendation', '').strip()}"
    )


async def _run(user_id: str, note: str) -> str:
    # Scraping can block (cloud browser); keep it off the event loop.
    page_text, source = await asyncio.to_thread(tournaments.fetch_opponent_text, note)
    s = await claude.scout_opponent(note, page_text)
    # File the scouting report as a coaching entry the dashboard surfaces.
    report = (
        f"Scouting — {s.get('opponent', 'opponent')}: {s.get('patterns', '')} "
        f"Weakness to target: {s.get('weaknesses', '')} "
        f"Plan: {s.get('tactical_recommendation', '')}"
    )
    await backend.create_entry(user_id, "coaching", report, meta={"source": "scout"})
    await backend.create_agent_output(
        user_id, "Scout Agent", "coaching",
        summary=f"Opponent {s.get('opponent', '')}: {s.get('weaknesses', '')[:80]}",
        severity="info",
        recommended_action=s.get("tactical_recommendation", ""),
    )
    return _format(s, source)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Scout agent ready. Name an opponent or log a match and I'll "
            "research their game and hand you a tactical edge."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    summary = await _run(env["user_id"], env["text"])
    ctx.logger.info("Scout handled note for %s", env["user_id"])

    if env.get("kind") == "run" and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            env["user_id"], env["text"],
            kind="result", agent="scout", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[scout] address: {agent.address}")
    agent.run()
