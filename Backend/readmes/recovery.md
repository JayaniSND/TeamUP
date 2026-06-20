![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Recovery Agent

**Agent name:** `recovery`
**Agent address:** `agent1q...` ← paste the address printed on boot

Flags overtraining and injury-risk patterns from an athlete's history.

## What it does
Over the **Agent Chat Protocol**, takes an injury/fitness note, pulls the
athlete's recent injury log and metrics from the journal backend, and asks
Claude whether there is an overtraining pattern — e.g. the same body part
sore across 3+ sessions, a training-volume spike, or a declining recovery
score. It writes a flag the dashboard surfaces and replies with a verdict and
recommendation.

## How to use it
Send a note like:

> "Right knee sore again after intervals, third time this week."

It replies with a risk level, the body parts involved, the rationale, and a
recommendation.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
