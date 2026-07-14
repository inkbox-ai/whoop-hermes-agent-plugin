"""Protected token storage and durable webhook idempotency."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: float
    scope: str = ""
    token_type: str = "bearer"

    @property
    def usable(self) -> bool:
        return bool(self.access_token and self.refresh_token)

    @property
    def needs_refresh(self) -> bool:
        return not self.access_token or self.expires_at <= time.time() + 60


def _parse_expiry(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class TokenStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.path = state_dir / "tokens.json"

    def load(self, fallback: dict[str, str] | None = None) -> TokenSet | None:
        payload: dict[str, Any] = {}
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
        if not payload and fallback:
            payload = {
                "access_token": fallback.get("WHOOP_ACCESS_TOKEN", ""),
                "refresh_token": fallback.get("WHOOP_REFRESH_TOKEN", ""),
                "expires_at": fallback.get("WHOOP_TOKEN_EXPIRES_AT", "0"),
                "scope": fallback.get("WHOOP_SCOPES", ""),
                "token_type": "bearer",
            }
        if not payload.get("access_token") and not payload.get("refresh_token"):
            return None
        return TokenSet(
            access_token=str(payload.get("access_token") or ""),
            refresh_token=str(payload.get("refresh_token") or ""),
            expires_at=_parse_expiry(payload.get("expires_at")),
            scope=str(payload.get("scope") or ""),
            token_type=str(payload.get("token_type") or "bearer"),
        )

    def save(self, tokens: TokenSet) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        fd, temp_name = tempfile.mkstemp(prefix="tokens.", suffix=".tmp", dir=self.state_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(tokens), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


class EventStore:
    def __init__(self, state_dir: Path):
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = state_dir / "state.db"
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "trace_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, resource_id TEXT NOT NULL, "
                "processed_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS resource_versions ("
                "event_type TEXT NOT NULL, resource_id TEXT NOT NULL, version TEXT NOT NULL, "
                "processed_at REAL NOT NULL, PRIMARY KEY(event_type, resource_id, version))"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return db

    def seen(self, trace_id: str) -> bool:
        if not trace_id:
            return False
        with self._connect() as db:
            row = db.execute("SELECT 1 FROM events WHERE trace_id = ?", (trace_id,)).fetchone()
        return row is not None

    def mark(self, trace_id: str, event_type: str, resource_id: str) -> None:
        if not trace_id:
            return
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO events(trace_id,event_type,resource_id,processed_at) VALUES(?,?,?,?)",
                (trace_id, event_type, resource_id, time.time()),
            )
            db.execute("DELETE FROM events WHERE processed_at < ?", (time.time() - 30 * 86400,))

    def seen_version(self, event_type: str, resource_id: str, version: str) -> bool:
        if not version:
            return False
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM resource_versions WHERE event_type=? AND resource_id=? AND version=?",
                (event_type, resource_id, version),
            ).fetchone()
        return row is not None

    def mark_version(self, event_type: str, resource_id: str, version: str) -> None:
        if not version:
            return
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO resource_versions(event_type,resource_id,version,processed_at) "
                "VALUES(?,?,?,?)",
                (event_type, resource_id, version, time.time()),
            )
            db.execute(
                "DELETE FROM resource_versions WHERE processed_at < ?",
                (time.time() - 90 * 86400,),
            )
