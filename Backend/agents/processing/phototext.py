"""phototext.py — notebook photo → Claude vision → Librarian.

Extracts text from a photo of a handwritten/printed page using Claude's
vision API, then forwards the transcript to the Librarian agent over the
standard uAgents chat protocol — same envelope/transport as
voicetotext.py and send_dump.py.

This is a one-shot script (do the OCR, send it, print the reply, done),
not a long-running listener — mirrors send_dump.py's pattern rather than
voicetotext.py's background-thread pattern, since there's no streaming
involved.

Usage (from Backend/):
    python -m agents.processing.phototext path/to/notebook_page.jpg

Requires ANTHROPIC_API_KEY and LIBRARIAN_ADDRESS to be set in .env
(boot the Librarian once first to get its printed address).
"""

from __future__ import annotations

import base64
import mimetypes
import os
import sys

import anthropic
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from agents.common import config
from agents.common.chat import encode_envelope, make_ack, make_chat, text_of

IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
if not IMAGE_PATH:
    raise SystemExit("Usage: python -m agents.processing.phototext <image_path>")
if not os.path.isfile(IMAGE_PATH):
    raise SystemExit(f"No such file: {IMAGE_PATH}")

LIBRARIAN = config.LIBRARIAN_ADDRESS
USER_ID = config.DEFAULT_USER_ID

anthropic_client = anthropic.Anthropic(api_key=config.require_anthropic_key())

agent = Agent(name="phototext", seed="baseline-phototext-seed-v1", port=8011, mailbox=True)
proto = Protocol(spec=chat_protocol_spec)


def extract_text_from_image(image_path: str) -> str:
    """Send the image to Claude vision and return the raw transcription."""
    media_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = anthropic_client.messages.create(
        # Use the stronger model here — this is a one-shot call, not a hot
        # path, and OCR on messy handwriting benefits from the better model.
        model=config.SYNTHESIS_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_data},
                },
                {
                    "type": "text",
                    "text": (
                        "Transcribe all handwritten or printed text in this image "
                        "exactly as written. Output only the transcription, no "
                        "commentary, no markdown formatting."
                    ),
                },
            ],
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


@agent.on_event("startup")
async def kickoff(ctx: Context):
    print(f"[phototext] my address: {agent.address}")
    if not LIBRARIAN:
        ctx.logger.error(
            "LIBRARIAN_ADDRESS not set. Boot the Librarian once and paste its "
            "printed address into .env, then re-run this script."
        )
        return

    ctx.logger.info("Extracting text from %s ...", IMAGE_PATH)
    transcript = extract_text_from_image(IMAGE_PATH)
    if not transcript:
        ctx.logger.warning("No text extracted from image — nothing to send.")
        return

    print(f"\n──── extracted text ────\n{transcript}\n")
    envelope = encode_envelope(USER_ID, transcript)
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