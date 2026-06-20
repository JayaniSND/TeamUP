"""voicetotext.py — live mic transcription, forwarded to the Librarian.

Streams microphone audio to Deepgram (nova-3) and, for each finalized
transcript, sends it to the Librarian agent over the standard uAgents
chat protocol — same envelope/transport that send_dump.py uses.

Run (from Backend/): python -m agents.processing.voicetotext
Requires LIBRARIAN_ADDRESS to be set in .env (paste it in after the
Librarian has booted once and printed its own address).
"""

from __future__ import annotations

import asyncio
import os
import queue
import threading

import sounddevice as sd
from dotenv import load_dotenv
from deepgram import DeepgramClient
from deepgram.core.events import EventType

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from agents.common.chat import encode_envelope, make_ack, make_chat, text_of
from agents.common import config

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    raise RuntimeError("Set DEEPGRAM_API_KEY in your .env file")

SAMPLE_RATE = 16000  # Hz, matches what we tell Deepgram below
CHANNELS = 1
BLOCKSIZE = 1024  # frames per mic callback

LIBRARIAN = config.LIBRARIAN_ADDRESS
USER_ID = config.DEFAULT_USER_ID

dg_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
audio_queue: "queue.Queue[bytes]" = queue.Queue()

agent = Agent(name="voicetotext", seed="baseline-voicetotext-seed-v1", port=8010, mailbox=True)
proto = Protocol(spec=chat_protocol_spec)

# Set once on startup, inside the agent's running event loop. The Deepgram
# callback fires on its own thread, so it can't call ctx.send directly —
# it schedules the send onto this loop instead.
main_loop: asyncio.AbstractEventLoop | None = None


def mic_callback(indata, frames, time_info, status):
    if status:
        print(f"[mic] {status}")
    audio_queue.put(bytes(indata))


def run_transcription(ctx: Context):
    """Background-thread worker: connects to Deepgram, streams mic audio,
    and forwards each final transcript to the Librarian."""
    with dg_client.listen.v1.connect(
        model="nova-3",
        language="en",
        encoding="linear16",  # raw PCM has no header, so we declare the format
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    ) as connection:
        ready = threading.Event()

        def on_message(result):
            if result.type != "Results" or not result.is_final:
                return
            transcript = result.channel.alternatives[0].transcript
            if not transcript:
                return
            if LIBRARIAN and main_loop:
                envelope = encode_envelope(USER_ID, transcript)
                asyncio.run_coroutine_threadsafe(
                    ctx.send(LIBRARIAN, make_chat(envelope)), main_loop
                )
                print(f"[FINAL → librarian] {transcript}")
            else:
                print(f"[FINAL] {transcript}  (LIBRARIAN_ADDRESS not set — not forwarded)")

        connection.on(EventType.OPEN, lambda _: ready.set())
        connection.on(EventType.MESSAGE, on_message)

        def stream_mic():
            ready.wait()
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype="int16",
                callback=mic_callback,
            ):
                while True:
                    chunk = audio_queue.get()
                    connection.send_media(chunk)

        threading.Thread(target=stream_mic, daemon=True).start()
        print("Listening on your microphone — speak now (Ctrl+C to stop)...")
        connection.start_listening()


@agent.on_event("startup")
async def start(ctx: Context):
    global main_loop
    main_loop = asyncio.get_running_loop()
    print(f"[voicetotext] my address: {agent.address}")
    if not LIBRARIAN:
        ctx.logger.warning(
            "LIBRARIAN_ADDRESS not set — transcripts will print but won't be filed."
        )
    threading.Thread(target=run_transcription, args=(ctx,), daemon=True).start()


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