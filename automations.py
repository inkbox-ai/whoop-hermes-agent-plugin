"""Install and manage the WHOOP plugin's durable Hermes automations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

try:
    from .config import hermes_home, read_config
except ImportError:  # pragma: no cover
    from config import hermes_home, read_config


DAILY_RECAP_JOB_NAME = "WHOOP Daily Visual Recap"
DAILY_RECAP_SCHEDULE = "0 23 * * *"
DAILY_RECAP_SCRIPT_NAME = "whoop_daily_recap.py"


def _delivery_target(home_channel: str) -> str:
    """Return an explicit Inkbox iMessage cron target."""
    value = str(home_channel or "").strip()
    if not value:
        raise ValueError(
            "WHOOP_HOME_CHANNEL is required. Set it to the Inkbox iMessage conversation ID first."
        )
    if value.startswith("inkbox:"):
        return value
    if value.startswith("imessage:"):
        return f"inkbox:{value}"
    return f"inkbox:imessage:{value}"


def daily_recap_spec() -> dict[str, Any]:
    cfg = read_config()
    return {
        "name": DAILY_RECAP_JOB_NAME,
        "prompt": "",
        "schedule": DAILY_RECAP_SCHEDULE,
        "deliver": _delivery_target(cfg.home_channel),
        "script": DAILY_RECAP_SCRIPT_NAME,
        "no_agent": True,
    }


def _install_script() -> Path:
    source = Path(__file__).parent / "scripts" / DAILY_RECAP_SCRIPT_NAME
    if not source.is_file():
        raise RuntimeError(f"Bundled WHOOP cron script is missing: {source}")
    destination_dir = hermes_home() / "scripts"
    destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = destination_dir / DAILY_RECAP_SCRIPT_NAME
    shutil.copy2(source, destination)
    destination.chmod(0o700)
    return destination


def _configure_cron_runtime() -> None:
    """Use WHOOP's timezone and suppress Hermes' extra cron wrapper bubble."""
    from hermes_cli.config import load_config, save_config, save_env_value
    import hermes_time

    cfg = read_config()
    config = load_config()
    config["timezone"] = cfg.timezone
    cron = config.setdefault("cron", {})
    cron["wrap_response"] = False
    save_config(config)
    save_env_value("WHOOP_RECAPS_RESPECT_QUIET_HOURS", "false")
    reset_cache = getattr(hermes_time, "reset_cache", None)
    if callable(reset_cache):
        reset_cache()
    else:  # Hermes versions before reset_cache was exposed.
        hermes_time._cached_tz = None
        hermes_time._cached_tz_name = None
        hermes_time._cache_resolved = False


def install_automations() -> dict[str, Any]:
    """Idempotently install/update the daily recap cron job."""
    from cron.jobs import create_job, list_jobs, update_job

    script_path = _install_script()
    _configure_cron_runtime()
    spec = daily_recap_spec()
    matches = [job for job in list_jobs(include_disabled=True) if job.get("name") == DAILY_RECAP_JOB_NAME]
    if matches:
        job = update_job(
            matches[0]["id"],
            {
                **spec,
                "enabled": True,
                "state": "scheduled",
                "paused_at": None,
                "paused_reason": None,
            },
        )
        action = "updated"
    else:
        job = create_job(**spec)
        action = "created"
    return {
        "ok": True,
        "action": action,
        "job": job,
        "script": str(script_path),
        "timezone": read_config().timezone,
        "workout_recap": "webhook: workout.updated",
        "sleep_recap": "webhook: recovery.updated",
    }


def automation_status() -> dict[str, Any]:
    from cron.jobs import list_jobs

    jobs = [job for job in list_jobs(include_disabled=True) if job.get("name") == DAILY_RECAP_JOB_NAME]
    return {
        "installed": bool(jobs),
        "jobs": jobs,
        "timezone": read_config().timezone,
        "workout_recap": "webhook: workout.updated",
        "sleep_recap": "webhook: recovery.updated",
    }


def remove_automations() -> dict[str, Any]:
    from cron.jobs import list_jobs, remove_job

    jobs = [job for job in list_jobs(include_disabled=True) if job.get("name") == DAILY_RECAP_JOB_NAME]
    removed = [job["id"] for job in jobs if remove_job(job["id"])]
    script = hermes_home() / "scripts" / DAILY_RECAP_SCRIPT_NAME
    script.unlink(missing_ok=True)
    return {"ok": True, "removed_job_ids": removed, "removed_script": str(script)}
