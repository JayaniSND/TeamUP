"""One-command OFFLINE end-to-end test of the whole agent loop.

Runs the Orchestrator, Librarian, Recovery, and a test-user agent together in
a single process via a uAgents Bureau, so messages route locally without
needing Agentverse. This is the fastest way to see the full multi-agent loop
work on your machine before you wire up mailboxes.

Prereqs:
    1. ANTHROPIC_API_KEY set (see .env).
    2. Backend running:  uvicorn main:app --port 8000   (separate terminal)
       (or `uvicorn mock_backend:app` for an offline, no-Supabase fallback —
        but that one lacks the /orchestrator/chat + /bookings routes)

Run (from Backend/):
    python run_local.py
"""

from __future__ import annotations

import os

from uagents import Agent, Bureau, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from agents import (
    librarian, orchestrator, performance, recovery, scout, sponsorship,
)
from agents.common import config
from agents.common.chat import make_ack, make_chat, text_of

# Wire the orchestrator to the real worker addresses for this process.
config.LIBRARIAN_ADDRESS = librarian.agent.address
config.RECOVERY_ADDRESS = recovery.agent.address
config.PERFORMANCE_ADDRESS = performance.agent.address
config.SPONSORSHIP_ADDRESS = sponsorship.agent.address
config.SCOUT_ADDRESS = scout.agent.address

# Logistics is the teammate's interactive agent and pulls heavier deps
# (stagehand, google libs). Import it best-effort so the offline loop still
# runs without those installed — it just won't be in the local bureau.
try:
    from agents import logistics
    config.LOGISTICS_ADDRESS = logistics.agent.address
except Exception as e:  # noqa: BLE001
    logistics = None
    print(f"[run_local] Logistics agent not loaded ({e}); continuing without it.")

DUMP = (
    "Worked on my serve today, felt sharp and the toss was consistent. "
    "Won my match 6-3, 6-4 against Rivera. "
    "Right knee was sore again after the long session. "
    "Got a tournament in San Jose in two weeks I want to enter."
)

user = Agent(name="local-user", seed="baseline-local-user-v1", port=8010)
user_proto = Protocol(spec=chat_protocol_spec)


@user.on_event("startup")
async def kickoff(ctx: Context):
    ctx.logger.info("Sending demo dump to orchestrator…")
    await ctx.send(orchestrator.agent.address, make_chat(DUMP))


@user_proto.on_message(ChatMessage)
async def on_reply(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    body = text_of(msg)
    if body:
        print(f"\n──── reply ────\n{body}\n")


@user_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


user.include(user_proto)


if __name__ == "__main__":
    print("Orchestrator:", orchestrator.agent.address)
    print("Librarian:   ", librarian.agent.address)
    print("Recovery:    ", recovery.agent.address)
    print("Performance: ", performance.agent.address)
    print("Sponsorship: ", sponsorship.agent.address)
    print("Scout:       ", scout.agent.address)
    if logistics is not None:
        print("Logistics:   ", logistics.agent.address)
    # Keep the Bureau OFF port 8000 — that's where the backend (mock_backend /
    # the real API) lives, and a collision makes the agents' data calls 404.
    bureau = Bureau(port=int(os.environ.get("BUREAU_PORT", "8800")))
    bureau.add(orchestrator.agent)
    bureau.add(librarian.agent)
    bureau.add(recovery.agent)
    bureau.add(performance.agent)
    bureau.add(sponsorship.agent)
    bureau.add(scout.agent)
    if logistics is not None:
        bureau.add(logistics.agent)
    bureau.add(user)
    bureau.run()
