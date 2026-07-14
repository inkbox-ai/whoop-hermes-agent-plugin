import time
from pathlib import Path

import client as client_mod
from client import WhoopClient
from config import WhoopConfig
from store import TokenSet, TokenStore


def _config(tmp_path: Path) -> WhoopConfig:
    return WhoopConfig(
        client_id="client",
        client_secret="secret",
        redirect_uri="https://agent/callback",
        scopes="offline read:workout",
        api_base_url="https://api.example/developer",
        auth_url="https://api.example/auth",
        token_url="https://api.example/token",
        home_channel="contact",
        timezone="UTC",
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
        state_dir=tmp_path / "whoop",
    )


def test_expired_token_refreshes_before_get(monkeypatch, tmp_path):
    cfg = _config(tmp_path)
    TokenStore(cfg.state_dir).save(TokenSet("old", "refresh", time.time() - 1))
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/token"):
            return {"access_token": "new", "refresh_token": "new-refresh", "expires_in": 3600}
        return {"user_id": 1}

    monkeypatch.setattr(client_mod, "_request", fake_request)

    assert WhoopClient(cfg).get("v2/user/profile/basic") == {"user_id": 1}
    assert calls[0][0] == "POST"
    assert calls[1][2]["headers"]["Authorization"] == "Bearer new"


def test_collection_follows_next_token(monkeypatch, tmp_path):
    client = WhoopClient(_config(tmp_path))
    pages = [
        {"records": [{"id": 1}], "next_token": "next"},
        {"records": [{"id": 2}], "next_token": None},
    ]
    monkeypatch.setattr(client, "get", lambda path, params: pages.pop(0))

    result = client.collection("v2/cycle", all_pages=True, limit=25)
    assert [row["id"] for row in result["records"]] == [1, 2]
