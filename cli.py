"""`hermes whoop` commands."""

from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

try:
    from .automations import automation_status, install_automations, remove_automations
    from .client import WhoopClient
    from .config import DEFAULT_CALLBACK_PATH, hermes_home, read_config, source_env
    from .oauth import create_authorization_url
    from .store import TokenSet, TokenStore
except ImportError:  # pragma: no cover
    from automations import automation_status, install_automations, remove_automations
    from client import WhoopClient
    from config import DEFAULT_CALLBACK_PATH, hermes_home, read_config, source_env
    from oauth import create_authorization_url
    from store import TokenSet, TokenStore


IMPORT_NAMES = (
    "WHOOP_CLIENT_ID",
    "WHOOP_CLIENT_SECRET",
    "WHOOP_REDIRECT_URI",
    "WHOOP_SCOPES",
    "WHOOP_API_BASE_URL",
    "WHOOP_AUTH_URL",
    "WHOOP_TOKEN_URL",
    "WHOOP_TIMEZONE",
    "WHOOP_HOME_CHANNEL",
    "WHOOP_RECAPS_RESPECT_QUIET_HOURS",
)


def _save_env(name: str, value: str) -> None:
    if not value:
        return
    try:
        from hermes_cli.config import save_env_value

        save_env_value(name, value)
        return
    except Exception:
        pass
    home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    home.mkdir(parents=True, exist_ok=True)
    path = home / ".env"
    rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"{name}={value}"
    for index, row in enumerate(rows):
        if row.split("=", 1)[0].strip() == name:
            rows[index] = replacement
            break
    else:
        rows.append(replacement)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _ensure_visual_dependency() -> None:
    """Install Pillow into the Python environment that is running Hermes."""
    if importlib.util.find_spec("PIL") is not None:
        return
    print("Installing WHOOP visual-report dependency into the Hermes environment...")
    uv = shutil.which("uv")
    command = (
        [uv, "pip", "install", "--python", sys.executable, "Pillow>=10"]
        if uv
        else [sys.executable, "-m", "pip", "install", "Pillow>=10"]
    )
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "Could not install Pillow>=10. Install it in the Hermes Python environment and rerun setup."
        ) from exc


def _active_imessage_conversations() -> list[dict]:
    """Read active Inkbox iMessage conversations from the already-loaded companion plugin."""
    module = sys.modules.get("hermes_plugins.inkbox.tools")
    list_conversations = getattr(module, "inkbox_list_imessage_conversations", None)
    if not callable(list_conversations):
        return []
    try:
        payload = json.loads(list_conversations({"limit": 100}))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [
        row
        for row in payload.get("conversations", [])
        if isinstance(row, dict) and row.get("id") and row.get("assignment_status") == "active"
    ]


def _configure_home_channel(explicit: str = "") -> str:
    selected = str(explicit or "").strip()
    if selected:
        _save_env("WHOOP_HOME_CHANNEL", selected)
        return selected
    existing = read_config().home_channel
    if existing:
        return existing
    conversations = _active_imessage_conversations()
    if len(conversations) == 1:
        selected = str(conversations[0]["id"])
        _save_env("WHOOP_HOME_CHANNEL", selected)
        print(f"Using the sole active Inkbox iMessage conversation as WHOOP_HOME_CHANNEL: {selected}")
        return selected
    if len(conversations) > 1:
        options = ", ".join(str(row["id"]) for row in conversations)
        print(f"Multiple active iMessage conversations found: {options}")
        print("Rerun with --home-channel <conversation-id> to choose proactive delivery.")
    else:
        print("No active Inkbox iMessage conversation found; OAuth can continue without outreach.")
        print("Connect/message the Inkbox identity, then rerun setup with --home-channel <conversation-id>.")
    return ""


def _public_url() -> str:
    env = source_env(hermes_home() / ".env")
    configured = env.get("INKBOX_PUBLIC_URL", "").rstrip("/")
    if configured:
        return configured
    state_path = hermes_home() / "inkbox_identity_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            public_url = str(state.get("public_url") or "").strip().rstrip("/")
            if public_url:
                return public_url
            host = str(state.get("tunnel_public_host") or "").strip()
            if host:
                return f"https://{host}"
        except (OSError, json.JSONDecodeError):
            pass
    return ""


def _import_existing(path: Path) -> dict[str, str]:
    values = source_env(path)
    for name in IMPORT_NAMES:
        _save_env(name, values.get(name, ""))
    secret = values.get("WHOOP_CLIENT_SECRET", "")
    if secret:
        _save_env("INKBOX_WEBHOOK_SECRET_WHOOP", secret)
    if values.get("WHOOP_ACCESS_TOKEN") or values.get("WHOOP_REFRESH_TOKEN"):
        cfg = read_config()
        tokens = TokenSet(
            access_token=values.get("WHOOP_ACCESS_TOKEN", ""),
            refresh_token=values.get("WHOOP_REFRESH_TOKEN", ""),
            expires_at=float(values.get("WHOOP_TOKEN_EXPIRES_AT") or 0),
            scope=values.get("WHOOP_SCOPES", ""),
        )
        TokenStore(cfg.state_dir).save(tokens)
    return values


def _urls() -> dict[str, str]:
    public = _public_url()
    return {
        "public_url": public,
        "redirect_uri": f"{public}{DEFAULT_CALLBACK_PATH}" if public else "",
        "webhook_url": f"{public}/webhook" if public else "",
    }


def doctor() -> dict:
    cfg = read_config()
    urls = _urls()
    tokens = WhoopClient(cfg).current_tokens()
    result = {
        "configured": cfg.configured,
        "redirect_uri": cfg.redirect_uri,
        "expected_redirect_uri": urls["redirect_uri"],
        "webhook_url": urls["webhook_url"],
        "tokens_present": bool(tokens and tokens.usable),
        "token_expired": bool(tokens and tokens.needs_refresh),
        "home_channel_configured": bool(cfg.home_channel),
        "timezone": cfg.timezone,
        "profile": None,
        "errors": [],
    }
    if not cfg.configured:
        result["errors"].append("WHOOP client credentials are missing")
    if not urls["public_url"]:
        result["errors"].append("Inkbox tunnel public URL is unavailable; restart the gateway")
    if cfg.redirect_uri and urls["redirect_uri"] and cfg.redirect_uri != urls["redirect_uri"]:
        result["errors"].append("WHOOP_REDIRECT_URI does not match the active Inkbox tunnel")
    if tokens and cfg.configured:
        try:
            result["profile"] = WhoopClient(cfg).get("v2/user/profile/basic")
        except Exception as exc:
            result["errors"].append(str(exc))
    result["ok"] = not result["errors"]
    return result


def setup_argparse(subparser) -> None:
    subs = subparser.add_subparsers(dest="whoop_command")
    setup = subs.add_parser("setup", help="Import credentials or start WHOOP OAuth")
    setup.add_argument("--import-env", type=Path, help="Import existing WHOOP values from an env file")
    setup.add_argument("--home-channel", help="Inkbox contact or iMessage conversation for outreach")
    setup.add_argument("--no-browser", action="store_true", help="Print the OAuth URL without opening it")
    subs.add_parser("doctor", help="Validate WHOOP, OAuth, tunnel, and API readiness")
    subs.add_parser("status", help="Show non-secret WHOOP integration status")
    subs.add_parser("webhook-url", help="Print the v2 WHOOP webhook URL")
    automations = subs.add_parser("automations", help="Manage WHOOP recap automations")
    automations.add_argument(
        "action", choices=("install", "status", "remove"), nargs="?", default="status"
    )
    disconnect = subs.add_parser("disconnect", help="Revoke WHOOP access and remove local tokens")
    disconnect.add_argument("--yes", action="store_true", help="Skip confirmation")
    subparser.set_defaults(func=handle_cli)


def _setup(args) -> None:
    _ensure_visual_dependency()
    if args.import_env:
        if not args.import_env.exists():
            raise SystemExit(f"Import file does not exist: {args.import_env}")
        _import_existing(args.import_env)
    _configure_home_channel(str(args.home_channel or ""))
    urls = _urls()
    cfg = read_config()
    if urls["redirect_uri"] and cfg.redirect_uri != urls["redirect_uri"]:
        _save_env("WHOOP_REDIRECT_URI", urls["redirect_uri"])
        cfg = read_config()
    if cfg.client_secret:
        _save_env("INKBOX_WEBHOOK_SECRET_WHOOP", cfg.client_secret)
    print(json.dumps({"redirect_uri": cfg.redirect_uri, "webhook_url": urls["webhook_url"]}, indent=2))
    tokens = WhoopClient(cfg).current_tokens()
    if tokens and tokens.usable:
        try:
            profile = WhoopClient(cfg).get("v2/user/profile/basic")
            print(json.dumps({"connected": True, "profile": profile}, indent=2))
            return
        except Exception as exc:
            print(f"Existing token needs authorization or refresh: {exc}")
    url = create_authorization_url()
    print("Open this URL to connect WHOOP:\n")
    print(url)
    if not args.no_browser:
        webbrowser.open(url)
    print("\nThe running Hermes gateway will store the tokens when WHOOP redirects back.")


def _disconnect(skip_confirmation: bool) -> None:
    if not skip_confirmation:
        answer = input("Revoke WHOOP OAuth access and delete local tokens? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled")
            return
    cfg = read_config()
    try:
        WhoopClient(cfg).delete("v2/user/access")
    finally:
        TokenStore(cfg.state_dir).path.unlink(missing_ok=True)
    print("WHOOP disconnected")


def handle_cli(args) -> None:
    command = getattr(args, "whoop_command", None)
    if command == "setup":
        _setup(args)
    elif command in {"doctor", "status"}:
        print(json.dumps(doctor(), indent=2, default=str))
    elif command == "webhook-url":
        print(json.dumps({**_urls(), "model_version": "v2"}, indent=2))
    elif command == "disconnect":
        _disconnect(bool(args.yes))
    elif command == "automations":
        action = getattr(args, "action", "status")
        result = {
            "install": install_automations,
            "status": automation_status,
            "remove": remove_automations,
        }[action]()
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: hermes whoop <setup|doctor|status|webhook-url|automations|disconnect>")
