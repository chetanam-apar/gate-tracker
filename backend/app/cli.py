"""
Command-line entry point. Run from the backend/ folder:

  python -m app.cli collect                     # all enabled platforms
  python -m app.cli collect --platform appstore # just one platform
  python -m app.cli collect --save              # also save results to data/ as JSON

In Step 4 the 12 AM scheduler will call the same run_collection() function.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.collectors.base import GameRank
from app.collectors.registry import COLLECTORS
from app.core.config import ConfigError, get_settings
from app.core.http import HttpClient
from app.core.logger import get_logger, setup_logging

log = get_logger("app.cli")


def run_collection(only_platform: str | None = None) -> tuple[list[GameRank], list[str]]:
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


def print_table(results: list[GameRank]) -> None:
    current = None
    for r in results:
        key = (r.platform, r.chart)
        if key != current:
            current = key
            print(f"\n=== {r.platform.upper()} | {r.chart} | {r.country.upper()} ===")
            print(f"{'#':>3}  {'Game':<45} Developer")
        print(f"{r.rank:>3}  {r.name[:45]:<45} {r.developer or '-'}")


def save_json(results: list[GameRank]) -> Path:
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"collect_{datetime.now():%Y-%m-%d_%H%M}.json"
    path.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2, ensure_ascii=False))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(prog="game-tracker", description="Game Tracker commands")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="Fetch top games from platforms")
    collect.add_argument("--platform", choices=list(COLLECTORS), help="Only this platform")
    collect.add_argument("--save", action="store_true", help="Save results to data/*.json")
    args = parser.parse_args()

    setup_logging()
    try:
        results, failed = run_collection(args.platform)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    print_table(results)
    if args.save and results:
        log.info("Saved to %s", save_json(results))

    log.info("Done: %d games collected, %d platform(s) failed %s", len(results), len(failed), failed or "")
    return 1 if failed else 0  # exit code 1 tells cron/CI that something went wrong


if __name__ == "__main__":
    sys.exit(main())
