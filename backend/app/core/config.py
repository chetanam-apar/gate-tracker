"""
Loads settings from config.yaml (non-secret) and .env (secrets).

Why two files?
- config.yaml = things a non-tech person may change (country, top N, time).
- .env       = passwords and keys. Never pushed to GitHub.

Pydantic checks every value. If someone types something wrong
(e.g. top_n: "fifty"), the app stops with a clear message instead
of failing in a strange way later.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


class AppSection(BaseModel):
    name: str = "Game Tracker"
    timezone: str = "Asia/Kolkata"


class ScheduleSection(BaseModel):
    daily_run_time: str = "00:00"

    @field_validator("daily_run_time")
    @classmethod
    def check_time(cls, value: str) -> str:
        hour, _, minute = value.partition(":")
        if not (hour.isdigit() and minute.isdigit() and 0 <= int(hour) < 24 and 0 <= int(minute) < 60):
            raise ValueError('must look like "HH:MM", for example "00:00" or "18:30"')
        return value


class DefaultsSection(BaseModel):
    country: str = Field("in", min_length=2, max_length=2)
    top_n: int = Field(50, ge=1, le=200)


class PlatformSection(BaseModel):
    enabled: bool = False
    charts: list[str] | str = []     # a list of chart names, or "all"
    devices: list[str] = []          # Roblox only
    country: str | None = None       # override defaults.country for this platform


class HttpSection(BaseModel):
    timeout_seconds: float = Field(20, gt=0)
    max_retries: int = Field(3, ge=0, le=10)


class Settings(BaseModel):
    app: AppSection = AppSection()
    schedule: ScheduleSection = ScheduleSection()
    defaults: DefaultsSection = DefaultsSection()
    platforms: dict[str, PlatformSection] = {}
    http: HttpSection = HttpSection()


class ConfigError(Exception):
    """Raised when config.yaml is missing or has a wrong value."""


def _find_config_file() -> Path:
    # 1. CONFIG_PATH from .env, if set
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        return Path(env_path)
    # 2. Look in the current folder, then one folder up (project root)
    for candidate in (Path.cwd() / "config.yaml", Path.cwd().parent / "config.yaml"):
        if candidate.exists():
            return candidate
    raise ConfigError("config.yaml not found. Run the app from the project folder or set CONFIG_PATH in .env")


@lru_cache
def get_settings() -> Settings:
    """Read settings once and reuse them (lru_cache = remember the result)."""
    load_dotenv()  # loads .env into environment variables, if the file exists
    path = _find_config_file()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
        return Settings(**raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yaml has a formatting problem: {exc}") from exc
    except ValidationError as exc:
        lines = [f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
        raise ConfigError("config.yaml has wrong values:\n" + "\n".join(lines)) from exc
