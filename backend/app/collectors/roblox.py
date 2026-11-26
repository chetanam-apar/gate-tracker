"""
Roblox charts collector.

Uses the same API that powers https://www.roblox.com/charts
  https://apis.roblox.com/explore-api/v1/get-sorts?sessionId=...&device=computer&country=in

Note: this API is NOT officially documented. It works without login,
but Roblox can change it any time. If that happens, the test with
saved sample data shows us exactly what broke.

How it works:
  - One call returns ~6 "sorts" (lists) like Top Trending, Top Playing Now...
  - The response has "nextSortsPageToken". We call again with
    sortsPageToken=<that token> to get the next 6, until it's empty.
  - ~26 lists in total. We skip non-game lists (Filters, Music).

Unlike the app stores, Roblox gives real LIVE PLAYER COUNTS.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, GameRank
from app.core.logger import get_logger

log = get_logger(__name__)

SORTS_URL = "https://apis.roblox.com/explore-api/v1/get-sorts"
GAME_URL = "https://www.roblox.com/games/{place_id}"
MAX_PAGES = 15  # safety stop, in case the API keeps returning a token forever

# Valid device values (taken from the API's own "Device" filter)
VALID_DEVICES = {"computer", "high_end_phone", "low_end_phone", "high_end_tablet",
                 "low_end_tablet", "console", "vr"}


def to_chart_name(sort_id: str) -> str:
    """'top-playing-now' -> 'top_playing_now' (same style as App Store chart names)."""
    return re.sub(r"[^a-z0-9]+", "_", sort_id.lower()).strip("_")


class RobloxCollector(BaseCollector):
    platform = "roblox"

    def collect(self) -> list[GameRank]:
        cfg = self.platform_settings
        country = cfg.country or self.settings.defaults.country
        devices = cfg.devices or ["computer"]
        wanted = None if cfg.charts in ("all", [], ["all"]) else {to_chart_name(c) for c in cfg.charts}

        results: list[GameRank] = []
        for device in devices:
            if device not in VALID_DEVICES:
                log.warning("Unknown Roblox device '%s' in config.yaml, skipping. Valid: %s", device, sorted(VALID_DEVICES))
                continue
            log.info("Fetching Roblox charts (%s, %s)", device, country)
            pages = self._fetch_all_pages(device, country)
            ranks = parse_sorts(pages, device=device, country=country, top_n=self.settings.defaults.top_n,
                                collected_at=datetime.now(timezone.utc), wanted_charts=wanted)
            charts = {r.chart for r in ranks}
            log.info("Got %d games across %d Roblox charts (%s)", len(ranks), len(charts), device)
            results.extend(ranks)
        return results

    def _fetch_all_pages(self, device: str, country: str) -> list[dict]:
        # A random session id per run, like a fresh browser visit
        params = {"sessionId": str(uuid.uuid4()), "device": device, "country": country}
        pages, token = [], None
        for _ in range(MAX_PAGES):
            data = self.http.get_json(SORTS_URL, params={**params, **({"sortsPageToken": token} if token else {})})
            pages.append(data)
            token = data.get("nextSortsPageToken")
            if not token:
                break
        return pages


def parse_sorts(pages: list[dict], device: str, country: str, top_n: int,
                collected_at: datetime, wanted_charts: set[str] | None = None) -> list[GameRank]:
    """Convert Roblox get-sorts pages into GameRank. Separate function so tests can use saved data."""
    results: list[GameRank] = []
    seen_charts: set[str] = set()

    for page in pages:
        for sort in page.get("sorts") or []:
            if sort.get("contentType") != "Games":   # skip "Filters", "Songs", etc.
                continue
            chart = to_chart_name(sort.get("sortId", ""))
            if not chart or chart in seen_charts or (wanted_charts and chart not in wanted_charts):
                continue
            seen_charts.add(chart)

            rank, seen_games = 0, set()
            for game in sort.get("games") or []:
                try:
                    universe_id = str(game["universeId"])
                    if game.get("isSponsored") or universe_id in seen_games:
                        continue  # ads are not real rankings; skip repeats
                    seen_games.add(universe_id)
                    rank += 1
                    results.append(GameRank(
                        platform="roblox", chart=chart, country=country, device=device, rank=rank,
                        game_id=universe_id,
                        name=game["name"].strip(),
                        genre=game.get("genreL1") or None,
                        player_count=game.get("playerCount"),
                        store_url=GAME_URL.format(place_id=game["rootPlaceId"]) if game.get("rootPlaceId") else None,
                        collected_at=collected_at,
                    ))
                except (KeyError, TypeError, AttributeError) as exc:
                    log.warning("Skipping Roblox game in '%s', unexpected shape: %s", chart, exc)
                    continue
                if rank >= top_n:
                    break
    return results
