"""Test client — sends one brain-dump to a deployed agent and prints replies.

Use this against a mailbox/Agentverse-connected agent (the real submission
path). Point it at the Orchestrator's address.

Usage (from Backend/):
    ORCHESTRATOR_ADDRESS=agent1q... python send_dump.py
    python send_dump.py agent1q...            # address as first arg
    python send_dump.py agent1q... "custom dump text here"
"""

from __future__ import annotations

import os
import sys

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from agents.common.chat import make_ack, make_chat, text_of

TARGET = (
    (sys.argv[1] if len(sys.argv) > 1 else "")
    or os.environ.get("ORCHESTRATOR_ADDRESS", "")
).strip()

DUMP = (
    sys.argv[2]
    if len(sys.argv) > 2
    else (
        "Worked on my serve today, felt sharp and the toss was consistent. "
        "Right knee was sore again after the long session. "
        "Got a tournament in San Jose in two weeks I want to enter."
    )
)

client = Agent(name="baseline-test-user", seed="baseline-test-user-v1", port=8009, mailbox=True)
proto = Protocol(spec=chat_protocol_spec)


@client.on_event("startup")
async def kickoff(ctx: Context):
    print(f"[test-user] my address: {client.address}")
    if not TARGET:
        ctx.logger.error("No target address. Pass it as arg or ORCHESTRATOR_ADDRESS.")
        return
    ctx.logger.info("Sending dump to %s", TARGET)
    await ctx.send(TARGET, make_chat(DUMP))


@proto.on_message(ChatMessage)
async def on_reply(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    body = text_of(msg)
    if body:
        print(f"\n──── reply from {sender[:16]}… ────\n{body}\n")


@proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


client.include(proto)


if __name__ == "__main__":
    client.run()
