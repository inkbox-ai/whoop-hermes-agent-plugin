import json
import sys
from types import SimpleNamespace

import cli


def test_public_url_reads_current_inkbox_identity_state(monkeypatch, tmp_path):
    (tmp_path / "inkbox_identity_state.json").write_text(
        json.dumps({"public_url": "https://whoop.inkboxwire.com"})
    )
    monkeypatch.setattr(cli, "hermes_home", lambda: tmp_path)

    assert cli._public_url() == "https://whoop.inkboxwire.com"
    assert cli._urls()["webhook_url"] == "https://whoop.inkboxwire.com/webhook"


def test_setup_auto_selects_sole_active_imessage_conversation(monkeypatch):
    module = SimpleNamespace(
        inkbox_list_imessage_conversations=lambda _args: json.dumps(
            {
                "ok": True,
                "conversations": [
                    {
                        "id": "conversation-123",
                        "assignment_status": "active",
                    }
                ],
            }
        )
    )
    monkeypatch.setitem(sys.modules, "hermes_plugins.inkbox.tools", module)
    monkeypatch.setattr(cli, "read_config", lambda: SimpleNamespace(home_channel=""))
    saved = {}
    monkeypatch.setattr(cli, "_save_env", lambda name, value: saved.update({name: value}))

    selected = cli._configure_home_channel()

    assert selected == "conversation-123"
    assert saved == {"WHOOP_HOME_CHANNEL": "conversation-123"}


def test_visual_dependency_is_noop_when_pillow_exists(monkeypatch):
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not install")),
    )

    cli._ensure_visual_dependency()
