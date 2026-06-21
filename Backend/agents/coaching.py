"""Coaching agent — tactical and technique advice, chains to Fitness.

Three ways this agent gets triggered:

  1. Recovery → Coaching (injury_accommodation): Recovery detected medium/high
     injury risk and fires Coaching so the athlete gets strategy adjustments
     that protect the flagged area. E.g. shoulder flagged → coach advises
     reducing serve pace, using slice returns instead of full swings.

  2. Scout → Coaching (weakness_exploitation): Scout found that an opponent
     consistently targets a specific weakness (e.g. backhand). Coaching
     advises the tactical response and technique cues for the next match.

  3. Performance → Coaching (performance_gap): Performance sees a consistent
     underperforming area across multiple matches. Coaching prescribes
     targeted technique changes and drills.

After generating advice, Coaching chains to Fitness when the recommendation
has a physical/conditioning component (e.g. "backhand needs more hip drive"
→ Fitness builds hip rotation + core exercises).

Speaks the Agent Chat Protocol — usable via ASI:One/Agentverse directly.
Run:  python -m agents.coaching   (from Backend/)
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
    name="coaching",
    seed=config.COACHING_SEED,
    port=config.COACHING_PORT,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)

# Maps source tag → context_type passed to Claude
_SOURCE_TO_CONTEXT = {
    "recovery": "injury_accommodation",
    "scout":    "weakness_exploitation",
    "performance": "performance_gap",
}


def _format(v: dict) -> str:
    trigger_labels = {
        "injury_accommodation":  "🩹 Coaching — injury accommodation",
        "weakness_exploitation": "🎯 Coaching — counter opponent exploitation",
        "performance_gap":       "📉 Coaching — closing the performance gap",
    }
    label = trigger_labels.get(v.get("trigger", ""), "🧑‍🏫 Coaching advice")
    lines = [label + "\n"]
    if v.get("summary"):
        lines.append(f"   {v['summary'].strip()}")
    if v.get("tactical_advice"):
        lines.append(f"\n📋 Tactical: {v['tactical_advice'].strip()}")
    if v.get("technique_focus"):
        lines.append(f"🎾 Technique: {v['technique_focus'].strip()}")
    if v.get("fitness_focus"):
        lines.append(f"💪 Physical gap → Fitness agent: {v['fitness_focus'].strip()}")
    if v.get("recommended_action"):
        lines.append(f"\n👉 {v['recommended_action'].strip()}")
    return "\n".join(lines)


async def _advise(user_id: str, note: str, source: str, recovery_verdict: dict | None = None) -> dict:
    context_type = _SOURCE_TO_CONTEXT.get(source, "performance_gap")
    entries = await backend.recent_entries(user_id, section="coaching", limit=10)
    matches = await backend.recent_match_results(user_id, limit=10)

    verdict = await claude.coach_strategy(
        context_type, note, entries, matches, recovery_verdict
    )

    await backend.create_agent_output(
        user_id,
        agent_name="Coaching Agent",
        section="coaching",
        summary=verdict.get("summary", ""),
        severity="medium" if context_type == "injury_accommodation" else "info",
        recommended_action=verdict.get("recommended_action", ""),
    )
    return verdict


async def _chain_to_fitness(ctx: Context, user_id: str, note: str, verdict: dict):
    """If Coaching identified a physical gap, fire Fitness to build exercises."""
    fitness_focus = verdict.get("fitness_focus", "").strip()
    if not fitness_focus:
        return

    fitness_addr = config.address_for("fitness")
    if not fitness_addr:
        ctx.logger.info("Coaching→Fitness chain skipped (FITNESS_ADDRESS unset)")
        return

    chain_note = (
        f"[Coaching→Fitness chain] technique weakness identified: {fitness_focus}. "
        f"Original context: {note[:200]}. "
        f"Build targeted conditioning exercises for: {fitness_focus}."
    )
    await ctx.send(fitness_addr, make_chat(
        encode_envelope(user_id, chain_note, kind="run", source="coaching",
                        fitness_focus=fitness_focus)
    ))
    ctx.logger.info(
        "Coaching chained → Fitness (focus=%s)", fitness_focus[:60]
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    if is_start(msg):
        await ctx.send(sender, make_chat(
            "🧑‍🏫 Coaching agent ready. Describe a match situation, a weakness you "
            "want to work on, or ask for strategy advice and I'll tailor a plan."
        ))
        return

    raw = text_of(msg)
    if not raw.strip():
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    user_id = env["user_id"]
    passive = env.get("kind") == "run"
    source = env.get("source", "performance")

    # Recovery passes its full verdict dict for richer injury-accommodation advice.
    recovery_verdict = env.get("recovery_verdict") or None

    ctx.logger.info(
        "Coaching triggered by source=%s for %s", source, user_id
    )

    verdict = await _advise(user_id, env["text"], source, recovery_verdict)
    summary = _format(verdict)

    # Chain to Fitness if a physical conditioning gap was identified.
    await _chain_to_fitness(ctx, user_id, env["text"], verdict)

    if passive and env.get("req_id"):
        await ctx.send(sender, make_chat(encode_envelope(
            user_id, env["text"],
            kind="result", agent="coaching", req_id=env["req_id"], summary=summary,
        )))
    else:
        await ctx.send(sender, make_chat(summary, end_session=True))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[coaching] address: {agent.address}")
    agent.run()
