![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Coaching Agent

**Agent name:** `coaching`
**Agent address:** `agent1q...` ← paste the address printed on boot

Delivers targeted tactical and technique advice, and chains to the Fitness agent when a physical conditioning gap needs addressing.

## What it does

The Coaching agent produces sport-specific advice tailored to one of three contexts:

**Injury accommodation** (chained from Recovery): when Recovery flags a medium/high injury risk, Coaching advises how to adjust playing strategy and technique to stay competitive while protecting the area. For example, if the shoulder is flagged, it recommends reducing serve pace and switching to more slice-based play rather than full-swing groundstrokes.

**Weakness exploitation counter** (chained from Scout): when Scout finds that an opponent consistently targets a specific weakness (e.g. backhand), Coaching advises the tactical adjustments and technique cues needed to defend and counter that pattern in the next match.

**Performance gap** (chained from Performance): when Performance analysis shows a consistent underperforming area across multiple matches, Coaching prescribes targeted technique changes and drills.

After generating advice, Coaching checks whether the recommendation has a physical/conditioning component (e.g. "backhand needs more hip drive and core rotation"). If it does, it automatically chains to the **Fitness agent** with a focused brief so Fitness can build the right conditioning exercises.

## Chains it receives and fires

| Receives from | Trigger |
|---|---|
| Recovery Agent | injury/fatigue risk ≥ medium |
| Scout Agent | opponent exploits a weakness |
| Performance Agent | consistent weak area in form trend |

| Fires to | When |
|---|---|
| Fitness Agent | advice has a physical/conditioning component |

## How to use it

Send a note like:

> "My backhand keeps getting attacked — how do I defend it?"

or

> "Shoulder is sore but I have a match next week — what should I change in my game?"

It replies with tactical advice, technique focus areas, and (if relevant) a brief to the Fitness agent for conditioning support.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
