"""
Command-line entry point. Run from the backend/ folder:

  python -m app.cli collect                      # fetch all enabled platforms and SAVE to database
  python -m app.cli collect --platform appstore  # just one platform
  python -m app.cli collect --dry-run            # fetch and print only, don't save
  python -m app.cli collect --dry-run --save-json  # also save a copy to data/*.json

  python -m app.cli show --chart top_free        # show the latest saved chart, with rank changes
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

from sqlalchemy.exc import OperationalError

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
        with session_scope() as session:
            repo.finish_run(session, session.get(CollectionRun, run_id), 0, [], error=str(exc))
        raise

    # 2. Mark the run as success / partial / failed
    with session_scope() as session:
        repo.finish_run(session, session.get(CollectionRun, run_id), saved, failed)
    return saved, failed


# ---------- Printing ----------

def print_results(results: list[GameRank]) -> None:
    current = None
    for r in results:
        if (r.platform, r.chart) != current:
            current = (r.platform, r.chart)
            print(f"\n=== {r.platform.upper()} | {r.chart} | {r.country.upper()} ===")
            print(f"{'#':>3}  {'Game':<45} Developer")
        print(f"{r.rank:>3}  {r.name[:45]:<45} {r.developer or '-'}")


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
    with session_scope() as session:
        day, rows = repo.get_chart(session, args.platform, args.chart, country, day)
    if not rows:
        print(f"No data yet for {args.platform} / {args.chart} / {country}. Run: python -m app.cli collect")
        return 0
    print(f"\n=== {args.platform.upper()} | {args.chart} | {country.upper()} | {day} ===")
    print(f"{'#':>3}  {'Change':<7} {'Game':<45} Developer")
    for row in rows[: args.limit]:
        print(f"{row.rank:>3}  {change_label(row.change):<7} {row.name[:45]:<45} {row.developer or '-'}")
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
    p.add_argument("--chart", default="top_free", help="top_free / top_paid / top_grossing")
    p.add_argument("--country", help="Default: from config.yaml")
    p.add_argument("--date", help="YYYY-MM-DD. Default: latest")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_show)

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
    except OperationalError as exc:
        log.error("Can't reach the database. Is Docker running? Try: docker compose up -d\n  (%s)",
                  str(exc.orig).strip().splitlines()[0])
        return 2


if __name__ == "__main__":
    sys.exit(main())
