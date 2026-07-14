"""Configuration loading for the WHOOP Hermes plugin."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_API_BASE_URL = "https://api.prod.whoop.com/developer"
DEFAULT_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
DEFAULT_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
DEFAULT_SCOPES = (
    "offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement"
)
DEFAULT_CALLBACK_PATH = "/integrations/whoop/oauth/callback"


def hermes_home() -> Path:
    return Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")).expanduser()


def _env_file_values(path: Path | None = None) -> dict[str, str]:
    target = path or hermes_home() / ".env"
    values: dict[str, str] = {}
    if not target.exists():
        return values
    for raw_line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(name: str, default: str = "") -> str:
    return os.getenv(name) or _env_file_values().get(name, default)


@dataclass(frozen=True)
class WhoopConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    api_base_url: str
    auth_url: str
    token_url: str
    home_channel: str
    timezone: str
    quiet_hours_start: str
    quiet_hours_end: str
    state_dir: Path

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def read_config() -> WhoopConfig:
    state_dir = Path(env_value("WHOOP_STATE_DIR", str(hermes_home() / "whoop"))).expanduser()
    return WhoopConfig(
        client_id=env_value("WHOOP_CLIENT_ID"),
        client_secret=env_value("WHOOP_CLIENT_SECRET"),
        redirect_uri=env_value("WHOOP_REDIRECT_URI"),
        scopes=env_value("WHOOP_SCOPES", DEFAULT_SCOPES),
        api_base_url=env_value("WHOOP_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
        auth_url=env_value("WHOOP_AUTH_URL", DEFAULT_AUTH_URL),
        token_url=env_value("WHOOP_TOKEN_URL", DEFAULT_TOKEN_URL),
        home_channel=env_value("WHOOP_HOME_CHANNEL") or env_value("INKBOX_HOME_CHANNEL"),
        timezone=env_value("WHOOP_TIMEZONE", "America/Los_Angeles"),
        quiet_hours_start=env_value("WHOOP_QUIET_HOURS_START", "23:00"),
        quiet_hours_end=env_value("WHOOP_QUIET_HOURS_END", "07:00"),
        state_dir=state_dir,
    )


def source_env(path: Path) -> dict[str, str]:
    return _env_file_values(path)
