"""Librarian (Parser) agent — classifies raw input and files it.

Takes an athlete's raw input (voice transcript / text / transcribed notebook
page), uses Claude to split it into sectioned entries, and writes each to the
backend (the dashboard's source of truth).

Speaks the Agent Chat Protocol.
  • Human (plain text via ASI:One) → classify, file, autonomously notify the
    relevant specialist agents (per SECTION_AGENTS), reply with a summary.
  • Orchestrator (envelope kind="classify") → reply the entries so the
    conductor can route and compose one answer.

Run:  python -m agents.librarian   (from Backend/)
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
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format_summary(entries: list[dict]) -> str:
    if not entries:
        return "I couldn't find anything to file in that note."
    sections = sorted({e["section"] for e in entries})
    lines = [f"📓 Filed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:"]
    for e in entries:
        lines.append(f"  • [{e['section']}] {e['text']}")
    lines.append(f"Sections: {', '.join(sections)}.")
    return "\n".join(lines)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Librarian ready. Dump your practice/match notes and I'll split them "
            "into the right dashboard sections."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    dump = env["text"]

    entries = await claude.classify(dump)
    for e in entries:
        await backend.create_entry(user_id, e["section"], e["text"], meta={})
    ctx.logger.info("Filed %d entries for %s", len(entries), user_id)

    if env.get("kind") == "classify" and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            user_id, dump, kind="classify_result", req_id=env["req_id"], entries=entries,
        )))
        return

    # Standalone human use: notify each relevant specialist once.
    to_notify: dict[str, list[str]] = {}
    for e in entries:
        for name in config.SECTION_AGENTS.get(e["section"], []):
            to_notify.setdefault(name, []).append(e["text"])
    for name, texts in to_notify.items():
        addr = config.address_for(name)
        if addr:
            await ctx.send(addr, make_chat(encode_envelope(user_id, " ".join(texts))))

    await ctx.send(sender, make_chat(_format_summary(entries), end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[librarian] address: {agent.address}")
    agent.run()
