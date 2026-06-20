"""textinput.py — forward a typed or piped note to the Librarian.

Sends raw text to the Librarian agent over the standard uAgents chat
protocol — same envelope/transport as phototext.py and voicetotext.py.
This is the fallback / demo input path when no mic or camera is available.

Usage (from Backend/):
    python -m agents.processing.textinput "Worked on serve today, knee sore."
    echo "notes..." | python -m agents.processing.textinput

Requires LIBRARIAN_ADDRESS to be set in .env (paste it in after the
Librarian has booted once and printed its own address).
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

from agents.common import config
from agents.common.chat import encode_envelope, make_ack, make_chat, text_of

if len(sys.argv) > 1:
    TEXT = " ".join(sys.argv[1:]).strip()
elif not sys.stdin.isatty():
    TEXT = sys.stdin.read().strip()
else:
    raise SystemExit(
        "Usage: python -m agents.processing.textinput <text>\n"
        "       echo '<text>' | python -m agents.processing.textinput"
    )

if not TEXT:
    raise SystemExit("No text provided.")

LIBRARIAN = config.LIBRARIAN_ADDRESS
USER_ID = config.DEFAULT_USER_ID

agent = Agent(name="textinput", seed="baseline-textinput-seed-v1", port=8012, mailbox=True)
proto = Protocol(spec=chat_protocol_spec)


@agent.on_event("startup")
async def kickoff(ctx: Context):
    print(f"[textinput] my address: {agent.address}")
    if not LIBRARIAN:
        ctx.logger.error(
            "LIBRARIAN_ADDRESS not set. Boot the Librarian once and paste its "
            "printed address into .env, then re-run this script."
        )
        return

    print(f"\n──── text to send ────\n{TEXT}\n")
    envelope = encode_envelope(USER_ID, TEXT)
    await ctx.send(LIBRARIAN, make_chat(envelope))
    ctx.logger.info("Sent to Librarian at %s", LIBRARIAN)


@proto.on_message(ChatMessage)
async def on_reply(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, make_ack(msg))
    body = text_of(msg)
    if body:
        print(f"\n──── librarian reply ────\n{body}\n")


@proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(proto)

if __name__ == "__main__":
    agent.run()
