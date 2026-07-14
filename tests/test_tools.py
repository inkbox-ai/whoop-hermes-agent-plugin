import tools


class FakeClient:
    def get(self, path, params=None):
        if path.startswith("v2/activity/workout/"):
            return {"id": path.rsplit("/", 1)[-1], "score_state": "SCORED", "score": {"strain": 10}}
        if path.startswith("v2/activity/sleep/"):
            return {"id": path.rsplit("/", 1)[-1], "score_state": "SCORED"}
        return {"path": path, "params": params}

    def collection(self, path, **kwargs):
        if path == "v2/recovery":
            return {
                "records": [
                    {
                        "sleep_id": "sleep-1",
                        "score_state": "SCORED",
                        "score": {"recovery_score": 80},
                    }
                ]
            }
        return {"records": [], "next_token": None}


def test_process_workout_event_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "WhoopClient", FakeClient)
    monkeypatch.setattr(
        tools,
        "read_config",
        lambda: type(
            "Config",
            (),
            {
                "state_dir": tmp_path / "whoop",
                "timezone": "UTC",
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "07:00",
                "recaps_respect_quiet_hours": True,
                "home_channel": "conversation-1",
            },
        )(),
    )
    event = {"event_type": "workout.updated", "resource_id": "workout-1", "trace_id": "trace-1"}

    first = tools.process_event(event)
    second = tools.process_event(event)

    assert first["workout"]["score_state"] == "SCORED"
    assert second["duplicate"] is True


def test_process_recovery_joins_on_sleep_uuid(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "WhoopClient", FakeClient)
    monkeypatch.setattr(
        tools,
        "read_config",
        lambda: type(
            "Config",
            (),
            {
                "state_dir": tmp_path / "whoop",
                "timezone": "UTC",
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "07:00",
                "recaps_respect_quiet_hours": True,
                "home_channel": "conversation-1",
            },
        )(),
    )
    result = tools.process_event(
        {"event_type": "recovery.updated", "resource_id": "sleep-1", "trace_id": "trace-2"}
    )
    assert result["recovery"]["score"]["recovery_score"] == 80
    assert result["sleep"]["id"] == "sleep-1"
    assert result["outreach_policy"]["may_call_from_webhook"] is False


def test_all_manifest_tools_are_registered():
    calls = []

    class Context:
        def register_tool(self, **kwargs):
            calls.append(kwargs)

    tools.register_tools(Context())
    assert {call["name"] for call in calls} == {definition[0] for definition in tools.TOOL_DEFINITIONS}
    assert all(call["schema"]["name"] == call["name"] for call in calls)
    assert all("emoji" not in call for call in calls)


class VisualClient:
    workout = {
        "id": "workout-1",
        "sport_name": "running",
        "score_state": "SCORED",
        "start": "2026-07-14T10:00:00Z",
        "end": "2026-07-14T10:25:00Z",
        "timezone_offset": "-04:00",
        "score": {
            "strain": 11.5,
            "average_heart_rate": 158,
            "max_heart_rate": 181,
            "distance_meter": 5000,
            "kilojoule": 1200,
            "zone_durations": {"zone_three_milli": 600000},
        },
    }
    sleep = {
        "id": "sleep-1",
        "score_state": "SCORED",
        "nap": False,
        "score": {
            "sleep_efficiency_percentage": 95,
            "sleep_performance_percentage": 83,
            "stage_summary": {
                "total_in_bed_time_milli": 24_000_000,
                "total_light_sleep_time_milli": 10_000_000,
                "total_slow_wave_sleep_time_milli": 7_000_000,
                "total_rem_sleep_time_milli": 5_000_000,
                "total_awake_time_milli": 2_000_000,
            },
        },
    }
    recovery = {
        "sleep_id": "sleep-1",
        "score_state": "SCORED",
        "score": {"recovery_score": 76, "hrv_rmssd_milli": 61, "resting_heart_rate": 53},
    }
    cycle = {"id": 123, "score": {"strain": 12.5, "max_heart_rate": 181, "kilojoule": 2200}}

    def get(self, path, params=None):
        del params
        if "workout" in path:
            return self.workout
        if "sleep" in path:
            return self.sleep
        if "recovery" in path:
            return self.recovery
        raise AssertionError(path)

    def collection(self, path, **kwargs):
        del kwargs
        if path == "v2/activity/workout":
            return {"records": [self.workout]}
        if path == "v2/activity/sleep":
            return {"records": [self.sleep]}
        if path == "v2/recovery":
            return {"records": [self.recovery]}
        if path == "v2/cycle":
            return {"records": [self.cycle]}
        raise AssertionError(path)


def test_render_visual_report_normalizes_live_workout(monkeypatch, tmp_path):
    captured = {}

    def fake_render(report_type, data):
        captured.update({"report_type": report_type, "data": data})
        return str(tmp_path / "workout.png")

    monkeypatch.setattr(tools, "WhoopClient", VisualClient)
    monkeypatch.setattr(tools, "render_report_data", fake_render)

    result = tools.render_visual_report({"report_type": "workout", "sport_name": "running"})

    assert result["media_directive"] == f"MEDIA:{tmp_path / 'workout.png'}"
    assert captured["report_type"] == "workout"
    assert captured["data"]["duration_second"] == 1500
    assert captured["data"]["zones_milli"][3] == 600000


def test_render_visual_report_joins_sleep_and_recovery(monkeypatch, tmp_path):
    captured = {}

    def fake_render(report_type, data):
        captured.update({"report_type": report_type, "data": data})
        return str(tmp_path / "sleep.png")

    monkeypatch.setattr(tools, "WhoopClient", VisualClient)
    monkeypatch.setattr(tools, "render_report_data", fake_render)

    result = tools.render_visual_report({"report_type": "post_sleep"})

    assert result["source"] == {"sleep_id": "sleep-1", "recovery_found": True}
    assert captured["data"]["recovery_score"] == 76
    assert captured["data"]["phases"][1]["label"] == "Deep"


def test_render_daily_report_uses_cycle_linked_sleep(monkeypatch, tmp_path):
    captured = {}

    def fake_render(report_type, data):
        captured.update({"report_type": report_type, "data": data})
        return str(tmp_path / "daily.png")

    monkeypatch.setattr(tools, "WhoopClient", VisualClient)
    monkeypatch.setattr(tools, "render_report_data", fake_render)

    result = tools.render_visual_report({"report_type": "daily_recap", "date": "2026-07-14"})

    assert result["source"]["cycle_id"] == 123
    assert captured["report_type"] == "daily_recap"
    assert captured["data"]["recovery_score"] == 76
    assert captured["data"]["strain"] == 12.5
