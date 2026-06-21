"""Browserbase-backed tournament + opponent search, with cached fallbacks.

Framework rule: live scraping is the happy path; a cached result is ALWAYS the
fallback so the demo never depends on a live scrape. Both helpers return
`(raw_page_text, source)` where source is "live" or "cached"; the calling agent
then uses Claude to extract structured data from the text.

Live path: open a Browserbase cloud browser session and drive it with Playwright
over CDP, navigate to a search page, and return the page's visible text. If
BROWSERBASE_API_KEY / BROWSERBASE_PROJECT_ID aren't set (or playwright/browserbase
aren't installed, or anything errors/times out), we return the cached sample.

Override the search pages with TOURNAMENT_SEARCH_URL / OPPONENT_SEARCH_URL
(use `{q}` as the query placeholder).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from agents.common import config

log = logging.getLogger("tournaments")

_TOURNAMENT_URL = os.environ.get(
    "TOURNAMENT_SEARCH_URL", "https://www.bing.com/search?q={q}"
)
_OPPONENT_URL = os.environ.get(
    "OPPONENT_SEARCH_URL", "https://www.bing.com/search?q={q}"
)
_NAV_TIMEOUT_MS = 30000


# ── cached fallbacks (realistic raw page text for Claude to extract) ──
_CACHED_TOURNAMENT = """
NorCal Tennis — Upcoming Tournaments (Bay Area)
------------------------------------------------
San Jose Open  •  USTA Adult/Open  •  Hard court
Dates: Sat–Sun, two weeks out
Venue: Alpine Tennis Courts, San Jose, CA
Draws: Open Singles, 4.0/4.5 NTRP
Entry deadline: Wednesday before start
Register: https://www.usta.com/tournaments/san-jose-open

Other nearby: Santa Clara Spring Classic (3 weeks, Santa Clara, CA),
Peninsula Ladder Finals (next month, Palo Alto, CA).
""".strip()

_CACHED_OPPONENT = """
Player Profile — recent results (last 10 matches)
-------------------------------------------------
Right-handed, two-handed backhand. Strong baseline grinder.
W 6-3 6-4 vs Chen | L 4-6 5-7 vs Okafor | W 7-6 6-2 vs Singh
L 3-6 4-6 vs Becker | W 6-1 6-4 vs Ruiz | W 6-4 7-5 vs Adams
Notes: heavy topspin forehand, prefers long rallies, struggles with low slices
and serve-and-volley pressure. Second serve is attackable. Footwork dips late
in third sets (fitness fades). Best surface: hard court.
""".strip()


def _connect_url(session) -> str | None:
    return getattr(session, "connect_url", None) or getattr(session, "connectUrl", None)


def _live_text(query: str, url_template: str) -> str | None:
    """Drive a Browserbase session with Playwright → return page text, or None
    on any issue so the caller falls back to cached. Never hangs/crashes."""
    if not (config.BROWSERBASE_API_KEY and config.BROWSERBASE_PROJECT_ID):
        return None
    try:
        from browserbase import Browserbase  # lazy: optional deps
        from playwright.sync_api import sync_playwright

        bb = Browserbase(api_key=config.BROWSERBASE_API_KEY)
        session = bb.sessions.create(project_id=config.BROWSERBASE_PROJECT_ID)
        connect_url = _connect_url(session)
        if not connect_url:
            log.warning("Browserbase session had no connect URL")
            return None

        url = url_template.format(q=quote_plus(query))
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(connect_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            text = page.inner_text("body")
            browser.close()
        text = (text or "").strip()
        log.info("Browserbase live scrape ok (%d chars) for: %s", len(text), query)
        return text[:6000] or None
    except Exception as e:  # noqa: BLE001 - any failure → cached fallback
        log.warning("Browserbase live scrape failed, using cache: %s", e)
        return None


def fetch_tournament_text(location: str, date_window: str = "") -> tuple[str, str]:
    q = f"tennis tournaments near {location} {date_window}".strip()
    text = _live_text(q, _TOURNAMENT_URL)
    return (text, "live") if text else (_CACHED_TOURNAMENT, "cached")


def fetch_opponent_text(name: str) -> tuple[str, str]:
    text = _live_text(f"{name} tennis player recent match results", _OPPONENT_URL)
    return (text, "live") if text else (_CACHED_OPPONENT, "cached")
