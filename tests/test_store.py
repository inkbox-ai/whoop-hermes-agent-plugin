import json
import stat
import time

from store import EventStore, TokenSet, TokenStore


def test_token_store_is_atomic_and_private(tmp_path):
    store = TokenStore(tmp_path / "whoop")
    tokens = TokenSet("access", "refresh", time.time() + 3600, "offline")

    store.save(tokens)

    assert store.load() == tokens
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert json.loads(store.path.read_text())["access_token"] == "access"


def test_token_store_imports_environment_fallback(tmp_path):
    store = TokenStore(tmp_path / "whoop")
    tokens = store.load(
        {
            "WHOOP_ACCESS_TOKEN": "a",
            "WHOOP_REFRESH_TOKEN": "r",
            "WHOOP_TOKEN_EXPIRES_AT": "123",
            "WHOOP_SCOPES": "offline",
        }
    )
    assert tokens.access_token == "a"
    assert tokens.refresh_token == "r"
    assert tokens.expires_at == 123


def test_event_store_deduplicates_trace_ids(tmp_path):
    store = EventStore(tmp_path / "whoop")
    assert not store.seen("trace")
    store.mark("trace", "workout.updated", "workout")
    assert store.seen("trace")
    assert not store.seen_version("workout.updated", "workout", "v1")
    store.mark_version("workout.updated", "workout", "v1")
    assert store.seen_version("workout.updated", "workout", "v1")
    assert store.claim_outreach("workout_recap", "workout") is True
    assert store.claim_outreach("workout_recap", "workout") is False
