"""Hermes tools covering the official WHOOP end-user API."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

try:
    from .client import WhoopClient, WhoopError
    from .config import read_config
    from .store import EventStore
except ImportError:  # pragma: no cover
    from client import WhoopClient, WhoopError
    from config import read_config
    from store import EventStore


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _run(handler: Callable[[dict[str, Any]], Any], args: dict[str, Any]) -> str:
    try:
        return _json({"ok": True, "data": handler(args)})
    except WhoopError as exc:
        return _json({"ok": False, "error": str(exc), "status": exc.status})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


def _configured() -> bool:
    cfg = read_config()
    return cfg.configured and WhoopClient(cfg).current_tokens() is not None


def _collection_args(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": str(args.get("start") or ""),
        "end": str(args.get("end") or ""),
        "limit": int(args.get("limit") or 10),
        "all_pages": bool(args.get("all_pages", False)),
        "max_records": min(int(args.get("max_records") or 100), 500),
    }


def get_profile(_args: dict[str, Any]) -> Any:
    return WhoopClient().get("v2/user/profile/basic")


def get_body_measurements(_args: dict[str, Any]) -> Any:
    return WhoopClient().get("v2/user/measurement/body")


def list_cycles(args: dict[str, Any]) -> Any:
    return WhoopClient().collection("v2/cycle", **_collection_args(args))


def get_cycle(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v2/cycle/{int(args['cycle_id'])}")


def get_cycle_sleep(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v2/cycle/{int(args['cycle_id'])}/sleep")


def get_cycle_recovery(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v2/cycle/{int(args['cycle_id'])}/recovery")


def list_recoveries(args: dict[str, Any]) -> Any:
    return WhoopClient().collection("v2/recovery", **_collection_args(args))


def list_sleeps(args: dict[str, Any]) -> Any:
    return WhoopClient().collection("v2/activity/sleep", **_collection_args(args))


def get_sleep(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v2/activity/sleep/{str(args['sleep_id']).strip()}")


def list_workouts(args: dict[str, Any]) -> Any:
    return WhoopClient().collection("v2/activity/workout", **_collection_args(args))


def get_workout(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v2/activity/workout/{str(args['workout_id']).strip()}")


def map_activity_id(args: dict[str, Any]) -> Any:
    return WhoopClient().get(f"v1/activity-mapping/{int(args['v1_activity_id'])}")


def get_today(_args: dict[str, Any]) -> Any:
    client = WhoopClient()
    cycles = client.collection("v2/cycle", limit=3).get("records", [])
    recoveries = client.collection("v2/recovery", limit=3).get("records", [])
    sleeps = client.collection("v2/activity/sleep", limit=5).get("records", [])
    workouts = client.collection("v2/activity/workout", limit=10).get("records", [])
    cycle = cycles[0] if cycles else None
    cycle_start = str((cycle or {}).get("start") or "")
    return {
        "cycle": cycle,
        "recovery": recoveries[0] if recoveries else None,
        "sleeps": [row for row in sleeps if not cycle_start or str(row.get("end") or "") >= cycle_start],
        "workouts": [
            row for row in workouts if not cycle_start or str(row.get("start") or "") >= cycle_start
        ],
    }


def _score_values(records: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in records:
        score = row.get("score") if isinstance(row.get("score"), dict) else {}
        value = score.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _average(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def summarize_period(args: dict[str, Any]) -> Any:
    days = max(1, min(int(args.get("days") or 7), 90))
    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    query = {
        "start": start_dt.isoformat().replace("+00:00", "Z"),
        "end": end_dt.isoformat().replace("+00:00", "Z"),
        "limit": 25,
        "all_pages": True,
        "max_records": 500,
    }
    client = WhoopClient()
    cycles = client.collection("v2/cycle", **query)["records"]
    recoveries = client.collection("v2/recovery", **query)["records"]
    sleeps = client.collection("v2/activity/sleep", **query)["records"]
    workouts = client.collection("v2/activity/workout", **query)["records"]
    main_sleeps = [row for row in sleeps if not row.get("nap")]
    sleep_hours = []
    for row in main_sleeps:
        summary = (row.get("score") or {}).get("stage_summary") or {}
        value = summary.get("total_in_bed_time_milli")
        if isinstance(value, (int, float)):
            sleep_hours.append(float(value) / 3_600_000)
    return {
        "days": days,
        "counts": {
            "cycles": len(cycles),
            "recoveries": len(recoveries),
            "sleeps": len(main_sleeps),
            "naps": len(sleeps) - len(main_sleeps),
            "workouts": len(workouts),
        },
        "averages": {
            "recovery_score": _average(_score_values(recoveries, "recovery_score")),
            "resting_heart_rate": _average(_score_values(recoveries, "resting_heart_rate")),
            "hrv_rmssd_milli": _average(_score_values(recoveries, "hrv_rmssd_milli")),
            "day_strain": _average(_score_values(cycles, "strain")),
            "sleep_hours_in_bed": _average(sleep_hours),
            "sleep_performance": _average(_score_values(main_sleeps, "sleep_performance_percentage")),
        },
        "workout_sports": [str(row.get("sport_name") or "unknown") for row in workouts],
    }


def compare_workouts(args: dict[str, Any]) -> Any:
    sport = str(args.get("sport_name") or "").strip().lower()
    count = max(2, min(int(args.get("count") or 5), 20))
    records = WhoopClient().collection("v2/activity/workout", limit=25, all_pages=True, max_records=100)[
        "records"
    ]
    if sport:
        records = [row for row in records if str(row.get("sport_name") or "").lower() == sport]
    selected = records[:count]
    return {
        "sport_name": sport or None,
        "workouts": selected,
        "averages": {
            "strain": _average(_score_values(selected, "strain")),
            "average_heart_rate": _average(_score_values(selected, "average_heart_rate")),
            "max_heart_rate": _average(_score_values(selected, "max_heart_rate")),
            "distance_meter": _average(_score_values(selected, "distance_meter")),
        },
    }


def process_event(args: dict[str, Any]) -> Any:
    event_type = str(args.get("event_type") or args.get("type") or "").strip()
    resource_id = str(args.get("resource_id") or args.get("id") or "").strip()
    trace_id = str(args.get("trace_id") or "").strip()
    supported = {
        "workout.updated",
        "workout.deleted",
        "sleep.updated",
        "sleep.deleted",
        "recovery.updated",
        "recovery.deleted",
    }
    if event_type not in supported or not resource_id:
        raise ValueError("event_type and resource_id must describe a supported WHOOP webhook")
    store = EventStore(read_config().state_dir)
    if trace_id and store.seen(trace_id):
        return {"duplicate": True, "event_type": event_type, "resource_id": resource_id}

    version = ""
    if event_type.endswith(".deleted"):
        result: dict[str, Any] = {
            "event_type": event_type,
            "resource_id": resource_id,
            "deleted": True,
            "recommended_action": "Do not contact the user; update context silently.",
        }
    elif event_type == "workout.updated":
        workout = WhoopClient().get(f"v2/activity/workout/{resource_id}")
        version = str(workout.get("updated_at") or "")
        result = {
            "event_type": event_type,
            "resource_id": resource_id,
            "workout": workout,
            "recommended_action": (
                "If score_state is SCORED, send one concise workout recap with strain, average/max HR, "
                "and heart-rate-zone durations. Otherwise send nothing."
            ),
        }
    elif event_type == "sleep.updated":
        sleep = WhoopClient().get(f"v2/activity/sleep/{resource_id}")
        version = str(sleep.get("updated_at") or "")
        result = {
            "event_type": event_type,
            "resource_id": resource_id,
            "sleep": sleep,
            "recommended_action": (
                "Usually send nothing yet; recovery.updated normally follows and should produce the combined briefing."
            ),
        }
    else:
        recoveries = WhoopClient().collection("v2/recovery", limit=25)["records"]
        recovery = next((row for row in recoveries if str(row.get("sleep_id")) == resource_id), None)
        sleep = WhoopClient().get(f"v2/activity/sleep/{resource_id}")
        version = str((recovery or {}).get("updated_at") or sleep.get("updated_at") or "")
        result = {
            "event_type": event_type,
            "resource_id": resource_id,
            "recovery": recovery,
            "sleep": sleep,
            "recommended_action": (
                "When both records are scored, send one morning briefing covering Recovery, HRV, resting HR, "
                "sleep performance, sleep need, and a conservative training suggestion."
            ),
        }
    if version and store.seen_version(event_type, resource_id, version):
        store.mark(trace_id, event_type, resource_id)
        return {
            "duplicate": True,
            "event_type": event_type,
            "resource_id": resource_id,
            "reason": "This resource version was already processed.",
        }
    cfg = read_config()
    try:
        local_now = datetime.now(ZoneInfo(cfg.timezone))
    except Exception:
        local_now = datetime.now(timezone.utc)
    current = local_now.strftime("%H:%M")
    start, end = cfg.quiet_hours_start, cfg.quiet_hours_end
    in_quiet_hours = (current >= start or current < end) if start > end else start <= current < end
    result["outreach_policy"] = {
        "home_channel": cfg.home_channel or None,
        "timezone": cfg.timezone,
        "quiet_hours": {"start": start, "end": end},
        "currently_quiet": in_quiet_hours,
        "may_message_now": bool(cfg.home_channel and not in_quiet_hours),
        "may_call_from_webhook": False,
    }
    store.mark_version(event_type, resource_id, version)
    store.mark(trace_id, event_type, resource_id)
    return result


EMPTY_SCHEMA = {"type": "object", "properties": {}}
COLLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "Inclusive ISO-8601 start time."},
        "end": {"type": "string", "description": "Exclusive ISO-8601 end time."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 25},
        "all_pages": {"type": "boolean", "default": False},
        "max_records": {"type": "integer", "minimum": 1, "maximum": 500},
    },
}


def _schema(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "description": description, "parameters": parameters}


TOOL_DEFINITIONS: tuple[tuple[str, dict[str, Any], Callable[[dict[str, Any]], Any]], ...] = (
    (
        "whoop_get_profile",
        _schema("whoop_get_profile", "Get the authenticated WHOOP member profile.", EMPTY_SCHEMA),
        get_profile,
    ),
    (
        "whoop_get_body_measurements",
        _schema(
            "whoop_get_body_measurements", "Get height, weight, and configured max heart rate.", EMPTY_SCHEMA
        ),
        get_body_measurements,
    ),
    (
        "whoop_list_cycles",
        _schema(
            "whoop_list_cycles",
            "List physiological cycles with day Strain and aggregate heart rate.",
            COLLECTION_SCHEMA,
        ),
        list_cycles,
    ),
    (
        "whoop_get_cycle",
        _schema(
            "whoop_get_cycle",
            "Get one physiological cycle by numeric ID.",
            {"type": "object", "properties": {"cycle_id": {"type": "integer"}}, "required": ["cycle_id"]},
        ),
        get_cycle,
    ),
    (
        "whoop_get_cycle_sleep",
        _schema(
            "whoop_get_cycle_sleep",
            "Get the sleep associated with a cycle.",
            {"type": "object", "properties": {"cycle_id": {"type": "integer"}}, "required": ["cycle_id"]},
        ),
        get_cycle_sleep,
    ),
    (
        "whoop_get_cycle_recovery",
        _schema(
            "whoop_get_cycle_recovery",
            "Get the recovery associated with a cycle.",
            {"type": "object", "properties": {"cycle_id": {"type": "integer"}}, "required": ["cycle_id"]},
        ),
        get_cycle_recovery,
    ),
    (
        "whoop_list_recoveries",
        _schema(
            "whoop_list_recoveries",
            "List Recovery scores, HRV, resting HR, SpO2, and skin temperature.",
            COLLECTION_SCHEMA,
        ),
        list_recoveries,
    ),
    (
        "whoop_list_sleeps",
        _schema(
            "whoop_list_sleeps", "List sleeps and naps with stage totals and sleep scores.", COLLECTION_SCHEMA
        ),
        list_sleeps,
    ),
    (
        "whoop_get_sleep",
        _schema(
            "whoop_get_sleep",
            "Get one sleep or nap by UUID.",
            {"type": "object", "properties": {"sleep_id": {"type": "string"}}, "required": ["sleep_id"]},
        ),
        get_sleep,
    ),
    (
        "whoop_list_workouts",
        _schema(
            "whoop_list_workouts",
            "List workouts with Strain, heart rate, energy, distance, altitude, and HR-zone durations.",
            COLLECTION_SCHEMA,
        ),
        list_workouts,
    ),
    (
        "whoop_get_workout",
        _schema(
            "whoop_get_workout",
            "Get one workout by UUID.",
            {"type": "object", "properties": {"workout_id": {"type": "string"}}, "required": ["workout_id"]},
        ),
        get_workout,
    ),
    (
        "whoop_map_activity_id",
        _schema(
            "whoop_map_activity_id",
            "Map a legacy v1 activity ID to its v2 UUID.",
            {
                "type": "object",
                "properties": {"v1_activity_id": {"type": "integer"}},
                "required": ["v1_activity_id"],
            },
        ),
        map_activity_id,
    ),
    (
        "whoop_get_today",
        _schema(
            "whoop_get_today",
            "Get the current cycle, latest Recovery, sleeps, naps, and workouts as one snapshot.",
            EMPTY_SCHEMA,
        ),
        get_today,
    ),
    (
        "whoop_summarize_period",
        _schema(
            "whoop_summarize_period",
            "Calculate a compact WHOOP summary for the last N days.",
            {"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}}},
        ),
        summarize_period,
    ),
    (
        "whoop_compare_workouts",
        _schema(
            "whoop_compare_workouts",
            "Compare recent workouts, optionally restricted to one sport.",
            {
                "type": "object",
                "properties": {
                    "sport_name": {"type": "string"},
                    "count": {"type": "integer", "minimum": 2, "maximum": 20},
                },
            },
        ),
        compare_workouts,
    ),
    (
        "whoop_process_event",
        _schema(
            "whoop_process_event",
            "Resolve a verified WHOOP webhook into current API data and an idempotent coaching action.",
            {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "workout.updated",
                            "workout.deleted",
                            "sleep.updated",
                            "sleep.deleted",
                            "recovery.updated",
                            "recovery.deleted",
                        ],
                    },
                    "resource_id": {"type": "string"},
                    "trace_id": {"type": "string"},
                },
                "required": ["event_type", "resource_id", "trace_id"],
            },
        ),
        process_event,
    ),
)


def register_tools(ctx: Any) -> None:
    for name, schema, handler in TOOL_DEFINITIONS:
        ctx.register_tool(
            name=name,
            toolset="whoop",
            schema=schema,
            handler=lambda args, _handler=handler, **kwargs: _run(_handler, args),
            check_fn=_configured,
        )
