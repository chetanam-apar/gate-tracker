"""
Tests for the App Store parser, using saved sample data.
No internet needed, so tests are fast and always give the same result.

Run from backend/:  python -m pytest
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.appstore import parse_feed

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "appstore_sample.json").read_text())
NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def test_parses_good_entries_in_rank_order():
    ranks = parse_feed(SAMPLE, chart="top_free", country="in", collected_at=NOW)
    assert [r.name for r in ranks] == ["Free Fire MAX", "Ludo King"]
    assert ranks[0].rank == 1
    assert ranks[0].game_id == "1480516829"
    assert ranks[0].developer == "Garena International I"


def test_picks_biggest_icon_and_handles_missing_icon():
    ranks = parse_feed(SAMPLE, chart="top_free", country="in", collected_at=NOW)
    assert ranks[0].icon_url == "https://example.com/ff-100.png"
    assert ranks[1].icon_url is None


def test_skips_broken_entry_instead_of_crashing():
    ranks = parse_feed(SAMPLE, chart="top_free", country="in", collected_at=NOW)
    assert len(ranks) == 2  # 3 entries in, 1 broken one skipped


def test_single_entry_as_dict_apple_quirk():
    one = {"feed": {"entry": SAMPLE["feed"]["entry"][0]}}
    assert len(parse_feed(one, chart="top_free", country="in", collected_at=NOW)) == 1


def test_empty_feed():
    assert parse_feed({"feed": {}}, chart="top_free", country="in", collected_at=NOW) == []
