"""voicetotext.py — speech → text via Deepgram.

Two surfaces:

1. **Importable API** (used by the backend Upload endpoint). A pure function
   that transcribes a *complete* audio file/blob with Deepgram's pre-recorded
   API and returns the text — no mic, no agents, no side effects on import:

       transcribe_audio_bytes(data, mimetype) -> str

   This is what the web Upload page hits: the browser records or uploads an
   audio file, the backend forwards the bytes here, the text comes back as JSON.

2. **CLI** (unchanged behavior): live microphone transcription that streams to
   Deepgram (nova-3) and forwards each finalized transcript to the Librarian
   agent over the uAgents chat protocol.

       python -m agents.processing.voicetotext

   Requires DEEPGRAM_API_KEY, and LIBRARIAN_ADDRESS in .env to forward.

The mic/streaming/agent stack (sounddevice, uagents) is imported only inside
the CLI path, so importing this module from the FastAPI backend stays cheap and
only needs `deepgram`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from agents.common import config

load_dotenv()

# Same model the live CLI path uses, so file and stream transcription match.
MODEL = "nova-3"
LANGUAGE = "en"


def _transcript_from_response(resp) -> str:
    """Pull the transcript out of a Deepgram response across SDK shapes.

    Deepgram's pre-recorded response can come back as a typed object or a dict
    depending on the installed SDK major version, so normalise to a dict first
    and fall back to attribute access.
    """
    payload = resp
    for attr in ("to_dict", "model_dump", "dict"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                payload = fn()
                break
            except Exception:
                pass
    if isinstance(payload, dict):
        try:
            return (payload["results"]["channels"][0]["alternatives"][0]["transcript"] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""
    try:
        return (resp.results.channels[0].alternatives[0].transcript or "").strip()
    except Exception:
        return ""


def transcribe_audio_bytes(data: bytes, mimetype: str | None = None) -> str:
    """Transcribe a complete audio file/blob and return the text.

    Raises ValueError on empty input and RuntimeError when the key is missing or
    Deepgram fails — the caller (endpoint) turns these into JSON errors for the
    UI rather than failing silently.
    """
    if not data:
        raise ValueError("Empty audio payload.")

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPGRAM_API_KEY is not set. Add it to Backend/.env "
            "(get a key at console.deepgram.com)."
        )

    from deepgram import DeepgramClient  # lazy import

    client = DeepgramClient(api_key=api_key)
    errors: list[str] = []

    # Attempt A — deepgram-sdk v3 sync REST (listen.rest.v("1").transcribe_file)
    try:
        from deepgram import PrerecordedOptions

        options = PrerecordedOptions(model=MODEL, smart_format=True, language=LANGUAGE)
        source: dict = {"buffer": data}
        if mimetype:
            source["mimetype"] = mimetype
        resp = client.listen.rest.v("1").transcribe_file(source, options)
        return _transcript_from_response(resp)
    except Exception as e:  # wrong SDK shape / missing symbol — try the next one
        errors.append(f"v3-rest: {e!r}")

    # Attempt B — deepgram-sdk v4 media API (same major version as the streaming
    # client used below: client.listen.v1.connect(...)).
    for kwargs in ({"request": data}, {"source": data}, {"file": data}):
        try:
            resp = client.listen.v1.media.transcribe_file(
                model=MODEL, smart_format=True, language=LANGUAGE, **kwargs
            )
            return _transcript_from_response(resp)
        except Exception as e:
            errors.append(f"v4-media{list(kwargs)}: {e!r}")

    raise RuntimeError("Deepgram transcription failed — " + " | ".join(errors))


def _run_live() -> None:
    """Live-mic CLI: stream the microphone to Deepgram and forward each final
    transcript to the Librarian. All mic/agent imports live here so importing
    this module for `transcribe_audio_bytes` never needs a mic or sounddevice.
    """
    import asyncio
    import queue
    import threading

    import sounddevice as sd
    from deepgram import DeepgramClient
    from deepgram.core.events import EventType

    from uagents import Agent, Context, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        chat_protocol_spec,
    )

    from agents.common.chat import encode_envelope, make_ack, make_chat, text_of

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise RuntimeError("Set DEEPGRAM_API_KEY in your .env file")

    sample_rate = 16000  # Hz, matches what we tell Deepgram below
    channels = 1
    blocksize = 1024  # frames per mic callback

    librarian = config.LIBRARIAN_ADDRESS
    user_id = config.DEFAULT_USER_ID

    dg_client = DeepgramClient(api_key=api_key)
    audio_queue: "queue.Queue[bytes]" = queue.Queue()

    agent = Agent(name="voicetotext", seed="baseline-voicetotext-seed-v1", port=8010, mailbox=True)
    proto = Protocol(spec=chat_protocol_spec)

    # Set once on startup, inside the agent's running event loop. The Deepgram
    # callback fires on its own thread, so it schedules sends onto this loop.
    state: dict = {"loop": None}

    def mic_callback(indata, frames, time_info, status):
        if status:
            print(f"[mic] {status}")
        audio_queue.put(bytes(indata))

    def run_transcription(ctx: Context):
        with dg_client.listen.v1.connect(
            model=MODEL,
            language=LANGUAGE,
            encoding="linear16",  # raw PCM has no header, so we declare the format
            sample_rate=sample_rate,
            channels=channels,
        ) as connection:
            ready = threading.Event()

            def on_message(result):
                if result.type != "Results" or not result.is_final:
                    return
                transcript = result.channel.alternatives[0].transcript
                if not transcript:
                    return
                if librarian and state["loop"]:
                    envelope = encode_envelope(user_id, transcript)
                    asyncio.run_coroutine_threadsafe(
                        ctx.send(librarian, make_chat(envelope)), state["loop"]
                    )
                    print(f"[FINAL → librarian] {transcript}")
                else:
                    print(f"[FINAL] {transcript}  (LIBRARIAN_ADDRESS not set — not forwarded)")

            connection.on(EventType.OPEN, lambda _: ready.set())
            connection.on(EventType.MESSAGE, on_message)

            def stream_mic():
                ready.wait()
                with sd.RawInputStream(
                    samplerate=sample_rate,
                    blocksize=blocksize,
                    channels=channels,
                    dtype="int16",
                    callback=mic_callback,
                ):
                    while True:
                        connection.send_media(audio_queue.get())

            threading.Thread(target=stream_mic, daemon=True).start()
            print("Listening on your microphone — speak now (Ctrl+C to stop)...")
            connection.start_listening()

    @agent.on_event("startup")
    async def start(ctx: Context):
        state["loop"] = asyncio.get_running_loop()
        print(f"[voicetotext] my address: {agent.address}")
        if not librarian:
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
    agent.run()


if __name__ == "__main__":
    _run_live()
