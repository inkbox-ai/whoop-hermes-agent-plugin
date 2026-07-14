"""Official WHOOP Developer API client with automatic OAuth refresh."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .config import WhoopConfig, read_config, source_env
    from .store import TokenSet, TokenStore
except ImportError:  # pragma: no cover
    from config import WhoopConfig, read_config, source_env
    from store import TokenSet, TokenStore


class WhoopError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def _decode_response(raw: bytes) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw": raw.decode("utf-8", errors="replace")}


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    form: dict[str, Any] | None = None,
    timeout: float = 20,
) -> Any:
    body = urlencode({k: v for k, v in (form or {}).items() if v is not None}).encode() if form else None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if form is not None:
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            return _decode_response(response.read())
    except HTTPError as exc:
        payload = _decode_response(exc.read())
        message = payload.get("error_description") or payload.get("message") or payload.get("error")
        raise WhoopError(
            str(message or f"WHOOP returned HTTP {exc.code}"), status=exc.code, payload=payload
        ) from exc
    except URLError as exc:
        raise WhoopError(f"Unable to reach WHOOP: {exc.reason}") from exc


def _token_from_payload(payload: dict[str, Any], previous_refresh: str = "") -> TokenSet:
    access_token = str(payload.get("access_token") or "")
    refresh_token = str(payload.get("refresh_token") or previous_refresh)
    if not access_token or not refresh_token:
        raise WhoopError("WHOOP token response did not include usable access and refresh tokens")
    expires_in = float(payload.get("expires_in") or 3600)
    return TokenSet(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=time.time() + max(0, expires_in),
        scope=str(payload.get("scope") or ""),
        token_type=str(payload.get("token_type") or "bearer"),
    )


class WhoopClient:
    _refresh_lock = threading.Lock()

    def __init__(self, config: WhoopConfig | None = None):
        self.config = config or read_config()
        self.tokens = TokenStore(self.config.state_dir)

    def _fallback_tokens(self) -> dict[str, str]:
        return source_env(self.config.state_dir.parent / ".env")

    def current_tokens(self) -> TokenSet | None:
        return self.tokens.load(self._fallback_tokens())

    def exchange_code(self, code: str) -> TokenSet:
        payload = _request(
            "POST",
            self.config.token_url,
            form={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
            },
        )
        tokens = _token_from_payload(payload)
        self.tokens.save(tokens)
        return tokens

    def refresh(self, tokens: TokenSet | None = None) -> TokenSet:
        with self._refresh_lock:
            latest = self.current_tokens()
            if latest and not latest.needs_refresh and tokens is not None:
                return latest
            active = latest or tokens
            if not active or not active.refresh_token:
                raise WhoopError("WHOOP OAuth is not connected; run `hermes whoop setup`")
            payload = _request(
                "POST",
                self.config.token_url,
                form={
                    "grant_type": "refresh_token",
                    "refresh_token": active.refresh_token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": self.config.scopes,
                },
            )
            refreshed = _token_from_payload(payload, active.refresh_token)
            self.tokens.save(refreshed)
            return refreshed

    def _access_token(self) -> str:
        tokens = self.current_tokens()
        if not tokens:
            raise WhoopError("WHOOP OAuth is not connected; run `hermes whoop setup`")
        if tokens.needs_refresh:
            tokens = self.refresh(tokens)
        return tokens.access_token

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
        url = f"{self.config.api_base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        token = self._access_token()
        try:
            return _request("GET", url, headers={"Authorization": f"Bearer {token}"})
        except WhoopError as exc:
            if exc.status != 401:
                raise
            token = self.refresh().access_token
            return _request("GET", url, headers={"Authorization": f"Bearer {token}"})

    def delete(self, path: str) -> Any:
        url = f"{self.config.api_base_url}/{path.lstrip('/')}"
        token = self._access_token()
        return _request("DELETE", url, headers={"Authorization": f"Bearer {token}"})

    def collection(
        self,
        path: str,
        *,
        start: str = "",
        end: str = "",
        limit: int = 10,
        all_pages: bool = False,
        max_records: int = 100,
    ) -> dict[str, Any]:
        page_limit = max(1, min(int(limit or 10), 25))
        params: dict[str, Any] = {"limit": page_limit, "start": start, "end": end}
        records: list[dict[str, Any]] = []
        next_token = ""
        while True:
            if next_token:
                params["nextToken"] = next_token
            payload = self.get(path, params)
            records.extend(payload.get("records") or [])
            next_token = str(payload.get("next_token") or "")
            if not all_pages or not next_token or len(records) >= max_records:
                break
        return {"records": records[:max_records], "next_token": next_token or None}


def utc_iso(days_ago: int = 0) -> str:
    timestamp = time.time() - days_ago * 86400
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
