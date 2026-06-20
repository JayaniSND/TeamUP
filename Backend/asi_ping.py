"""Optional: query ASI:One (OpenAI-compatible) — for the bonus demo clip.

Once the Orchestrator is registered on Agentverse with the chat protocol and
a README, ASI:One can discover and route to it. This script just verifies
your ASI:One key works and lets you show a natural-language query going
through ASI:One. It is NOT on the critical demo path.

Usage (from Backend/):
    ASI_ONE_API_KEY=... python asi_ping.py "find me a tennis tournament near San Jose"
"""

from __future__ import annotations

import sys

from openai import OpenAI

from agents.common import config

if not config.ASI_ONE_API_KEY:
    raise SystemExit("Set ASI_ONE_API_KEY in .env (get one at asi1.ai/dashboard/api-keys).")

query = sys.argv[1] if len(sys.argv) > 1 else "What can the BASELINE training-journal agent do?"

client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=config.ASI_ONE_API_KEY)
resp = client.chat.completions.create(
    model="asi1",
    messages=[{"role": "user", "content": query}],
)
print(resp.choices[0].message.content)
