"""Fitness agent — conversational training schedule builder with calendar integration.

INTERACTIVE (direct user message or chat):
  Stage 1 — ASKING: agent asks 3 questions in one message:
    • Which days are you free next week?
    • How long per session?
    • What's your focus? (recovery / performance / pre-competition / maintenance)
  Stage 2 — CONFIRMING: agent generates a 7-day plan and presents it.
    User says "yes" → sessions written to calendar_events → dashboard updates.
    User says anything else → treated as modification request, plan re-generated.
  State is stored in ctx.storage keyed by sender address so it survives
  between message turns.

PASSIVE (chained from Recovery or Coaching via kind="run"):
  Agent runs silently — reads history, generates a draft plan, writes it to
  agent_outputs so it surfaces on the dashboard as an insight card. Does NOT
  write to calendar (no user confirmation yet). Sends back a brief summary
  with an invitation to confirm in chat.

Speaks the Agent Chat Protocol — usable via ASI:One / Agentverse.
Run:  python -m agents.fitness   (from Backend/)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

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
    name="fitness",
    seed=config.FITNESS_SEED,
    port=config.FITNESS_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)

# ── Questions sent to user at stage 1 ─────────────────────────────

_QUESTIONS = """👟 I'm building your training schedule for next week.

Quick check — answer in one message and I'll draft your plan:

1️⃣ Which days work for you? (e.g. Mon, Wed, Fri, Sat)
2️⃣ How long per session? (30 / 45 / 60 / 90 min)
3️⃣ Main focus: recovery / performance / pre-competition / maintenance"""

_YES_WORDS = {"yes", "yep", "yeah", "ok", "okay", "sure", "confirm",
              "add it", "add them", "looks good", "perfect", "sounds good",
              "do it", "great", "approved", "go ahead"}


# ── Date helpers ──────────────────────────────────────────────────

_DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _next_date_for(day_name: str) -> date:
    """Return the soonest future date that falls on day_name."""
    target_wd = _DAY_MAP.get(day_name.lower().strip())
    if target_wd is None:
        return date.today() + timedelta(days=1)
    today = date.today()
    days_ahead = target_wd - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _session_times(day_name: str, duration_minutes: int) -> tuple[str, str]:
    """Return (start_time_iso, end_time_iso) at 9 AM for the given day."""
    d = _next_date_for(day_name)
    start = datetime(d.year, d.month, d.day, 9, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration_minutes)
    return start.isoformat(), end.isoformat()


# ── Formatting helpers ────────────────────────────────────────────

_INTENSITY_EMOJI = {"rest": "💤", "low": "🟢", "moderate": "🟡", "high": "🔴"}


def _format_plan_for_confirmation(plan: dict) -> str:
    """Render the plan as a readable proposal with a confirmation prompt."""
    lines = ["📅 Here's your plan for next week:\n"]
    for day in plan.get("adjusted_plan", []):
        emoji = _INTENSITY_EMOJI.get(day.get("intensity", "moderate"), "⚪")
        dur = day.get("session_length_minutes", 60)
        d = _next_date_for(day["day"])
        date_str = d.strftime("%a %b %-d")
        if day.get("intensity") == "rest":
            lines.append(f"  {date_str} — 💤 Rest / recovery")
        else:
            lines.append(
                f"  {date_str} — {day['session_type']} "
                f"({emoji} {day['intensity']}, {dur} min)"
            )
        if day.get("focus"):
            lines.append(f"     Focus: {day['focus']}")
        if day.get("modification_reason"):
            lines.append(f"     ↳ {day['modification_reason']}")

    avoided = plan.get("avoided_areas", [])
    if avoided:
        lines.append(f"\n🚫 Avoiding load on: {', '.join(avoided)}")
    if plan.get("recommended_action"):
        lines.append(f"\n💡 {plan['recommended_action']}")

    lines.append(
        "\nReply **yes** to add these to your calendar, "
        "or tell me what you'd like to change."
    )
    return "\n".join(lines)


def _format_passive_summary(plan: dict) -> str:
    """Short summary for background (passive) chain results."""
    days = [d["day"] for d in plan.get("adjusted_plan", [])
            if d.get("intensity") != "rest"]
    avoided = plan.get("avoided_areas", [])
    lines = [f"🏋️ Fitness draft ready — {len(days)} active sessions planned."]
    if avoided:
        lines.append(f"🚫 Avoiding: {', '.join(avoided)}")
    if plan.get("summary"):
        lines.append(f"   {plan['summary']}")
    lines.append(
        "\n💬 Chat with me directly to review the schedule and add it to your calendar."
    )
    return "\n".join(lines)


# ── Core plan generation ──────────────────────────────────────────

async def _generate_plan(user_id: str, note: str, recovery_ctx: dict | None) -> dict:
    """Call the backend + Claude to produce a structured 7-day plan."""
    training = await backend.recent_training(user_id, limit=14)
    recovery_logs = await backend.recent_recovery_logs(user_id, limit=14)
    entries = await backend.recent_entries(user_id, limit=20)
    return await claude.suggest_fitness_plan(
        note, training, recovery_logs, entries, recovery_ctx
    )


# ── Calendar write ────────────────────────────────────────────────

async def _add_plan_to_calendar(user_id: str, plan: dict) -> int:
    """Write each active session in the plan to calendar_events. Returns count."""
    added = 0
    for day in plan.get("adjusted_plan", []):
        if day.get("intensity") == "rest":
            continue
        start, end = _session_times(day["day"], day.get("session_length_minutes", 60))
        await backend.create_calendar_event(user_id, {
            "title": f"Training: {day['session_type']}",
            "event_type": "training",
            "start_time": start,
            "end_time": end,
            "location": "",
            "source": "fitness_agent",
            "metadata": {
                "focus": day.get("focus", ""),
                "intensity": day.get("intensity", ""),
                "modification_reason": day.get("modification_reason", ""),
            },
        })
        added += 1
    return added


# ── Message handler — state machine ──────────────────────────────

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))

    raw = text_of(msg)
    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    passive = env.get("kind") == "run"
    source = env.get("source", "")

    # ── PASSIVE (chained from Recovery / Coaching) ─────────────────
    # Run silently, write a draft to agent_outputs, invite user to confirm.
    if passive:
        recovery_ctx: dict | None = None
        if source == "recovery":
            recovery_ctx = {"chained_from": "recovery", "recovery_note": env["text"]}
        elif source == "coaching":
            recovery_ctx = {
                "chained_from": "coaching",
                "coaching_note": env["text"],
                "fitness_focus": env.get("fitness_focus", ""),
            }
        ctx.logger.info("Fitness passive run (source=%s) for %s", source, user_id)

        plan = await _generate_plan(user_id, env["text"], recovery_ctx)
        await backend.create_agent_output(
            user_id,
            agent_name="Fitness Agent",
            section="training",
            summary=plan.get("summary", ""),
            severity="medium" if plan.get("trigger") in ("injury_flag", "fatigue_flag") else "info",
            recommended_action=plan.get("recommended_action", ""),
        )
        summary = _format_passive_summary(plan)
        ctx.logger.info(
            "Fitness draft written (trigger=%s, days=%d)",
            plan.get("trigger"), len(plan.get("adjusted_plan", [])),
        )

        if env.get("req_id"):
            await ctx.send(sender, make_chat(encode_envelope(
                user_id, env["text"],
                kind="result", agent="fitness", req_id=env["req_id"], summary=summary,
            )))
        else:
            await ctx.send(sender, make_chat(summary))
        return

    # ── INTERACTIVE (direct user / chat session) ───────────────────
    # Load conversation state for this sender.
    state: dict = ctx.storage.get(sender) or {}
    stage = state.get("stage")

    # Session start — reset and ask questions.
    if is_start(msg) or not stage:
        # Carry over any injury/coaching context from the envelope (e.g.
        # the user opened a chat after seeing a Recovery alert).
        new_state: dict = {
            "stage": "asking",
            "user_id": user_id,
            "context_note": env.get("text", ""),
            "source": source,
        }
        if source == "recovery":
            new_state["recovery_ctx"] = {"chained_from": "recovery", "recovery_note": env.get("text", "")}
        elif source == "coaching":
            new_state["recovery_ctx"] = {
                "chained_from": "coaching",
                "fitness_focus": env.get("fitness_focus", ""),
            }
        ctx.storage.set(sender, new_state)
        await ctx.send(sender, make_chat(_QUESTIONS))
        return

    # ── Stage: ASKING — user just answered the 3 questions ─────────
    if stage == "asking":
        if not raw.strip():
            await ctx.send(sender, make_chat("No problem — whenever you're ready, just answer those three questions."))
            return

        # Build the full context note: original trigger + user's answers.
        context_note = state.get("context_note", "") + f"\nUser preferences: {raw}"
        recovery_ctx = state.get("recovery_ctx")

        ctx.logger.info("Fitness generating plan from answers for %s", user_id)
        plan = await _generate_plan(user_id, context_note, recovery_ctx)

        # Save plan and advance stage.
        state["stage"] = "confirming"
        state["plan"] = plan
        state["context_note"] = context_note
        ctx.storage.set(sender, state)

        proposal = _format_plan_for_confirmation(plan)
        await ctx.send(sender, make_chat(proposal))
        return

    # ── Stage: CONFIRMING — user either confirms or requests changes ─
    if stage == "confirming":
        lowered = raw.lower().strip()
        confirmed = any(w in lowered for w in _YES_WORDS)

        if confirmed:
            plan = state.get("plan", {})
            added = await _add_plan_to_calendar(user_id, plan)
            ctx.storage.set(sender, {})  # clear state

            ctx.logger.info("Fitness added %d sessions to calendar for %s", added, user_id)
            await ctx.send(sender, make_chat(
                f"✅ Done! Added {added} training session{'s' if added != 1 else ''} "
                f"to your calendar. You'll see them in the Schedule section of the dashboard.\n\n"
                f"Come back after training and I'll adjust next week's plan based on how it went.",
                end_session=True,
            ))
        else:
            # Treat the message as a modification request — re-generate with it.
            ctx.logger.info("Fitness re-generating plan with modifications for %s", user_id)
            modified_note = state.get("context_note", "") + f"\nModification request: {raw}"
            recovery_ctx = state.get("recovery_ctx")

            plan = await _generate_plan(user_id, modified_note, recovery_ctx)
            state["plan"] = plan
            state["context_note"] = modified_note
            ctx.storage.set(sender, state)

            proposal = _format_plan_for_confirmation(plan)
            await ctx.send(sender, make_chat(
                f"Got it — here's the updated plan:\n\n{proposal}"
            ))
        return

    # Fallback: unknown stage, reset.
    ctx.storage.set(sender, {})
    await ctx.send(sender, make_chat(_QUESTIONS))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[fitness] address: {agent.address}")
    agent.run()
