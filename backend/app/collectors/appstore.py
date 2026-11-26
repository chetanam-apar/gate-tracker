"""
Apple App Store collector.

Uses Apple's free public RSS feed (JSON). No API key needed.
Example URL (top free games in India, 50 results):
  https://itunes.apple.com/in/rss/topfreeapplications/limit=50/genre=6014/json

URL parts:
  in                   -> country code
  topfreeapplications  -> which chart
  limit=50             -> how many results
  genre=6014           -> 6014 is Apple's ID for "Games"

Note: Apple gives RANK, not how many people are playing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.collectors.base import BaseCollector, GameRank
from app.core.logger import get_logger

log = get_logger(__name__)

BASE_URL = "https://itunes.apple.com/{country}/rss/{feed}/limit={limit}/genre={genre}/json"
GAMES_GENRE_ID = 6014

# Our chart name  ->  Apple's feed name
CHART_FEEDS = {
    "top_free": "topfreeapplications",
    "top_paid": "toppaidapplications",
    "top_grossing": "topgrossingapplications",
}


class AppStoreCollector(BaseCollector):
    platform = "appstore"

    def collect(self) -> list[GameRank]:
        country = self.settings.defaults.country
        limit = self.settings.defaults.top_n
        charts = self.platform_settings.charts or list(CHART_FEEDS)

        results: list[GameRank] = []
        for chart in charts:
            feed = CHART_FEEDS.get(chart)
            if feed is None:
                log.warning("Unknown App Store chart '%s' in config.yaml, skipping. Valid: %s", chart, list(CHART_FEEDS))
                continue

            url = BASE_URL.format(country=country, feed=feed, limit=limit, genre=GAMES_GENRE_ID)
            log.info("Fetching App Store %s (%s)", chart, country)
            data = self.http.get_json(url)
            ranks = parse_feed(data, chart=chart, country=country, collected_at=datetime.now(timezone.utc))
            log.info("Got %d games for App Store %s", len(ranks), chart)
            results.extend(ranks)
        return results


def parse_feed(data: dict, chart: str, country: str, collected_at: datetime) -> list[GameRank]:
    """
    Convert Apple's JSON into our GameRank list.

    Kept as a separate function (not inside the class) so we can
    test it with saved sample data, without calling the internet.
    """
    entries = data.get("feed", {}).get("entry", [])
    # Apple quirk: if there is only ONE result, "entry" is a dict, not a list
    if isinstance(entries, dict):
        entries = [entries]

    ranks: list[GameRank] = []
    for position, entry in enumerate(entries, start=1):
        try:
            images = entry.get("im:image") or []
            ranks.append(
                GameRank(
                    platform="appstore",
                    chart=chart,
                    country=country,
                    rank=position,  # Apple returns them in rank order
                    game_id=entry["id"]["attributes"]["im:id"],
                    name=entry["im:name"]["label"],
                    developer=entry.get("im:artist", {}).get("label"),
                    icon_url=images[-1]["label"] if images else None,  # last image = biggest
                    store_url=entry["id"].get("label"),
                    collected_at=collected_at,
                )
            )
        except (KeyError, TypeError) as exc:
            # One bad row should not break the whole chart
            log.warning("Skipping App Store entry #%d, unexpected shape: %s", position, exc)
    return ranks
