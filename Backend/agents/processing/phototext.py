"""phototext.py — notebook photo → Claude vision → text.

Two surfaces:

1. **Importable API** (used by the backend Upload endpoints). Pure functions
   that take an image and return the extracted transcript — no agents, no
   network beyond the Claude vision call, no side effects on import:

       extract_text_from_image_bytes(data, media_type) -> str
       extract_text_from_image(path) -> str

2. **CLI** (unchanged behavior): one-shot OCR that forwards the transcript to
   the Librarian agent over the uAgents chat protocol — same envelope/transport
   as voicetotext.py and send_dump.py.

       python -m agents.processing.phototext path/to/notebook_page.jpg

   Requires ANTHROPIC_API_KEY and LIBRARIAN_ADDRESS in .env (boot the Librarian
   once first to get its printed address).

The heavy / agent-only imports (uagents, sys argv parsing) live inside the CLI
path so importing this module from the FastAPI backend stays cheap and only
needs `anthropic`.
"""

from __future__ import annotations

import base64
import mimetypes
import os

from agents.common import config

# One prompt, shared by the importable API and the CLI, so the OCR behaviour is
# identical however the function is reached.
_OCR_PROMPT = (
    "Transcribe all handwritten or printed text in this image exactly as "
    "written. Output only the transcription, no commentary, no markdown "
    "formatting."
)


def extract_text_from_image_bytes(data: bytes, media_type: str = "image/jpeg") -> str:
    """Send raw image bytes to Claude vision and return the transcription.

    Raises ValueError on empty input and RuntimeError if ANTHROPIC_API_KEY is
    missing — the caller (endpoint) turns these into JSON errors for the UI.
    """
    if not data:
        raise ValueError("Empty image payload.")

    api_key = config.require_anthropic_key()  # RuntimeError if missing — fail fast

    import anthropic  # lazy import keeps module import cheap + dependency-light

    client = anthropic.Anthropic(api_key=api_key)
    image_b64 = base64.standard_b64encode(data).decode("utf-8")
    response = client.messages.create(
        # The stronger model — OCR on messy handwriting benefits from it, and
        # this is a one-shot call, not a hot path.
        model=config.SYNTHESIS_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                },
                {"type": "text", "text": _OCR_PROMPT},
            ],
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def extract_text_from_image(image_path: str) -> str:
    """Read an image file from disk and return its transcription."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"No such file: {image_path}")
    media_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        return extract_text_from_image_bytes(f.read(), media_type)


def _run_cli() -> None:
    """One-shot CLI: OCR an image, forward it to the Librarian, print the reply.

    All uAgents wiring lives here so importing this module for the OCR helpers
    above never pulls in the agent stack.
    """
    import sys

    from uagents import Agent, Context, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        chat_protocol_spec,
    )

    from agents.common.chat import encode_envelope, make_ack, make_chat, text_of

    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not image_path:
        raise SystemExit("Usage: python -m agents.processing.phototext <image_path>")
    if not os.path.isfile(image_path):
        raise SystemExit(f"No such file: {image_path}")

    librarian = config.LIBRARIAN_ADDRESS
    user_id = config.DEFAULT_USER_ID

    agent = Agent(name="phototext", seed="baseline-phototext-seed-v1", port=8011, mailbox=True)
    proto = Protocol(spec=chat_protocol_spec)

    @agent.on_event("startup")
    async def kickoff(ctx: Context):
        print(f"[phototext] my address: {agent.address}")
        if not librarian:
            ctx.logger.error(
                "LIBRARIAN_ADDRESS not set. Boot the Librarian once and paste its "
                "printed address into .env, then re-run this script."
            )
            return

        ctx.logger.info("Extracting text from %s ...", image_path)
        transcript = extract_text_from_image(image_path)
        if not transcript:
            ctx.logger.warning("No text extracted from image — nothing to send.")
            return

        print(f"\n──── extracted text ────\n{transcript}\n")
        await ctx.send(librarian, make_chat(encode_envelope(user_id, transcript)))
        ctx.logger.info("Sent to Librarian at %s", librarian)

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
    agent.run()


if __name__ == "__main__":
    _run_cli()
