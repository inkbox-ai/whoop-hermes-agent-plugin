"""OAuth authorization state and callback handler mounted on the Inkbox tunnel."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from aiohttp import web

try:
    from .client import WhoopClient
    from .config import DEFAULT_CALLBACK_PATH, read_config
except ImportError:  # pragma: no cover
    from client import WhoopClient
    from config import DEFAULT_CALLBACK_PATH, read_config


def _pending_path() -> Path:
    return read_config().state_dir / "oauth-pending.json"


def create_authorization_url() -> str:
    cfg = read_config()
    if not cfg.configured or not cfg.redirect_uri:
        raise RuntimeError("WHOOP client ID, secret, and redirect URI must be configured first")
    cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = secrets.token_urlsafe(32)
    pending = {"state": state, "created_at": time.time(), "redirect_uri": cfg.redirect_uri}
    path = _pending_path()
    path.write_text(json.dumps(pending), encoding="utf-8")
    path.chmod(0o600)
    query = urlencode(
        {
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "response_type": "code",
            "scope": cfg.scopes,
            "state": state,
        }
    )
    return f"{cfg.auth_url}?{query}"


def _load_pending() -> dict:
    path = _pending_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


async def oauth_callback(request: web.Request) -> web.Response:
    error = str(request.query.get("error") or "")
    if error:
        description = str(request.query.get("error_description") or error)
        return web.Response(status=400, text=f"WHOOP authorization failed: {description}")
    code = str(request.query.get("code") or "")
    state = str(request.query.get("state") or "")
    pending = _load_pending()
    created_at = float(pending.get("created_at") or 0)
    if not code or not state or not secrets.compare_digest(state, str(pending.get("state") or "")):
        return web.Response(status=400, text="Invalid or missing WHOOP OAuth state")
    if created_at < time.time() - 900:
        return web.Response(status=400, text="WHOOP OAuth state expired; run setup again")
    try:
        await asyncio.to_thread(WhoopClient().exchange_code, code)
    except Exception as exc:
        return web.Response(status=502, text=f"WHOOP token exchange failed: {exc}")
    try:
        _pending_path().unlink(missing_ok=True)
    except OSError:
        pass
    return web.Response(
        status=200,
        content_type="text/html",
        text=(
            "<!doctype html><title>WHOOP connected</title>"
            "<h1>WHOOP connected</h1><p>You can close this tab and return to Hermes.</p>"
        ),
    )


def register_route(inkbox_plugin) -> None:
    register = getattr(inkbox_plugin, "register_http_route", None)
    if not callable(register):
        raise RuntimeError(
            "The installed Inkbox Hermes plugin does not expose tunnel route registration; update it first."
        )
    register("GET", DEFAULT_CALLBACK_PATH, oauth_callback)
