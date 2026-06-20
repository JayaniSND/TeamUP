"""Orchestrator agent — the front desk for the whole demo loop.

This is the agent a user talks to through ASI:One. It performs multi-step
planning and orchestration (a scored judging criterion):

  1. Receive a raw dump.
  2. Delegate classification + filing to the Librarian (chat protocol).
  3. Route the resulting injury notes to Recovery and tournament notes to
     Logistics (Dev 4), over the chat protocol.
  4. Correlate the workers' async replies and compose one consolidated
     answer back to the user — all inside the same ASI:One session.

If the worker addresses aren't configured yet (first boot), it falls back to
running the full loop inline using the same Claude functions, so the demo is
never broken by a missing address.

Run:  python -m agents.orchestrator   (from the Backend/ directory)
On boot it prints its address — this is the agent you register on
Agentverse and reach through ASI:One.
"""

from __future__ import annotations

from uuid import uuid4

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
    name="orchestrator",
    seed=config.ORCHESTRATOR_SEED,
    port=config.ORCHESTRATOR_PORT,
    mailbox=True,  # reachable through Agentverse / ASI:One
)

chat_proto = Protocol(spec=chat_protocol_spec)


# ── formatting helpers ─────────────────────────────────────────────
def _format_filing(entries: list[dict]) -> str:
    if not entries:
        return "I couldn't find anything to file in that note."
    sections = sorted({e["section"] for e in entries})
    lines = [f"📓 Filed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:"]
    for e in entries:
        lines.append(f"  • [{e['section']}] {e['text']}")
    lines.append(f"Sections: {', '.join(sections)}.")
    return "\n".join(lines)


def _format_verdict(v: dict) -> str:
    if not v.get("overtraining_risk"):
        return "✅ Recovery: no overtraining pattern in your recent history."
    parts = ", ".join(v.get("body_parts") or []) or "an area"
    return (
        f"⚠️ Recovery flag ({v.get('severity', 'unknown')}) — {parts}.\n"
        f"   {v.get('rationale', '').strip()}\n"
        f"   👉 {v.get('recommendation', '').strip()}"
    )


def _closing(verdicts: list[dict], logistics: list[dict]) -> str:
    lines: list[str] = []
    for v in verdicts:
        lines.append(_format_verdict(v))
    for e in logistics:
        lines.append(f"📅 Logistics: handed '{e['text']}' to the calendar agent.")
    if not lines:
        lines.append("Done — nothing needed the recovery or logistics agents.")
    return "\n".join(lines)


# ── correlation state (kept in agent storage, keyed by request id) ──
def _load(ctx: Context, req_id: str) -> dict | None:
    return ctx.storage.get(req_id)


def _save(ctx: Context, req_id: str, state: dict) -> None:
    ctx.storage.set(req_id, state)


def _drop(ctx: Context, req_id: str) -> None:
    try:
        ctx.storage.remove(req_id)
    except Exception:  # noqa: BLE001 - older storage impls
        ctx.storage.set(req_id, None)


# ── inline fallback (used when worker addresses aren't configured) ──
async def _run_inline(ctx: Context, user: str, user_id: str, dump: str):
    entries = await claude.classify(dump)
    for e in entries:
        await backend.create_entry(user_id, e["section"], e["text"], meta={})
    await ctx.send(user, make_chat(_format_filing(entries)))

    injuries = [e for e in entries if e["section"] in config.INJURY_SECTIONS]
    logistics = [e for e in entries if e["section"] in config.LOGISTICS_SECTIONS]

    verdicts: list[dict] = []
    for e in injuries:
        recent = await backend.recent_entries(user_id, "injury_log", limit=10)
        metrics = await backend.recent_metrics(user_id, limit=20)
        v = await claude.assess_overtraining(e["text"], recent, metrics)
        await backend.create_recovery_flag(user_id, v)
        verdicts.append(v)

    await ctx.send(user, make_chat(_closing(verdicts, logistics), end_session=True))


# ── chat protocol ──────────────────────────────────────────────────
@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))

    if is_start(msg):
        await ctx.send(
            sender,
            make_chat(
                "👋 I'm BASELINE — your self-organizing training journal.\n"
                "Brain-dump after practice or a match (voice transcript or "
                "text) and I'll file it, watch for overtraining, and line up "
                "your next tournament."
            ),
        )
        return

    raw = text_of(msg)
    if not raw.strip():
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    kind = env.get("kind")

    if kind == "classify_result":
        await _on_classify_result(ctx, env)
        return
    if kind == "assess_result":
        await _on_assess_result(ctx, env)
        return

    # Otherwise it's a fresh dump from a user.
    await _on_new_dump(ctx, sender, env)


async def _on_new_dump(ctx: Context, sender: str, env: dict):
    user_id = env["user_id"]
    dump = env["text"]

    # No workers wired yet → do the whole loop ourselves so the demo works.
    if not (config.LIBRARIAN_ADDRESS and config.RECOVERY_ADDRESS):
        ctx.logger.info("Worker addresses not set; running inline workflow.")
        await _run_inline(ctx, sender, user_id, dump)
        return

    req_id = uuid4().hex
    _save(
        ctx,
        req_id,
        {"user": sender, "user_id": user_id, "pending": None, "verdicts": []},
    )
    await ctx.send(sender, make_chat("🧭 On it — classifying and filing your notes…"))
    await ctx.send(
        config.LIBRARIAN_ADDRESS,
        make_chat(encode_envelope(user_id, dump, kind="classify", req_id=req_id)),
    )


async def _on_classify_result(ctx: Context, env: dict):
    req_id = env.get("req_id")
    state = _load(ctx, req_id) if req_id else None
    if not state:
        return

    entries = env.get("entries", [])
    await ctx.send(state["user"], make_chat(_format_filing(entries)))

    injuries = [e for e in entries if e["section"] in config.INJURY_SECTIONS]
    logistics = [e for e in entries if e["section"] in config.LOGISTICS_SECTIONS]
    state["logistics"] = logistics

    # Route tournament notes to Dev 4's Logistics agent (fire-and-forget).
    if config.LOGISTICS_ADDRESS:
        for e in logistics:
            await ctx.send(
                config.LOGISTICS_ADDRESS,
                make_chat(encode_envelope(state["user_id"], e["text"])),
            )

    if not injuries:
        await ctx.send(state["user"], make_chat(_closing([], logistics), end_session=True))
        _drop(ctx, req_id)
        return

    # Fan out injury notes to Recovery and wait for the verdicts.
    state["pending"] = len(injuries)
    _save(ctx, req_id, state)
    for e in injuries:
        await ctx.send(
            config.RECOVERY_ADDRESS,
            make_chat(
                encode_envelope(state["user_id"], e["text"], kind="assess", req_id=req_id)
            ),
        )


async def _on_assess_result(ctx: Context, env: dict):
    req_id = env.get("req_id")
    state = _load(ctx, req_id) if req_id else None
    if not state:
        return

    state["verdicts"].append(env.get("verdict", {}))
    state["pending"] = (state.get("pending") or 1) - 1

    if state["pending"] <= 0:
        await ctx.send(
            state["user"],
            make_chat(_closing(state["verdicts"], state.get("logistics", [])), end_session=True),
        )
        _drop(ctx, req_id)
    else:
        _save(ctx, req_id, state)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print(f"[orchestrator] address: {agent.address}")
    agent.run()
