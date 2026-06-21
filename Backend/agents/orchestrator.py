"""Orchestrator agent — the ASI:One entry point and conductor.

Multi-step planning + orchestration:
  1. Receive a raw dump.
  2. Delegate classification + filing to the Librarian (chat protocol).
  3. From the classified sections, trigger the relevant specialists
     (Recovery / Performance / Sponsorship / Logistics) via SECTION_AGENTS.
  4. Correlate their async replies and compose one consolidated answer in the
     same ASI:One session.

If no worker addresses are configured (first boot), it runs the whole loop
inline with the same Claude functions, so the demo is never broken.

Run:  python -m agents.orchestrator   (from Backend/)
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
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


# ── formatting ─────────────────────────────────────────────────────
def _format_filing(entries: list[dict]) -> str:
    if not entries:
        return "I couldn't find anything to file in that note."
    sections = sorted({e["section"] for e in entries})
    lines = [f"📓 Filed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:"]
    for e in entries:
        lines.append(f"  • [{e['section']}] {e['text']}")
    lines.append(f"Sections: {', '.join(sections)}.")
    return "\n".join(lines)


def _agent_texts(entries: list[dict]) -> dict[str, list[str]]:
    """Map each triggered specialist agent -> the entry texts relevant to it."""
    out: dict[str, list[str]] = {}
    for e in entries:
        for name in config.SECTION_AGENTS.get(e["section"], []):
            out.setdefault(name, []).append(e["text"])
    return out


# ── correlation state (agent storage, keyed by request id) ─────────
def _load(ctx: Context, req_id: str):
    return ctx.storage.get(req_id)


def _save(ctx: Context, req_id: str, state: dict):
    ctx.storage.set(req_id, state)


def _drop(ctx: Context, req_id: str):
    try:
        ctx.storage.remove(req_id)
    except Exception:  # noqa: BLE001
        ctx.storage.set(req_id, None)


# ── inline fallback specialists (used when addresses aren't set) ───
async def _inline_specialist(name: str, user_id: str, note: str) -> str:
    if name == "recovery":
        v = await claude.assess_recovery(
            note,
            await backend.recent_entries(user_id, limit=60),
            await backend.recent_recovery_logs(user_id),
            await backend.recent_training(user_id),
            await backend.recent_metrics(user_id),
        )
        await backend.create_agent_output(
            user_id, "Recovery Agent", "recovery",
            v.get("summary", ""), v.get("severity", "info"), v.get("recommended_action", ""),
        )
        parts = ", ".join(v.get("body_parts") or []) or "an area"
        out = f"⚠️ Recovery (risk {v.get('risk_level')}, {parts}): {v.get('summary', '')} 👉 {v.get('recommended_action', '')}"
        if v.get("pattern_type", "none") not in ("none", ""):
            out += f"\n🔎 Pattern — {v['pattern_type'].replace('_', ' ')}: {v.get('pattern_summary', '')}"
            if v.get("chain_message"):
                out += f"\n   ➡️ {v['chain_message']}"
        return out
    if name == "performance":
        v = await claude.analyze_performance(
            note,
            await backend.recent_match_results(user_id),
            await backend.recent_training(user_id),
            await backend.recent_metrics(user_id),
        )
        await backend.create_agent_output(
            user_id, "Performance Agent", "performance",
            v.get("summary", ""), "info", v.get("recommended_focus", ""),
        )
        return f"📈 Performance ({v.get('trend')}): {v.get('summary', '')} 👉 {v.get('recommended_focus', '')}"
    if name == "sponsorship":
        v = await claude.suggest_sponsorship(
            note,
            await backend.athlete_profile(user_id),
            await backend.recent_match_results(user_id),
            await backend.recent_metrics(user_id),
            await backend.recent_entries(user_id, "media_notes"),
        )
        await backend.create_sponsorship_opportunity(user_id, {
            "brand_name": v.get("brand_name", ""), "category": v.get("category", ""),
            "fit_score": v.get("fit_score", 0), "reason": v.get("reason", ""),
            "draft_email": v.get("draft_email", ""), "status": "drafted",
        })
        return f"🤝 Sponsor: {v.get('brand_name')} (fit {v.get('fit_score', 0):.2f}) — draft ready for review (not sent)."
    return ""


async def _run_inline(ctx: Context, user: str, user_id: str, dump: str):
    entries = await claude.classify(dump)
    for e in entries:
        await backend.create_entry(user_id, e["section"], e["text"], meta={})
    await ctx.send(user, make_chat(_format_filing(entries)))

    summaries: list[str] = []
    for name, texts in _agent_texts(entries).items():
        if name in ("logistics", "scout"):
            summaries.append(f"↪️ {name.title()}: needs the {name} agent running (start it to enable).")
            continue
        s = await _inline_specialist(name, user_id, " ".join(texts))
        if s:
            summaries.append(s)
    await ctx.send(user, make_chat("\n".join(summaries) or "Done.", end_session=True))


# ── chat protocol ──────────────────────────────────────────────────
@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "👋 I'm BASELINE — your sports analytics assistant. Two things you can do:\n"
            "• Log: brain-dump after practice/a match and I'll file it, track your "
            "form, watch for overtraining, and surface sponsor fits.\n"
            "• Ask: 'how's my serve trending?', 'am I overtrained?', 'find me a "
            "tournament' — I'll route it to the right place and answer."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    kind = env.get("kind")
    if kind == "classify_result":
        await _on_classify_result(ctx, env)
    elif kind == "result":
        await _on_result(ctx, env)
    elif sender in _specialist_addresses():
        # A plain (non-envelope) reply from a specialist we forwarded to (e.g. the
        # interactive Logistics agent). Don't reclassify it as a new user message.
        ctx.logger.debug("Ignoring stray reply from specialist %s", sender)
    else:
        await _on_user_message(ctx, sender, env)


def _specialist_addresses() -> set[str]:
    names = ("librarian", "recovery", "performance", "sponsorship", "logistics", "scout")
    addrs = {config.address_for(n) for n in names} | {config.LIBRARIAN_ADDRESS}
    return {a for a in addrs if a}


async def _on_user_message(ctx: Context, sender: str, env: dict):
    """ASI:One gateway: read intent, then log / answer / act (framework v4 §6a)."""
    user_id, message = env["user_id"], env["text"]
    intent = await claude.classify_intent(message)
    ctx.logger.info("Intent=%s agent=%s", intent.get("intent"), intent.get("agent"))

    if intent.get("intent") == "ask":
        await _handle_ask(ctx, sender, user_id, message)
    elif intent.get("intent") == "action" and intent.get("agent") not in (None, "none"):
        await _handle_action(ctx, sender, user_id, message, intent["agent"])
    else:  # "log" — file it through the Librarian
        await _on_new_dump(ctx, sender, env)


async def _handle_ask(ctx: Context, user: str, user_id: str, question: str):
    """History/pattern question → RAG over the backend's /chat, relay the answer."""
    res = await backend.chat(user_id, question)
    answer = (res or {}).get("answer")
    if not answer:
        await ctx.send(user, make_chat(
            "I couldn't reach the chat/RAG service to answer that yet.", end_session=True
        ))
        return
    n = len((res or {}).get("sources") or [])
    suffix = f"\n\n_(grounded in {n} of your journal entries)_" if n else ""
    await ctx.send(user, make_chat(answer + suffix, end_session=True))


async def _handle_action(ctx: Context, user: str, user_id: str, message: str, agent: str):
    """Domain request → the specialist that owns it."""
    addr = config.address_for(agent)
    if not addr:
        if agent in ("recovery", "performance", "sponsorship"):
            summary = await _inline_specialist(agent, user_id, message)
            await ctx.send(user, make_chat(summary or "Done.", end_session=True))
        else:  # logistics / scout need their agent running
            await ctx.send(user, make_chat(
                f"The {agent} agent isn't connected yet.", end_session=True
            ))
        return
    # Logistics is interactive (it runs its own multi-step flights/hotels/
    # tournament-pick conversation), so kick it off and point the athlete to it
    # rather than waiting for a single one-shot result.
    if agent == "logistics":
        await ctx.send(addr, make_chat(encode_envelope(user_id, message)))
        await ctx.send(user, make_chat(
            "🧳 I've handed that to the Logistics agent — it'll walk you through "
            "tournaments, flights, and hotels. Chat it directly to pick options.",
            end_session=True,
        ))
        return
    # one-shot worker (recovery / performance / sponsorship / scout): relay result
    req_id = uuid4().hex
    _save(ctx, req_id, {"user": user, "user_id": user_id, "pending": 1, "summaries": []})
    await ctx.send(addr, make_chat(
        encode_envelope(user_id, message, kind="run", agent=agent, req_id=req_id)
    ))


async def _on_new_dump(ctx: Context, sender: str, env: dict):
    user_id, dump = env["user_id"], env["text"]
    if not config.LIBRARIAN_ADDRESS:
        ctx.logger.info("No LIBRARIAN_ADDRESS; running inline workflow.")
        await _run_inline(ctx, sender, user_id, dump)
        return
    req_id = uuid4().hex
    _save(ctx, req_id, {"user": sender, "user_id": user_id, "pending": None, "summaries": []})
    await ctx.send(sender, make_chat("🧭 On it — classifying and filing your notes…"))
    await ctx.send(config.LIBRARIAN_ADDRESS, make_chat(
        encode_envelope(user_id, dump, kind="classify", req_id=req_id)
    ))


async def _on_classify_result(ctx: Context, env: dict):
    req_id = env.get("req_id")
    state = _load(ctx, req_id) if req_id else None
    if not state:
        return
    entries = env.get("entries", [])
    await ctx.send(state["user"], make_chat(_format_filing(entries)))

    triggered = _agent_texts(entries)
    sent = 0
    for name, texts in triggered.items():
        addr = config.address_for(name)
        if not addr:
            continue
        await ctx.send(addr, make_chat(encode_envelope(
            state["user_id"], " ".join(texts), kind="run", agent=name, req_id=req_id
        )))
        sent += 1

    if sent == 0:
        await ctx.send(state["user"], make_chat("Done — filed and routed.", end_session=True))
        _drop(ctx, req_id)
        return
    state["pending"] = sent
    _save(ctx, req_id, state)


async def _on_result(ctx: Context, env: dict):
    req_id = env.get("req_id")
    state = _load(ctx, req_id) if req_id else None
    if not state:
        return
    if env.get("summary"):
        state["summaries"].append(env["summary"])
    state["pending"] = (state.get("pending") or 1) - 1
    if state["pending"] <= 0:
        await ctx.send(state["user"], make_chat(
            "\n".join(state["summaries"]) or "Done.", end_session=True
        ))
        _drop(ctx, req_id)
    else:
        _save(ctx, req_id, state)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[orchestrator] address: {agent.address}")
    agent.run()
