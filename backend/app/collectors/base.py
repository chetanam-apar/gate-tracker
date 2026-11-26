"""
The "contract" every collector must follow.

Every platform's API returns data in a DIFFERENT shape.
Apple calls the name "im:name", Roblox calls it "name", and so on.
So each collector converts its platform's data into ONE common
shape: GameRank. The rest of the app (database, API, dashboard)
only ever sees GameRank, so it doesn't care which platform the
data came from.

To add a new platform, you:
  1. create a new file in collectors/ with a class that extends BaseCollector
  2. write its collect() method
  3. add it to registry.py
Nothing else in the app has to change. That's what "modular" means.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel

from app.core.config import PlatformSection, Settings
from app.core.http import HttpClient


class GameRank(BaseModel):
    """One game's position in one chart, at one moment in time."""

    platform: str               # "appstore", "playstore", "roblox"
    chart: str                  # "top_free", "top_grossing", "most_played" ...
    country: str                # "in"
    rank: int                   # 1 = top
    game_id: str                # the platform's own ID for this game
    name: str
    developer: str | None = None
    icon_url: str | None = None
    store_url: str | None = None
    player_count: int | None = None   # only platforms that share it (Roblox)
    collected_at: datetime            # when we fetched it (UTC)


class BaseCollector(ABC):
    platform: ClassVar[str]  # each child class sets this, e.g. "appstore"

    def __init__(self, settings: Settings, http: HttpClient):
        self.settings = settings
        self.http = http

    @property
    def platform_settings(self) -> PlatformSection:
        return self.settings.platforms.get(self.platform, PlatformSection())

    @abstractmethod
    def collect(self) -> list[GameRank]:
        """Fetch data from the platform and return it as a list of GameRank."""
