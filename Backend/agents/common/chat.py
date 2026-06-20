"""Helpers around the standardized uAgents chat protocol.

The Fetch.ai prize specifically scores agents that talk over the
`uagents_core.contrib.protocols.chat` protocol, so all inter-agent
traffic in this layer is `ChatMessage` / `ChatAcknowledgement`.

The chat protocol only carries free text (that's all the Agentverse
"Chat with Agent" button can send). To move a little structure between
our own agents we JSON-encode a small envelope inside the text and fall
back to treating the whole string as a raw dump when it isn't JSON — so
a human typing plain text in Agentverse still works.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def text_of(msg: ChatMessage) -> str:
    """Concatenate all TextContent parts of an incoming ChatMessage."""
    return "".join(
        part.text for part in msg.content if isinstance(part, TextContent)
    )


def is_start(msg: ChatMessage) -> bool:
    """True if the message opens a session (no work to do, just greet)."""
    return any(isinstance(p, StartSessionContent) for p in msg.content)


def make_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Build a ChatMessage wrapping a text block, optionally ending the session."""
    content: list = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=_now(), msg_id=uuid4(), content=content)


def make_ack(msg: ChatMessage) -> ChatAcknowledgement:
    """Build the acknowledgement the protocol expects for an incoming msg."""
    return ChatAcknowledgement(timestamp=_now(), acknowledged_msg_id=msg.msg_id)


def encode_envelope(user_id: str, text: str, **extra) -> str:
    """Encode a routed payload (user_id + text + optional metadata) as text."""
    payload = {"user_id": user_id, "text": text}
    payload.update(extra)
    return json.dumps(payload)


def decode_envelope(raw: str, default_user_id: str) -> dict:
    """Decode an envelope. Falls back to {user_id, text} for plain text.

    Returns a dict that always has `user_id` and `text` keys.
    """
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "text" in data:
                data.setdefault("user_id", default_user_id)
                return data
        except json.JSONDecodeError:
            pass
    return {"user_id": default_user_id, "text": raw}
