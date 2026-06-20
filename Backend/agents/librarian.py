"""Librarian agent — classifies a raw dump and files it into sections.

Job: take an athlete's raw brain-dump (voice transcript / text / transcribed
notebook page), call Claude to split it into sectioned entries, and write
each one to Dev 2's backend.

Speaks the standardized Agent Chat Protocol, so it is usable directly through
ASI:One/Agentverse and callable by the Orchestrator.

  • Human (plain text via ASI:One) → classify, file, autonomously forward
    injury notes to Recovery and tournament notes to Logistics, then reply
    with a readable summary.
  • Orchestrator (envelope with kind="classify") → reply a structured
    envelope (kind="classify_result") with the entries so the conductor can
    route and compose one answer.

Run:  python -m agents.librarian   (from the Backend/ directory)
On boot it prints its address — paste that into .env as LIBRARIAN_ADDRESS.
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
    name="librarian",
    seed=config.LIBRARIAN_SEED,
    port=config.LIBRARIAN_PORT,
    mailbox=True,  # reachable through Agentverse
)

chat_proto = Protocol(spec=chat_protocol_spec)


def _format_summary(entries: list[dict]) -> str:
    if not entries:
        return "I couldn't find anything to file in that note."
    sections = sorted({e["section"] for e in entries})
    lines = [f"📓 Filed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:"]
    for e in entries:
        lines.append(f"  • [{e['section']}] {e['text']}")
    lines.append(f"Sections touched: {', '.join(sections)}.")
    return "\n".join(lines)


async def _forward(ctx: Context, address: str, user_id: str, text: str):
    """Fire-and-forget hand-off to a specialist agent over the chat protocol."""
    if not address:
        return
    await ctx.send(address, make_chat(encode_envelope(user_id, text)))


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))

    if is_start(msg):
        await ctx.send(
            sender,
            make_chat(
                "👋 Librarian ready. Dump your practice/match notes and I'll "
                "split them into the right sections of your journal."
            ),
        )
        return

    raw = text_of(msg)
    if not raw.strip():
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    dump = env["text"]

    entries = await claude.classify(dump)

    # Write every entry to the backend (the journal's source of truth).
    for e in entries:
        await backend.create_entry(user_id, e["section"], e["text"], meta={})

    ctx.logger.info("Filed %d entries for %s", len(entries), user_id)

    if env.get("kind") == "classify" and env.get("req_id"):
        # Called by the Orchestrator: return entries for it to route.
        await ctx.send(
            sender,
            make_chat(
                encode_envelope(
                    user_id,
                    dump,
                    kind="classify_result",
                    req_id=env["req_id"],
                    entries=entries,
                )
            ),
        )
        return

    # Direct human use: act autonomously — forward to the specialists itself.
    for e in entries:
        if e["section"] in config.INJURY_SECTIONS:
            await _forward(ctx, config.RECOVERY_ADDRESS, user_id, e["text"])
        elif e["section"] in config.LOGISTICS_SECTIONS:
            await _forward(ctx, config.LOGISTICS_ADDRESS, user_id, e["text"])

    await ctx.send(sender, make_chat(_format_summary(entries), end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print(f"[librarian] address: {agent.address}")
    agent.run()
