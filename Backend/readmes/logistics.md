![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Logistics Agent

**Agent name:** `logistics`
**Agent address:** `agent1q...` ← paste the address printed on boot

Finds the athlete's next tournament and puts it on the calendar.

## What it does
Over the **Agent Chat Protocol**, on a tournament/travel/schedule note it
searches a tournament finder via **Browserbase** (with a cached fallback so the
demo never depends on a live scrape), uses Claude to extract the best-matching
event, adds it to the athlete's calendar (dashboard + optional Google Calendar),
writes a dashboard insight, and replies with the event details.

## How to use it
Send a note like:

> "There's a tournament in San Jose in two weeks I want to enter."

It replies with the tournament name, dates, venue, and a calendar confirmation.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Browserbase · Google Calendar · Anthropic Claude
