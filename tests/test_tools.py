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
            return {"records": [{"sleep_id": "sleep-1", "score": {"recovery_score": 80}}]}
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
    assert len(calls) == 16
    assert {call["name"] for call in calls} == {definition[0] for definition in tools.TOOL_DEFINITIONS}
    assert all(call["schema"]["name"] == call["name"] for call in calls)
