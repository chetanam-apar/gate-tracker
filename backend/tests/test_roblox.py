"""
Tests for the Roblox parser and paging, using a saved sample shaped like the real API.
No internet needed.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.roblox import RobloxCollector, parse_sorts, to_chart_name
from app.core.config import Settings

PAGES = json.loads((Path(__file__).parent / "fixtures" / "roblox_sample.json").read_text())
NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def parse(**kw):
    args = dict(device="computer", country="in", top_n=50, collected_at=NOW)
    return parse_sorts(PAGES, **(args | kw))


def test_chart_names():
    assert to_chart_name("top-playing-now") == "top_playing_now"
    assert to_chart_name("trending-in-sports-and-racing") == "trending_in_sports_and_racing"


def test_only_game_lists_are_saved():
    charts = {r.chart for r in parse()}
    assert charts == {"top_trending", "top_playing_now"}  # Filters and Songs skipped


def test_skips_ads_and_repeats_and_ranks_are_continuous():
    trending = [r for r in parse() if r.chart == "top_trending"]
    assert [r.name for r in trending] == ["Hyper Realistic Ragdoll", "Voxel Wars", "Krillion 🦐 [UNLIMITED]"]
    assert [r.rank for r in trending] == [1, 2, 3]  # no gap where the ad was


def test_keeps_player_count_genre_and_link():
    first = parse()[0]
    assert first.player_count == 46568
    assert first.genre == "Simulation"
    assert first.store_url == "https://www.roblox.com/games/101277003916102"
    assert first.device == "computer" and first.platform == "roblox"


def test_broken_game_is_skipped():
    playing = [r for r in parse() if r.chart == "top_playing_now"]
    assert len(playing) == 2


def test_top_n_limit():
    trending = [r for r in parse(top_n=2) if r.chart == "top_trending"]
    assert len(trending) == 2


def test_pick_only_some_charts():
    assert {r.chart for r in parse(wanted_charts={"top_playing_now"})} == {"top_playing_now"}


class FakeHttp:
    """Pretends to be the internet: returns page 1, then page 2 when asked with the token."""
    def __init__(self):
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append(params)
        return PAGES[1] if params.get("sortsPageToken") == "page2" else PAGES[0]


def test_collector_follows_pages_for_each_device():
    settings = Settings(platforms={"roblox": {"enabled": True, "charts": "all",
                                              "devices": ["high_end_phone", "computer", "toaster"]}})
    http = FakeHttp()
    results = RobloxCollector(settings, http).collect()
    assert len(http.calls) == 4                     # 2 pages x 2 valid devices ("toaster" skipped)
    assert {r.device for r in results} == {"high_end_phone", "computer"}
    assert http.calls[0]["country"] == "in"
