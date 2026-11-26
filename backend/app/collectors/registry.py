"""
The list of all collectors the app knows about.

The name on the left must match the name under "platforms:" in config.yaml.
To add a new platform: import its class and add one line here.
"""
from __future__ import annotations

from app.collectors.appstore import AppStoreCollector
from app.collectors.base import BaseCollector

COLLECTORS: dict[str, type[BaseCollector]] = {
    "appstore": AppStoreCollector,
    # "playstore": PlayStoreCollector,   # Step 3
    # "roblox": RobloxCollector,         # Step 3
}
