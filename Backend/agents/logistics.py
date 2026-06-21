"""Logistics agent — finds the next tournament and puts it on the calendar.

On a logistics/tournament note: searches a tournament finder (Browserbase, with
a cached fallback so the demo never depends on a live scrape), uses Claude to
extract the best-matching event, adds it to the calendar (dashboard + optional
Google Calendar), writes a dashboard insight, and replies.

Speaks the Agent Chat Protocol (usable via ASI:One/Agentverse and callable by
the Orchestrator).

Run:  python -m agents.logistics   (from Backend/)
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
from .integrations import calendar as cal
from .integrations import tournaments

agent = Agent(
    name="logistics",
    seed=config.LOGISTICS_SEED,
    port=config.LOGISTICS_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def _format(t: dict, source: str, synced: bool, link: str) -> str:
    if not t.get("name"):
        return f"📅 Logistics: {t.get('summary') or 'no matching tournament found.'}"
    when = " ".join(x for x in (t.get("start_date"), t.get("end_date")) if x).strip()
    where = t.get("venue") or t.get("location") or ""
    cal_note = "added to your Google Calendar" if synced else "added to your schedule"
    out = (
        f"📅 Logistics: **{t['name']}** ({source} result).\n"
        f"   {when} · {where}\n"
        f"   ✅ {cal_note}."
    )
    if synced and link:
        out += f"\n   {link}"
    elif t.get("url"):
        out += f"\n   {t['url']}"
    return out


async def _run(user_id: str, note: str) -> str:
    # Scraping can block (cloud browser); keep it off the event loop.
    page_text, source = await asyncio.to_thread(tournaments.fetch_tournament_text, note)
    t = await claude.extract_tournament(note, page_text)
    synced, link = False, ""
    if t.get("name"):
        ev = await cal.add_event(
            user_id, title=t["name"],
            start=t.get("start_date", ""), end=t.get("end_date", ""),
            location=t.get("venue") or t.get("location", ""),
        )
        synced = ev.get("synced_to_google", False)
        link = ev.get("google_link", "")
        await backend.create_agent_output(
            user_id, "Logistics Agent", "logistics",
            summary=f"{t['name']} — {t.get('start_date', '')} {t.get('venue', '')}".strip(),
            severity="info",
            recommended_action="Confirm entry and travel before the deadline.",
        )
    return _format(t, source, synced, link)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 Logistics agent ready. Mention a tournament, travel, or schedule "
            "and I'll find the event and add it to your calendar."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    summary = await _run(env["user_id"], env["text"])
    ctx.logger.info("Logistics handled note for %s", env["user_id"])

    if env.get("kind") == "run" and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            env["user_id"], env["text"],
            kind="result", agent="logistics", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[logistics] address: {agent.address}")
    agent.run()
