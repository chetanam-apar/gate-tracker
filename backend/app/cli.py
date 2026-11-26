"""
Command-line entry point. Run from the backend/ folder:

  python -m app.cli collect                      # fetch all enabled platforms and SAVE to database
  python -m app.cli collect --platform appstore  # just one platform
  python -m app.cli collect --dry-run            # fetch and print only, don't save
  python -m app.cli collect --dry-run --save-json  # also save a copy to data/*.json

  python -m app.cli charts                       # list every chart saved on the latest day
  python -m app.cli show --chart top_free        # show the latest saved chart, with rank changes
  python -m app.cli show --platform roblox --chart top_trending --device high_end_phone
  python -m app.cli runs                         # history of collection runs

In Step 4 the 12 AM scheduler will call the same collect_and_save() function.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.collectors.base import GameRank
from app.collectors.registry import COLLECTORS
from app.core.config import ConfigError, get_settings
from app.core.http import HttpClient
from app.core.logger import get_logger, setup_logging
from app.db import repository as repo
from app.db.models import CollectionRun
from app.db.session import DatabaseNotConfigured, session_scope

log = get_logger("app.cli")


# ---------- Collect ----------

def run_collectors(only_platform: str | None = None) -> tuple[list[GameRank], list[str]]:
    """Run every enabled collector. Returns (all results, list of failed platforms)."""
    settings = get_settings()
    results: list[GameRank] = []
    failed: list[str] = []

    with HttpClient(settings.http.timeout_seconds, settings.http.max_retries) as http:
        for name, collector_class in COLLECTORS.items():
            if only_platform and name != only_platform:
                continue
            platform_config = settings.platforms.get(name)
            is_enabled = platform_config is not None and platform_config.enabled
            # --platform forces a run even if disabled (handy for testing)
            if not only_platform and not is_enabled:
                log.info("Skipping %s (disabled in config.yaml)", name)
                continue
            try:
                results.extend(collector_class(settings, http).collect())
            except Exception:
                # One platform failing must NOT stop the others
                log.exception("Collector '%s' failed", name)
                failed.append(name)
    return results, failed


def short_error(exc: Exception) -> str:
    """A short, readable error for run history: the error TYPE + first line only.
    (Database errors can be huge because they include all the data that failed.)"""
    original = getattr(exc, "orig", None) or exc   # for database errors, use the real cause
    first_line = (str(original).strip().splitlines() or [""])[0]
    return f"{type(original).__name__}: {first_line}"[:500]


def today_local() -> date:
    """Today's date in the app time zone (IST), not the server's time zone (UTC on EC2)."""
    return datetime.now(ZoneInfo(get_settings().app.timezone)).date()


def collect_and_save(only_platform: str | None = None, trigger: str = "manual") -> tuple[int, list[str]]:
    """Fetch + save, and record the run in collection_runs. Returns (saved count, failed platforms)."""
    # 1. Write "running" first, so even a crash leaves a trace in run history
    with session_scope() as session:
        run_id = repo.start_run(session, trigger=trigger).id

    try:
        results, failed = run_collectors(only_platform)
        with session_scope() as session:
            saved = repo.save_rankings(session, results, ranking_date=today_local(), run_id=run_id)
    except Exception as exc:
        # Always save the error TYPE too: some errors have an empty message
        error = short_error(exc)
        log.exception("Run %s failed while collecting or saving", run_id)
        with session_scope() as session:
            repo.finish_run(session, session.get(CollectionRun, run_id), 0, [], error=error)
        raise

    # 2. Mark the run as success / partial / failed
    with session_scope() as session:
        repo.finish_run(session, session.get(CollectionRun, run_id), saved, failed)
    return saved, failed


# ---------- Printing ----------

def print_results(results: list[GameRank]) -> None:
    current = None
    for r in results:
        if (r.platform, r.chart, r.device) != current:
            current = (r.platform, r.chart, r.device)
            print(f"\n=== {r.platform.upper()} | {r.chart} | {r.country.upper()} | {r.device} ===")
            print(f"{'#':>3}  {'Game':<45} {'Players':>9}  Developer / genre")
        players = f"{r.player_count:,}" if r.player_count is not None else "-"
        print(f"{r.rank:>3}  {r.name[:45]:<45} {players:>9}  {r.developer or r.genre or '-'}")


def change_label(change: int | None) -> str:
    if change is None:
        return "NEW"
    if change > 0:
        return f"▲ {change}"
    if change < 0:
        return f"▼ {-change}"
    return "="


def save_json(results: list[GameRank]) -> Path:
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"collect_{datetime.now():%Y-%m-%d_%H%M}.json"
    path.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2, ensure_ascii=False))
    return path


def explain_db_error(message: str) -> str:
    """Turn a raw database error into a hint a human can act on (without printing the password)."""
    text = message.lower()
    if "resolve host" in text or "nodename nor servname" in text:
        return ("DATABASE_URL in .env looks wrong. If your password has @ : / # ? in it, "
                "replace them in DATABASE_URL only (@ -> %40, : -> %3A, / -> %2F, # -> %23, ? -> %3F).")
    if "password authentication failed" in text:
        return ("Database password doesn't match. The password in DATABASE_URL must be the same as "
                "POSTGRES_PASSWORD when the database was first created. Fresh start: docker compose down -v && docker compose up -d")
    if "does not exist" in text and "relation" in text:
        return "Tables are missing. Run: alembic upgrade head"
    if "refused" in text or "could not connect" in text or "connection failed" in text:
        return "Can't reach the database. Is Docker Desktop open? Then run: docker compose up -d"
    return f"Database error: {message.strip().splitlines()[0]}"


# ---------- Commands ----------

def cmd_collect(args) -> int:
    if args.dry_run:
        results, failed = run_collectors(args.platform)
        print_results(results)
        if args.save_json and results:
            log.info("Saved to %s", save_json(results))
        log.info("Dry run: %d games fetched, nothing saved to database", len(results))
        return 1 if failed else 0

    saved, failed = collect_and_save(args.platform)
    log.info("Done: %d rankings saved, %d platform(s) failed %s", saved, len(failed), failed or "")
    log.info("See them with: python -m app.cli show --chart top_free")
    return 1 if failed else 0


def cmd_show(args) -> int:
    country = args.country or get_settings().defaults.country
    day = date.fromisoformat(args.date) if args.date else None
    device = args.device or ("computer" if args.platform == "roblox" else "all")
    with session_scope() as session:
        day, rows = repo.get_chart(session, args.platform, args.chart, country, device=device, day=day)
    if not rows:
        print(f"No data for {args.platform} / {args.chart} / {country} / {device}.")
        print("See what's saved with: python -m app.cli charts")
        return 0
    print(f"\n=== {args.platform.upper()} | {args.chart} | {country.upper()} | {device} | {day} ===")
    print(f"{'#':>3}  {'Change':<7} {'Game':<45} {'Players':>9}  Developer / genre")
    for row in rows[: args.limit]:
        players = f"{row.player_count:,}" if row.player_count is not None else "-"
        print(f"{row.rank:>3}  {change_label(row.change):<7} {row.name[:45]:<45} {players:>9}  "
              f"{row.developer or row.genre or '-'}")
    return 0


def cmd_charts(args) -> int:
    day = date.fromisoformat(args.date) if args.date else None
    with session_scope() as session:
        day, charts = repo.list_charts(session, day)
    if not charts:
        print("No data yet. Run: python -m app.cli collect")
        return 0
    print(f"\nCharts saved on {day}:\n")
    print(f"{'Platform':<10} {'Device':<16} {'Chart':<38} Games")
    for c in charts:
        print(f"{c.platform:<10} {c.device:<16} {c.chart:<38} {c.games}")
    print("\nShow one with: python -m app.cli show --platform <platform> --chart <chart> --device <device>")
    return 0


def cmd_runs(args) -> int:
    with session_scope() as session:
        runs = repo.recent_runs(session, args.limit)
    if not runs:
        print("No runs yet.")
        return 0
    tz = ZoneInfo(get_settings().app.timezone)
    print(f"\n{'ID':>4}  {'Started (IST)':<20} {'Status':<8} {'Saved':>5}  {'Trigger':<9} Failed")
    for r in runs:
        started_utc = r.started_at if r.started_at.tzinfo else r.started_at.replace(tzinfo=timezone.utc)
        started = started_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{r.id:>4}  {started:<20} {r.status:<8} {r.games_collected:>5}  {r.trigger:<9} {r.failed_platforms or ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-tracker", description="Game Tracker commands")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("collect", help="Fetch top games and save to database")
    p.add_argument("--platform", choices=list(COLLECTORS), help="Only this platform")
    p.add_argument("--dry-run", action="store_true", help="Fetch and print only, don't save")
    p.add_argument("--save-json", action="store_true", help="With --dry-run: also save to data/*.json")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("show", help="Show a saved chart with rank changes")
    p.add_argument("--platform", default="appstore", choices=list(COLLECTORS))
    p.add_argument("--chart", default="top_free", help="e.g. top_free, top_grossing, top_trending. See: charts")
    p.add_argument("--device", help="Roblox: high_end_phone / computer. Default: computer (Roblox), all (others)")
    p.add_argument("--country", help="Default: from config.yaml")
    p.add_argument("--date", help="YYYY-MM-DD. Default: latest")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("charts", help="List every chart saved on a day")
    p.add_argument("--date", help="YYYY-MM-DD. Default: latest")
    p.set_defaults(func=cmd_charts)

    p = sub.add_parser("runs", help="Show recent collection runs")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_runs)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    setup_logging()
    try:
        return args.func(args)
    except (ConfigError, DatabaseNotConfigured) as exc:
        log.error("%s", exc)
        return 2
    except (OperationalError, ProgrammingError) as exc:
        log.error("%s", explain_db_error(str(exc.orig)))
        return 2


if __name__ == "__main__":
    sys.exit(main())
