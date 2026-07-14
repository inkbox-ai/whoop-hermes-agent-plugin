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
    from .visuals import local_datetime_label, render_report_data
except ImportError:  # pragma: no cover
    from client import WhoopClient, WhoopError
    from config import read_config
    from store import EventStore
    from visuals import local_datetime_label, render_report_data


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


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _duration_seconds(record: dict[str, Any]) -> float:
    start = _parse_timestamp(record.get("start"))
    end = _parse_timestamp(record.get("end"))
    return max(0.0, (end - start).total_seconds()) if start and end else 0.0


def _sleep_phases(sleep: dict[str, Any]) -> list[dict[str, Any]]:
    stage = ((sleep.get("score") or {}).get("stage_summary") or {})
    return [
        {"label": "Light", "milliseconds": _value_number(stage, "total_light_sleep_time_milli")},
        {"label": "Deep", "milliseconds": _value_number(stage, "total_slow_wave_sleep_time_milli")},
        {"label": "REM", "milliseconds": _value_number(stage, "total_rem_sleep_time_milli")},
        {"label": "Awake", "milliseconds": _value_number(stage, "total_awake_time_milli")},
    ]


def _value_number(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key)
    return float(value) if isinstance(value, (int, float)) else default


def _normalize_sleep(sleep: dict[str, Any], recovery: dict[str, Any] | None) -> dict[str, Any]:
    if sleep.get("score_state") not in (None, "SCORED"):
        raise ValueError("The selected WHOOP sleep is not scored yet")
    sleep_score = sleep.get("score") if isinstance(sleep.get("score"), dict) else {}
    recovery_score = (
        recovery.get("score") if isinstance((recovery or {}).get("score"), dict) else {}
    )
    stage = sleep_score.get("stage_summary") if isinstance(sleep_score.get("stage_summary"), dict) else {}
    phases = _sleep_phases(sleep)
    total_in_bed = _value_number(stage, "total_in_bed_time_milli")
    if not total_in_bed:
        total_in_bed = sum(row["milliseconds"] for row in phases)
    return {
        "sleep_id": str(sleep.get("id") or ""),
        "total_in_bed_milli": total_in_bed,
        "sleep_efficiency": _value_number(sleep_score, "sleep_efficiency_percentage"),
        "sleep_performance": _value_number(sleep_score, "sleep_performance_percentage"),
        "sleep_consistency": _value_number(sleep_score, "sleep_consistency_percentage"),
        "disturbances": int(_value_number(stage, "disturbance_count")),
        "phases": phases,
        "recovery_score": _value_number(recovery_score, "recovery_score"),
        "hrv": _value_number(recovery_score, "hrv_rmssd_milli"),
        "rhr": _value_number(recovery_score, "resting_heart_rate"),
        "spo2": _value_number(recovery_score, "spo2_percentage"),
        "skin_temp": _value_number(recovery_score, "skin_temp_celsius"),
    }


def _normalize_workout(workout: dict[str, Any]) -> dict[str, Any]:
    if workout.get("score_state") not in (None, "SCORED"):
        raise ValueError("The selected WHOOP workout is not scored yet")
    score = workout.get("score") if isinstance(workout.get("score"), dict) else {}
    zones = score.get("zone_durations") if isinstance(score.get("zone_durations"), dict) else {}
    sport_name = str(workout.get("sport_name") or "activity")
    label = local_datetime_label(str(workout.get("start") or ""), str(workout.get("timezone_offset") or ""))
    return {
        "workout_id": str(workout.get("id") or ""),
        "title": f"{sport_name.replace('-', ' ').title()} summary",
        "subtitle": f"Latest logged activity • {label}" if label else "Latest logged activity",
        "sport_name": sport_name,
        "duration_second": _duration_seconds(workout),
        "strain": _value_number(score, "strain"),
        "average_heart_rate": _value_number(score, "average_heart_rate"),
        "max_heart_rate": _value_number(score, "max_heart_rate"),
        "kilojoule": _value_number(score, "kilojoule"),
        "distance_meter": score.get("distance_meter") if isinstance(score.get("distance_meter"), (int, float)) else None,
        "altitude_gain_meter": score.get("altitude_gain_meter") if isinstance(score.get("altitude_gain_meter"), (int, float)) else None,
        "percent_recorded": score.get("percent_recorded") if isinstance(score.get("percent_recorded"), (int, float)) else None,
        "zones_milli": [_value_number(zones, f"zone_{name}_milli") for name in ("zero", "one", "two", "three", "four", "five")],
    }


def _latest_main_sleep(client: WhoopClient, sleep_id: str = "") -> dict[str, Any]:
    if sleep_id:
        return client.get(f"v2/activity/sleep/{sleep_id}")
    sleeps = client.collection("v2/activity/sleep", limit=10).get("records", [])
    sleep = next((row for row in sleeps if not row.get("nap")), None)
    if not sleep:
        raise ValueError("WHOOP returned no main sleep to visualize")
    return sleep


def _matching_recovery(client: WhoopClient, sleep_id: str) -> dict[str, Any] | None:
    recoveries = client.collection("v2/recovery", limit=25).get("records", [])
    return next((row for row in recoveries if str(row.get("sleep_id") or "") == sleep_id), None)


def _visual_date_window(value: str) -> tuple[datetime, datetime, str]:
    cfg = read_config()
    try:
        zone = ZoneInfo(cfg.timezone)
    except Exception:
        zone = timezone.utc
    if value:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    else:
        day = datetime.now(zone).date()
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), day.isoformat()


def _configured_timezone():
    try:
        return ZoneInfo(read_config().timezone)
    except Exception:
        return timezone.utc


def _daily_coaching(recovery: float, strain: float, sleep: float) -> tuple[str, str, str]:
    if recovery >= 67 and strain >= 14:
        return (
            "Green engine. Orange workload.",
            "Strong readiness, but the day stacked heavy — refuel and protect sleep.",
            "End-of-day move: eat, hydrate, downshift, sleep.",
        )
    if recovery < 34:
        return (
            "Recovery was the limiter.",
            "Keep the load easy and give tonight's sleep a real chance to work.",
            "Next move: recover, hydrate, and get to bed on time.",
        )
    if sleep < 70:
        return (
            "Sleep debt is driving the day.",
            "Keep intensity controlled and prioritize a longer sleep window tonight.",
            "Next move: downshift early and protect bedtime.",
        )
    return (
        "A balanced day on the books.",
        "Readiness and workload stayed manageable — keep the recovery routine steady.",
        "Next move: refuel, hydrate, and protect the next sleep window.",
    )


def render_visual_report(args: dict[str, Any]) -> Any:
    report_type = str(args.get("report_type") or "").strip()
    if report_type not in {"sleep_phases", "post_sleep", "workout", "daily_recap"}:
        raise ValueError("report_type must be sleep_phases, post_sleep, workout, or daily_recap")
    client = WhoopClient()

    if report_type in {"sleep_phases", "post_sleep"}:
        sleep = _latest_main_sleep(client, str(args.get("sleep_id") or "").strip())
        recovery = _matching_recovery(client, str(sleep.get("id") or ""))
        normalized = _normalize_sleep(sleep, recovery)
        source = {"sleep_id": normalized["sleep_id"], "recovery_found": recovery is not None}
    elif report_type == "workout":
        workout_id = str(args.get("workout_id") or "").strip()
        if workout_id:
            workout = client.get(f"v2/activity/workout/{workout_id}")
        else:
            workouts = client.collection("v2/activity/workout", limit=25).get("records", [])
            sport_name = str(args.get("sport_name") or "").strip().lower()
            if sport_name:
                workouts = [
                    row
                    for row in workouts
                    if str(row.get("sport_name") or "").strip().lower() == sport_name
                ]
            if not workouts:
                raise ValueError("WHOOP returned no matching workout to visualize")
            workout = workouts[0]
        normalized = _normalize_workout(workout)
        source = {"workout_id": normalized["workout_id"], "sport_name": normalized["sport_name"]}
    else:
        start, end, day = _visual_date_window(str(args.get("date") or "").strip())
        query = {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "limit": 25,
        }
        cycles = client.collection("v2/cycle", **query).get("records", [])
        sleeps = client.collection("v2/activity/sleep", **query).get("records", [])
        recoveries = client.collection("v2/recovery", **query).get("records", [])
        workouts = client.collection("v2/activity/workout", **query).get("records", [])
        cycle = cycles[0] if cycles else {}
        sleep: dict[str, Any] = {}
        recovery: dict[str, Any] = {}
        if cycle.get("id") is not None:
            try:
                sleep = client.get(f"v2/cycle/{int(cycle['id'])}/sleep")
                recovery = client.get(f"v2/cycle/{int(cycle['id'])}/recovery")
            except (WhoopError, TypeError, ValueError):
                sleep = {}
                recovery = {}
        if not sleep:
            sleep = next((row for row in sleeps if not row.get("nap")), {})
        if not recovery:
            recovery = next(
                (
                    row
                    for row in recoveries
                    if str(row.get("sleep_id") or "") == str(sleep.get("id") or "")
                ),
                recoveries[0] if recoveries else {},
            )
        sleep_data = _normalize_sleep(sleep, recovery)
        cycle_score = cycle.get("score") if isinstance(cycle.get("score"), dict) else {}
        recovery_score = float(sleep_data.get("recovery_score") or 0)
        strain = _value_number(cycle_score, "strain")
        sleep_performance = float(sleep_data.get("sleep_performance") or 0)
        coach_read, next_action, footer = _daily_coaching(recovery_score, strain, sleep_performance)
        normalized = {
            **sleep_data,
            "title": f"{start.astimezone(_configured_timezone()).strftime('%A')} recap",
            "subtitle": (
                f"{datetime.strptime(day, '%Y-%m-%d').strftime('%b')} "
                f"{datetime.strptime(day, '%Y-%m-%d').day} • end-of-day WHOOP snapshot"
            ),
            "strain": strain,
            "max_hr": _value_number(cycle_score, "max_heart_rate"),
            "calories": _value_number(cycle_score, "kilojoule") / 4.184,
            "workouts": [_normalize_workout(row) for row in workouts],
            "coach_read": coach_read,
            "next_action": next_action,
            "footer": footer,
        }
        source = {
            "date": day,
            "cycle_id": cycle.get("id"),
            "sleep_id": sleep.get("id"),
            "workout_ids": [row.get("id") for row in workouts],
        }

    media_path = render_report_data(report_type, normalized)
    return {
        "report_type": report_type,
        "media_path": media_path,
        "media_directive": f"MEDIA:{media_path}",
        "source": source,
        "delivery": (
            "For the current Inkbox iMessage thread, include media_directive in one normal reply. "
            "Use inkbox_send_imessage(mediaPaths=[media_path]) only for a different conversation."
        ),
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
                "If score_state is SCORED and outreach_policy allows it, call whoop_render_report with "
                "report_type='workout' and this resource_id, then send media_path exactly once to the "
                "home iMessage conversation. Otherwise send nothing."
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
                "When both records are scored and outreach_policy allows it, call whoop_render_report with "
                "report_type='post_sleep' and this resource_id as sleep_id, then send media_path exactly "
                "once to the home iMessage conversation. Otherwise send nothing."
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
    outreach_kind = None
    if event_type == "workout.updated" and result["workout"].get("score_state") == "SCORED":
        outreach_kind = "workout_recap"
    elif (
        event_type == "recovery.updated"
        and (result.get("recovery") or {}).get("score_state") == "SCORED"
        and result["sleep"].get("score_state") == "SCORED"
    ):
        outreach_kind = "sleep_recap"
    if outreach_kind and not store.claim_outreach(outreach_kind, resource_id):
        store.mark_version(event_type, resource_id, version)
        store.mark(trace_id, event_type, resource_id)
        return {
            "duplicate": True,
            "event_type": event_type,
            "resource_id": resource_id,
            "reason": "A proactive recap was already claimed for this resource.",
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
        "may_message_now": bool(
            cfg.home_channel and (not in_quiet_hours or not cfg.recaps_respect_quiet_hours)
        ),
        "recaps_respect_quiet_hours": cfg.recaps_respect_quiet_hours,
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
        "whoop_render_report",
        _schema(
            "whoop_render_report",
            (
                "Render a polished PNG from live WHOOP data. Returns a media_path and MEDIA: directive; "
                "use the directive in the current Inkbox iMessage reply so the attachment is sent once."
            ),
            {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": ["sleep_phases", "post_sleep", "workout", "daily_recap"],
                    },
                    "sleep_id": {
                        "type": "string",
                        "description": "Optional WHOOP sleep UUID for sleep reports; defaults to latest main sleep.",
                    },
                    "workout_id": {
                        "type": "string",
                        "description": "Optional WHOOP workout UUID; defaults to latest matching workout.",
                    },
                    "sport_name": {
                        "type": "string",
                        "description": "Optional exact sport filter when rendering the latest workout.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional local YYYY-MM-DD for daily_recap; defaults to today.",
                    },
                },
                "required": ["report_type"],
            },
        ),
        render_visual_report,
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
