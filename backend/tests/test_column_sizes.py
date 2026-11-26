"""
Checks that real values fit in the database columns.

Why this test exists: SQLite (used in our other tests) ignores text length
limits, but PostgreSQL (used for real) enforces them. A 35-character Roblox
chart name once broke a whole run because the column allowed only 32.
"""
from app.collectors.roblox import VALID_DEVICES, to_chart_name
from app.db.models import CollectionRun, Game, Ranking

# Real Roblox sortIds seen from the API on 2026-11-26
REAL_ROBLOX_SORT_IDS = [
    "top-trending", "up-and-coming", "top-playing-now", "fun-with-friends", "top-revisited",
    "top-earning", "top-paid-access", "top-rated", "most-popular", "trending-music-experiences",
    "trending-in-rpg", "trending-in-sports-and-racing", "trending-in-shooter", "trending-in-action",
    "trending-in-adventure", "trending-in-entertainment", "trending-in-obby-and-platformer",
    "trending-in-party-and-casual", "trending-in-puzzle", "trending-in-roleplay-and-avatar-sim",
    "trending-in-shopping", "trending-in-simulation", "trending-in-strategy", "trending-in-survival",
    "learning-and-explore",
]


def max_len(column) -> int:
    return column.property.columns[0].type.length


def test_real_roblox_chart_names_fit_with_room_to_grow():
    longest = max(len(to_chart_name(s)) for s in REAL_ROBLOX_SORT_IDS)
    # Leave room: Roblox may add longer names later
    assert longest * 1.5 <= max_len(Ranking.chart), f"longest chart name is {longest} chars"


def test_devices_fit():
    assert max(len(d) for d in VALID_DEVICES | {"all"}) <= max_len(Ranking.device)


def test_platform_and_status_fit():
    assert max(len(p) for p in ["appstore", "playstore", "roblox"]) <= max_len(Game.platform)
    assert max(len(s) for s in ["running", "success", "partial", "failed"]) <= max_len(CollectionRun.status)
