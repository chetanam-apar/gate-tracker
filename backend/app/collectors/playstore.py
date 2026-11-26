"""
Google Play Store collector.

Google has NO public API for Play Store charts. This collector sends the
same request the Play Store website sends to its own internal endpoint
("batchexecute"), the method used by the open-source google-play-scraper
library. It works without login, but:
  - Google can change it at any time -> this collector breaks
  - Scraping is against Google Play's terms. We keep it light:
    3 requests a day for a learning project.
If it breaks, the run is marked "partial" and the other platforms still save.

How the request works:
  POST https://play.google.com/_/PlayStoreUi/data/batchexecute?rpcids=vyAe2&hl=en&gl=IN
  body: f.req=<a big nested JSON "question">
The "question" says: give me <num> apps from chart <topselling_free> in category <GAME>.
Most of it is a fixed list of which fields to return (we copy it as-is).

The answer is text like:
  )]}'                        <- anti-hijacking prefix, ignore
  <length>
  [["wrb.fr","vyAe2","<JSON as a string>", ...]]
Inside that JSON, the apps are at position [0][1][0][28][0].
Like Apple, Google gives RANK, not player counts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, GameRank
from app.core.logger import get_logger

log = get_logger(__name__)

URL = "https://play.google.com/_/PlayStoreUi/data/batchexecute"
BASE_PARAMS = {
    "rpcids": "vyAe2", "source-path": "/store/apps", "f.sid": "-4178618388443751758",
    "bl": "boq_playuiserver_20220612.08_p0", "authuser": "0", "soc-app": "121",
    "soc-platform": "1", "soc-device": "1", "_reqid": "82003", "rt": "c",
}
STORE_URL = "https://play.google.com"

# Our chart name -> Google's name
CHARTS = {
    "top_free": "topselling_free",
    "top_paid": "topselling_paid",
    "top_grossing": "topgrossing",
}

# --- The fixed "which fields to return" part of the request (copied from the website's request) ---
_MASK_IDS = [1, 31, 104, 9, 8, 27, 12, 65, 110, 88, 11, 56, 55, 96, 10, 122, 72, 71, 64, 113,
             139, 150, 169, 165, 151, 163, 32, 16, 108, 100]
_MASK_FIELDS = {
    7: [1, 73, 96, 103, 97, 58, 50, 92, 52, 112, 69, 19, 31, 101, 123, 74, 49, 80, 38, 20, 10, 14, 79, 43, 42, 139],
    9: [1, 7, 9, 24, 12, 31, 5, 15, 27, 8, 13, 10],
    17: [1, 7, 9, 25, 13, 31, 5, 41, 27, 8, 14, 10],
    10: [1, 7, 6, 9],
    1: [1, 5, 14, 38, 19, 29, 34, 4, 12, 11, 6, 30, 43, 40, 42, 16, 10, 7],
    4: [1, 3, 5, 4, 7, 6, 11, 19, 21, 17, 15, 12, 16, 20],
    3: [1, 5, 14, 4, 10, 17],
    2: [1, 5, 7, 4, 13, 16, 12, 18],
}
_TOP_FIELDS = [64, 1, 195, 71, 8, 72, 9, 10, 11, 139, 12, 16, 145, 148, 150, 151, 152, 27, 30, 31, 96, 32,
               34, 163, 100, 165, 104, 169, 108, 110, 113, 55, 56, 57, 122]
_OPTIONS = [[[True], None, [[None, []]], None, None, None, None, [None, 2], None, None, None, None, None, None,
             [1], None, None, None, None, None, None, None, [1]],
            [None, [[None, []]]], [None, [[None, []]], None, [True]], [None, [[None, []]]],
            None, None, None, None, [[[None, []]]], [[[None, []]]]]


def build_request_body(num: int, chart: str, category: str = "GAME") -> dict:
    masks = [[[group, mask_id], [_MASK_FIELDS[group]]] for group in _MASK_FIELDS for mask_id in _MASK_IDS]
    question = [[None,
                 [[8, [20, num]], True, None, _TOP_FIELDS, [None, None, _OPTIONS, [masks]],
                  None, None, [[[1, 2], [10, 8, 9], [], []]]],
                 [2, chart, category]]]
    # JSON inside JSON: Google's format wants the question as a string
    f_req = [[["vyAe2", json.dumps(question, separators=(",", ":")), None, "generic"]]]
    return {"f.req": json.dumps(f_req, separators=(",", ":"))}


class PlayStoreCollector(BaseCollector):
    platform = "playstore"

    def collect(self) -> list[GameRank]:
        cfg = self.platform_settings
        country = cfg.country or self.settings.defaults.country
        limit = self.settings.defaults.top_n
        charts = list(CHARTS) if cfg.charts in ("all", [], ["all"]) else cfg.charts

        results: list[GameRank] = []
        for chart in charts:
            google_chart = CHARTS.get(chart)
            if google_chart is None:
                log.warning("Unknown Play Store chart '%s' in config.yaml, skipping. Valid: %s", chart, list(CHARTS))
                continue
            log.info("Fetching Play Store %s (%s)", chart, country)
            text = self.http.post_form(URL, data=build_request_body(limit, google_chart),
                                       params={**BASE_PARAMS, "hl": "en", "gl": country.upper()})
            ranks = parse_response(text, chart=chart, country=country, collected_at=datetime.now(timezone.utc))
            if not ranks:
                # An empty chart almost always means Google changed the format
                raise ValueError(f"Play Store returned 0 games for {chart}. The response format may have changed.")
            log.info("Got %d games for Play Store %s", len(ranks), chart)
            results.extend(ranks[:limit])
        return results


def _dig(data, *path):
    """Safely walk nested lists: _dig(x, 0, 3) = x[0][3], or None if anything is missing."""
    for key in path:
        try:
            data = data[key]
        except (IndexError, KeyError, TypeError):
            return None
    return data


def parse_response(text: str, chart: str, country: str, collected_at: datetime) -> list[GameRank]:
    """Turn Google's batchexecute text into GameRank. Separate function so tests can use saved data."""
    payload = None
    for line in text.splitlines():   # find the data line instead of trusting a fixed line number
        if line.startswith('[["wrb.fr"'):
            payload = json.loads(line)
            break
    if payload is None or not isinstance(_dig(payload, 0, 2), str):
        raise ValueError("Play Store response has no data line. The format may have changed.")

    apps = _dig(json.loads(payload[0][2]), 0, 1, 0, 28, 0) or []
    results: list[GameRank] = []
    for position, item in enumerate(apps, start=1):
        app = _dig(item, 0)
        package_id, name = _dig(app, 0, 0), _dig(app, 3)
        if not package_id or not name:
            log.warning("Skipping Play Store entry #%d, unexpected shape", position)
            continue
        path = _dig(app, 10, 4, 2)
        results.append(GameRank(
            platform="playstore", chart=chart, country=country, rank=len(results) + 1,
            game_id=package_id,            # e.g. "com.pubg.imobile"
            name=name,
            developer=_dig(app, 14),
            icon_url=_dig(app, 1, 3, 2),
            store_url=f"{STORE_URL}{path}" if path else None,
            collected_at=collected_at,
        ))
    return results
