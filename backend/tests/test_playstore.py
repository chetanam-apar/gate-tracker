"""
Tests for the Play Store request builder and parser.
The sample file has the same shape as Google's real answer (checked on 2026-11-26).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.collectors.playstore import CHARTS, PlayStoreCollector, build_request_body, parse_response
from app.core.config import Settings

SAMPLE = (Path(__file__).parent / "fixtures" / "playstore_sample.txt").read_text()
NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def parse(text=SAMPLE):
    return parse_response(text, chart="top_free", country="in", collected_at=NOW)


def test_parses_games_in_order_and_skips_broken_entry():
    ranks = parse()
    assert [r.name for r in ranks] == ["Sheru Bhai Life Simulator Game", "Free Fire India", "Ludo King®"]
    assert [r.rank for r in ranks] == [1, 2, 3]   # no gap where the broken entry was


def test_fields():
    ff = parse()[1]
    assert ff.game_id == "com.garena.game.ffi"
    assert ff.developer == "Garena International III"
    assert ff.store_url == "https://play.google.com/store/apps/details?id=com.garena.game.ffi"
    assert ff.icon_url.startswith("https://play-lh.googleusercontent.com/")
    assert ff.platform == "playstore" and ff.device == "all"


def test_changed_format_raises_clear_error():
    with pytest.raises(ValueError, match="format may have changed"):
        parse(")]}'\n\n12\n<html>something else</html>")


def test_request_asks_for_right_chart_category_and_count():
    outer = json.loads(build_request_body(50, "topgrossing")["f.req"])
    assert outer[0][0][0] == "vyAe2"
    question = json.loads(outer[0][0][1])
    assert question[0][2] == [2, "topgrossing", "GAME"]
    assert question[0][1][0] == [8, [20, 50]]


class FakeHttp:
    def __init__(self, text):
        self.text, self.calls = text, []

    def post_form(self, url, data, params=None):
        self.calls.append(params)
        return self.text


def test_collector_calls_each_chart_with_india():
    settings = Settings(platforms={"playstore": {"enabled": True, "charts": "all"}})
    http = FakeHttp(SAMPLE)
    results = PlayStoreCollector(settings, http).collect()
    assert len(http.calls) == len(CHARTS)
    assert all(c["gl"] == "IN" for c in http.calls)
    assert {r.chart for r in results} == set(CHARTS)


def test_empty_chart_is_treated_as_failure():
    empty = SAMPLE.split("\n")
    obj_line = json.loads(empty[3])
    inner = json.loads(obj_line[0][2])
    inner[0][1][0][28][0] = []
    obj_line[0][2] = json.dumps(inner)
    empty[3] = json.dumps(obj_line)
    settings = Settings(platforms={"playstore": {"enabled": True, "charts": ["top_free"]}})
    with pytest.raises(ValueError, match="0 games"):
        PlayStoreCollector(settings, FakeHttp("\n".join(empty))).collect()
