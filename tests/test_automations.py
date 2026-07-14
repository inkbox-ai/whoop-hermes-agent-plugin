from types import SimpleNamespace

import automations


def test_daily_recap_spec_targets_explicit_imessage(monkeypatch):
    monkeypatch.setattr(
        automations,
        "read_config",
        lambda: SimpleNamespace(home_channel="conversation-123", timezone="America/Los_Angeles"),
    )

    spec = automations.daily_recap_spec()

    assert spec["schedule"] == "0 23 * * *"
    assert spec["deliver"] == "inkbox:imessage:conversation-123"
    assert spec["script"] == "whoop_daily_recap.py"
    assert spec["no_agent"] is True


def test_delivery_target_preserves_explicit_prefixes():
    assert automations._delivery_target("imessage:abc") == "inkbox:imessage:abc"
    assert automations._delivery_target("inkbox:imessage:abc") == "inkbox:imessage:abc"
