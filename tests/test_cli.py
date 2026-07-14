import json

import cli


def test_public_url_reads_current_inkbox_identity_state(monkeypatch, tmp_path):
    (tmp_path / "inkbox_identity_state.json").write_text(
        json.dumps({"public_url": "https://whoop.inkboxwire.com"})
    )
    monkeypatch.setattr(cli, "hermes_home", lambda: tmp_path)

    assert cli._public_url() == "https://whoop.inkboxwire.com"
    assert cli._urls()["webhook_url"] == "https://whoop.inkboxwire.com/webhook"
