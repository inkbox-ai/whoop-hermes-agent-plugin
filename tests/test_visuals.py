from pathlib import Path

from PIL import Image

import visuals


SLEEP = {
    "total_in_bed_milli": 24_000_000,
    "sleep_efficiency": 94,
    "sleep_performance": 82,
    "sleep_consistency": 78,
    "disturbances": 6,
    "recovery_score": 72,
    "hrv": 58.4,
    "rhr": 54,
    "spo2": 96,
    "skin_temp": 34.8,
    "phases": [
        {"label": "Light", "milliseconds": 10_000_000},
        {"label": "Deep", "milliseconds": 7_000_000},
        {"label": "REM", "milliseconds": 5_000_000},
        {"label": "Awake", "milliseconds": 2_000_000},
    ],
}

WORKOUT = {
    "sport_name": "running",
    "duration_second": 1500,
    "distance_meter": 5000,
    "strain": 11.8,
    "average_heart_rate": 160,
    "max_heart_rate": 182,
    "kilojoule": 1300,
    "altitude_gain_meter": 125,
    "percent_recorded": 0.998,
    "zones_milli": [0, 30_000, 150_000, 700_000, 600_000, 20_000],
}


def test_all_report_templates_render_nonempty_png(tmp_path):
    payloads = {
        "sleep_phases": SLEEP,
        "post_sleep": SLEEP,
        "workout": WORKOUT,
        "daily_recap": {
            **SLEEP,
            "strain": 14.2,
            "max_hr": 182,
            "calories": 2600,
            "workouts": [WORKOUT],
            "coach_read": "Strong readiness, meaningful work.",
            "next_action": "Refuel and protect sleep.",
        },
    }
    expected_heights = {
        "sleep_phases": 1350,
        "post_sleep": 1500,
        "workout": 1500,
        "daily_recap": 1600,
    }

    for report_type, payload in payloads.items():
        output = tmp_path / f"{report_type}.png"
        rendered = Path(visuals.render_report_data(report_type, payload, output))
        assert rendered == output.resolve()
        assert rendered.stat().st_size > 10_000
        with Image.open(rendered) as image:
            assert image.format == "PNG"
            assert image.size == (1080, expected_heights[report_type])


def test_unknown_report_type_is_rejected(tmp_path):
    try:
        visuals.render_report_data("unknown", {}, tmp_path / "bad.png")
    except ValueError as exc:
        assert "Unknown WHOOP report type" in str(exc)
    else:
        raise AssertionError("unknown report type should fail")
