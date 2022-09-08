from __future__ import annotations

import argparse
import json
from typing import Any

import ustvgo_iptv

from .paths import config_path


def save_settings(settings: dict[str, Any]) -> None:
    """Save user settings."""
    settings_path = config_path() / 'settings.cfg'
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open('w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)


def load_settings() -> dict[str, Any]:
    """Load user settings."""
    settings = default_settings()
    settings_path = config_path() / 'settings.cfg'
    if settings_path.is_file():
        try:
            user_settings = json.loads(settings_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            user_settings = {}

        settings = {**settings, **user_settings}
    else:
        save_settings(settings)

    return settings


def default_settings() -> dict[str, Any]:
    """Get default settings."""
    parser = ustvgo_iptv.args_parser()
    return {x.dest: x.default for x in parser._actions
            if x.default != argparse.SUPPRESS
            and x.dest != argparse.SUPPRESS}
