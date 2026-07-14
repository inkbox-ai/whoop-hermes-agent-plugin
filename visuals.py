"""Deterministic, mobile-friendly WHOOP visual report templates."""

from __future__ import annotations

import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # Keep plugin/CLI discovery available for a clear setup error.
    Image = ImageDraw = ImageFilter = ImageFont = None


W = 1080
BG_TOP = (9, 14, 31)
BG_BOTTOM = (28, 16, 66)
CARD = (12, 20, 44)
PANEL = (24, 36, 74)
PANEL_DARK = (34, 46, 78)
WHITE = (248, 250, 252)
MUTED = (176, 192, 216)
BORDER = (62, 84, 130)
GREEN = (42, 211, 111)
YELLOW = (245, 196, 67)
RED = (248, 82, 82)
CYAN = (56, 189, 248)
BLUE = (79, 70, 255)
PURPLE = (192, 105, 255)
ORANGE = (255, 128, 50)
ZONE_COLORS = [(92, 108, 148), CYAN, GREEN, YELLOW, ORANGE, RED]

_FONT_REGULAR = (
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "Arial.ttf",
)
_FONT_BOLD = (
    "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "Arial Bold.ttf",
)


def _require_pillow() -> None:
    if Image is None:
        raise RuntimeError(
            "WHOOP visual reports require Pillow>=10 in the Hermes Python environment"
        )


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_BOLD if bold else _FONT_REGULAR:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _canvas(height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, height), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line((0, y, W, y), fill=color)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-280, -260, 620, 620), fill=(63, 45, 190, 95))
    gd.ellipse((650, height - 650, 1400, height + 120), fill=(101, 23, 190, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 42, W - 42, height - 42), 44, fill=CARD, outline=BORDER, width=2)
    return image, draw


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius, fill=PANEL, outline=BORDER, width=2)


def _center(draw: ImageDraw.ImageDraw, cx: float, y: float, text: str, font, fill=WHITE) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (box[2] - box[0]) / 2, y), text, font=font, fill=fill)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int, *, bold: bool = False):
    current = size
    while current > 16:
        candidate = _font(current, bold)
        box = draw.textbbox((0, 0), text, font=candidate)
        if box[2] - box[0] <= max_width:
            return candidate
        current -= 2
    return _font(16, bold)


def _value(data: dict[str, Any] | None, key: str, default: float = 0.0) -> float:
    raw = (data or {}).get(key)
    return float(raw) if isinstance(raw, (int, float)) else default


def _duration(ms: float) -> str:
    minutes = max(0, round(ms / 60_000))
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


def _zone_time(ms: float) -> str:
    seconds = max(0, round(ms / 1000))
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes}:{remainder:02d}"


def _clock(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"


def _recovery_color(score: float) -> tuple[int, int, int]:
    return GREEN if score >= 67 else YELLOW if score >= 34 else RED


def _recovery_label(score: float) -> str:
    return "primed" if score >= 67 else "balanced" if score >= 34 else "recover"


def _strain_label(strain: float) -> str:
    return "big load" if strain >= 14 else "productive" if strain >= 8 else "light"


def _ring(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    fraction: float,
    color: tuple[int, int, int],
    value: str,
    label: str,
    sublabel: str,
) -> None:
    fraction = max(0.0, min(float(fraction), 1.0))
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.ellipse(box, fill=PANEL_DARK, outline=(220, 232, 255), width=3)
    draw.pieslice(box, -90, -90 + 360 * fraction, fill=color)
    inner = round(radius * 0.61)
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=CARD, outline=WHITE, width=2)
    _center(draw, cx, cy - 55, value, _font(66, True))
    _center(draw, cx, cy + 19, label, _font(25), MUTED)
    _center(draw, cx, cy + 55, sublabel, _font(22), color)


def _metric_chips(draw: ImageDraw.ImageDraw, metrics: Iterable[tuple[str, str, tuple[int, int, int]]], y: int) -> None:
    rows = list(metrics)[:4]
    gap = 22
    width = round((916 - gap * max(len(rows) - 1, 0)) / max(len(rows), 1))
    for index, (label, value, color) in enumerate(rows):
        x = 82 + index * (width + gap)
        _panel(draw, (x, y, x + width, y + 92), 22)
        draw.text((x + 22, y + 15), label, font=_font(19), fill=MUTED)
        value_font = _fit_font(draw, value, 31, width - 42, bold=True)
        draw.text((x + 22, y + 43), value, font=value_font, fill=color)


def _phase_rows(draw: ImageDraw.ImageDraw, phases: list[dict[str, Any]], y: int, *, row_gap: int = 78) -> None:
    max_ms = max([float(row.get("milliseconds") or 0) for row in phases] or [1]) or 1
    total_ms = sum(float(row.get("milliseconds") or 0) for row in phases) or 1
    bar_x, bar_width = 250, 515
    colors = {"Light": CYAN, "Deep": BLUE, "REM": PURPLE, "Awake": ORANGE}
    for index, row in enumerate(phases):
        label = str(row.get("label") or "Unknown")
        ms = float(row.get("milliseconds") or 0)
        color = colors.get(label, MUTED)
        row_y = y + index * row_gap
        draw.rounded_rectangle((82, row_y + 6, 126, row_y + 50), 13, fill=color)
        draw.text((146, row_y), label, font=_font(31, True), fill=WHITE)
        draw.text((146, row_y + 35), f"{ms / total_ms:.0%}", font=_font(23), fill=MUTED)
        draw.rounded_rectangle((bar_x, row_y + 10, bar_x + bar_width, row_y + 48), 18, fill=PANEL_DARK)
        fill_width = max(8, round(bar_width * ms / max_ms)) if ms else 0
        if fill_width:
            draw.rounded_rectangle((bar_x, row_y + 10, bar_x + fill_width, row_y + 48), 18, fill=color)
        draw.text((bar_x + bar_width + 28, row_y + 10), _duration(ms), font=_font(30, True), fill=WHITE)


def render_sleep_phases(data: dict[str, Any], output: Path) -> Path:
    image, draw = _canvas(1350)
    total_in_bed = float(data.get("total_in_bed_milli") or 0)
    efficiency = float(data.get("sleep_efficiency") or 0)
    phases = list(data.get("phases") or [])
    title = str(data.get("title") or "Sleep phases")
    subtitle = str(data.get("subtitle") or f"Last sleep • {_duration(total_in_bed)} in bed • {efficiency:.0f}% efficiency")
    draw.text((82, 82), title, font=_fit_font(draw, title, 76, 910, bold=True), fill=WHITE)
    draw.text((86, 168), subtitle, font=_fit_font(draw, subtitle, 34, 910), fill=MUTED)
    _metric_chips(
        draw,
        [
            ("Recovery", f"{data.get('recovery_score', 0):.0f}%", _recovery_color(float(data.get("recovery_score") or 0))),
            ("HRV", f"{data.get('hrv', 0):.1f} ms", WHITE),
            ("RHR", f"{data.get('rhr', 0):.0f}", WHITE),
            ("Disturb.", f"{int(data.get('disturbances') or 0)}", WHITE),
        ],
        238,
    )
    total = sum(float(row.get("milliseconds") or 0) for row in phases) or 1
    cx, cy, outer, inner = 540, 610, 245, 145
    start = -90.0
    colors = [CYAN, BLUE, PURPLE, ORANGE]
    for index, row in enumerate(phases):
        angle = float(row.get("milliseconds") or 0) / total * 360
        draw.pieslice((cx - outer, cy - outer, cx + outer, cy + outer), start, start + angle, fill=colors[index % 4])
        start += angle
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=CARD, outline=WHITE, width=3)
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), outline=WHITE, width=3)
    _center(draw, cx, cy - 57, _duration(total_in_bed), _font(64, True))
    _center(draw, cx, cy + 18, "total in bed", _font(27), MUTED)
    _center(draw, cx, cy + 58, f"{efficiency:.0f}% efficiency", _font(23), CYAN)
    draw.text((82, 900), "Distribution", font=_font(44, True), fill=WHITE)
    _phase_rows(draw, phases, 978)
    image.save(output, "PNG", optimize=True)
    return output


def render_post_sleep(data: dict[str, Any], output: Path) -> Path:
    image, draw = _canvas(1500)
    total_in_bed = float(data.get("total_in_bed_milli") or 0)
    recovery = float(data.get("recovery_score") or 0)
    efficiency = float(data.get("sleep_efficiency") or 0)
    title = str(data.get("title") or "Post-sleep report")
    draw.text((82, 82), title, font=_fit_font(draw, title, 70, 910, bold=True), fill=WHITE)
    subtitle = str(data.get("subtitle") or f"Recovery + sleep phases • {_duration(total_in_bed)} in bed")
    draw.text((86, 164), subtitle, font=_fit_font(draw, subtitle, 32, 910), fill=MUTED)
    _metric_chips(
        draw,
        [
            ("HRV", f"{data.get('hrv', 0):.1f} ms", WHITE),
            ("RHR", f"{data.get('rhr', 0):.0f}", WHITE),
            ("SpO₂", f"{data.get('spo2', 0):.0f}%", WHITE),
            ("Disturb.", f"{int(data.get('disturbances') or 0)}", WHITE),
        ],
        236,
    )
    _ring(draw, 320, 590, 185, recovery / 100, _recovery_color(recovery), f"{recovery:.0f}%", "recovery", _recovery_label(recovery))
    _ring(draw, 760, 590, 185, efficiency / 100, CYAN, f"{efficiency:.0f}%", "efficiency", "clean sleep" if efficiency >= 90 else "fragmented")
    draw.text((82, 835), "Sleep phases", font=_font(44, True), fill=WHITE)
    _phase_rows(draw, list(data.get("phases") or []), 913)
    _metric_chips(
        draw,
        [
            ("Sleep perf.", f"{data.get('sleep_performance', 0):.0f}%", WHITE),
            ("Consistency", f"{data.get('sleep_consistency', 0):.0f}%", WHITE),
            ("Skin temp", f"{data.get('skin_temp', 0):.1f}°C", WHITE),
        ],
        1285,
    )
    image.save(output, "PNG", optimize=True)
    return output


def render_workout(data: dict[str, Any], output: Path) -> Path:
    image, draw = _canvas(1500)
    title = str(data.get("title") or f"{str(data.get('sport_name') or 'Activity').replace('-', ' ').title()} summary")
    subtitle = str(data.get("subtitle") or "Latest WHOOP workout")
    draw.text((82, 82), title, font=_fit_font(draw, title, 72, 910, bold=True), fill=WHITE)
    draw.text((86, 166), subtitle, font=_fit_font(draw, subtitle, 31, 910), fill=MUTED)
    _panel(draw, (82, 238, 998, 505), 34)
    distance = data.get("distance_meter")
    duration = float(data.get("duration_second") or 0)
    strain = float(data.get("strain") or 0)
    average_hr = float(data.get("average_heart_rate") or 0)
    max_hr = float(data.get("max_heart_rate") or 0)
    if isinstance(distance, (int, float)) and distance > 0:
        km = float(distance) / 1000
        pace = duration / km if km else 0
        draw.text((122, 275), "DISTANCE", font=_font(20), fill=MUTED)
        draw.text((122, 302), f"{km:.2f} km", font=_font(76, True), fill=WHITE)
        draw.text((124, 390), f"{float(distance) / 1609.344:.2f} mi", font=_font(31, True), fill=MUTED)
        right = [("PACE", f"{int(pace // 60)}:{int(round(pace % 60)):02d}/km", CYAN), ("TIME", _clock(duration), WHITE)]
    else:
        draw.text((122, 275), "DURATION", font=_font(20), fill=MUTED)
        draw.text((122, 302), _clock(duration), font=_font(76, True), fill=WHITE)
        draw.text((124, 390), "no distance recorded", font=_font(31, True), fill=MUTED)
        right = [("STRAIN", f"{strain:.1f}", ORANGE), ("AVG HR", f"{average_hr:.0f}", RED)]
    for index, (label, value, color) in enumerate(right):
        y = 278 + index * 100
        draw.text((555, y), label, font=_font(20), fill=MUTED)
        draw.text((555, y + 28), value, font=_fit_font(draw, value, 46, 390, bold=True), fill=color)
    _ring(draw, 310, 725, 164, strain / 21, ORANGE, f"{strain:.1f}", "strain", _strain_label(strain))
    _ring(draw, 770, 725, 164, average_hr / max(max_hr, 200), RED, f"{average_hr:.0f}", "avg HR", f"max {max_hr:.0f}")
    kilojoule = float(data.get("kilojoule") or 0)
    recorded = data.get("percent_recorded")
    _metric_chips(
        draw,
        [
            ("Elevation", "—" if data.get("altitude_gain_meter") is None else f"{float(data['altitude_gain_meter']):.0f} m", WHITE),
            ("Energy", "—" if not kilojoule else f"{kilojoule / 4.184:.0f} cal", WHITE),
            ("Max HR", "—" if not max_hr else f"{max_hr:.0f}", WHITE),
            ("Recorded", "—" if recorded is None else f"{float(recorded) * 100:.2f}%", WHITE),
        ],
        932,
    )
    draw.text((82, 1090), "Heart-rate zones", font=_font(44, True), fill=WHITE)
    zones = list(data.get("zones_milli") or [0] * 6)[:6]
    zones += [0] * (6 - len(zones))
    total = sum(float(value or 0) for value in zones) or 1
    for index, (milliseconds, color) in enumerate(zip(zones, ZONE_COLORS)):
        y = 1168 + index * 50
        draw.rounded_rectangle((82, y + 4, 122, y + 36), 10, fill=color)
        draw.text((142, y), f"Z{index}", font=_font(23), fill=WHITE)
        draw.rounded_rectangle((250, y + 3, 765, y + 35), 15, fill=PANEL_DARK)
        width = round(515 * float(milliseconds or 0) / total)
        if width:
            draw.rounded_rectangle((250, y + 3, 250 + max(4, width), y + 35), 15, fill=color)
        draw.text((793, y + 1), _zone_time(float(milliseconds or 0)), font=_font(23), fill=WHITE)
    image.save(output, "PNG", optimize=True)
    return output


def render_daily_recap(data: dict[str, Any], output: Path) -> Path:
    image, draw = _canvas(1600)
    recovery = float(data.get("recovery_score") or 0)
    strain = float(data.get("strain") or 0)
    sleep_performance = float(data.get("sleep_performance") or 0)
    title = str(data.get("title") or "Daily recap")
    subtitle = str(data.get("subtitle") or "End-of-day WHOOP snapshot")
    _center(draw, W / 2, 85, title, _fit_font(draw, title, 68, 900, bold=True))
    _center(draw, W / 2, 165, subtitle, _fit_font(draw, subtitle, 29, 900), MUTED)
    width, gap, y = 290, 22, 245
    cards = [
        ("RECOVERY", f"{recovery:.0f}%", _recovery_color(recovery), _recovery_label(recovery)),
        ("STRAIN", f"{strain:.1f}", ORANGE, _strain_label(strain)),
        ("SLEEP", f"{sleep_performance:.0f}%", CYAN, "solid" if sleep_performance >= 80 else "needs work"),
    ]
    for index, (label, value, color, sublabel) in enumerate(cards):
        x = 82 + index * (width + gap)
        _panel(draw, (x, y, x + width, y + 205), 30)
        _center(draw, x + width / 2, y + 28, label, _font(18, True), MUTED)
        _center(draw, x + width / 2, y + 74, value, _font(76, True))
        _center(draw, x + width / 2, y + 155, sublabel, _font(22), color)
        draw.rounded_rectangle((x + 42, y + 185, x + width - 42, y + 193), 4, fill=color)
    _panel(draw, (82, 500, 998, 630), 28)
    coach = str(data.get("coach_read") or "Recovery and strain tell the story.")
    action = str(data.get("next_action") or "Use the trend, not one isolated number.")
    _center(draw, W / 2, 528, coach, _fit_font(draw, coach, 40, 840, bold=True))
    _center(draw, W / 2, 584, action, _fit_font(draw, action, 25, 840), MUTED)
    _metric_chips(
        draw,
        [
            ("HRV", f"{data.get('hrv', 0):.1f} ms", _recovery_color(recovery)),
            ("RHR", f"{data.get('rhr', 0):.0f} bpm", _recovery_color(recovery)),
            ("Max HR", f"{data.get('max_hr', 0):.0f}", ORANGE),
            ("Burn", f"{data.get('calories', 0):.0f} cal", WHITE),
        ],
        675,
    )
    workouts = list(data.get("workouts") or [])
    _center(draw, W / 2, 825, "Activity stack", _font(42, True))
    total_minutes = sum(float(row.get("duration_second") or 0) for row in workouts) / 60
    _center(draw, W / 2, 873, f"{len(workouts)} logged effort{'s' if len(workouts) != 1 else ''} • {total_minutes / 60:.1f}h movement", _font(25), MUTED)
    visible = workouts[:3]
    max_strain = max([float(row.get("strain") or 0) for row in visible] or [1]) or 1
    for index in range(3):
        row_y = 925 + index * 72
        _panel(draw, (118, row_y, 962, row_y + 54), 18)
        if index >= len(visible):
            _center(draw, W / 2, row_y + 14, "No additional activity", _font(22), MUTED)
            continue
        row = visible[index]
        row_strain = float(row.get("strain") or 0)
        color = ORANGE if row_strain >= 10 else CYAN
        draw.rounded_rectangle((145, row_y + 14, 175, row_y + 40), 8, fill=color)
        name = str(row.get("sport_name") or "Activity").replace("-", " ").title()
        draw.text((198, row_y + 13), name[:18], font=_font(22), fill=WHITE)
        _center(draw, 472, row_y + 14, f"{float(row.get('duration_second') or 0) / 60:.0f}m", _font(22), MUTED)
        draw.rounded_rectangle((570, row_y + 16, 795, row_y + 38), 11, fill=PANEL_DARK)
        draw.rounded_rectangle((570, row_y + 16, 570 + round(225 * row_strain / max_strain), row_y + 38), 11, fill=color)
        _center(draw, 875, row_y + 11, f"{row_strain:.1f}", _font(29, True))
    phases = list(data.get("phases") or [])
    total_in_bed = float(data.get("total_in_bed_milli") or 0)
    efficiency = float(data.get("sleep_efficiency") or 0)
    _center(draw, W / 2, 1185, "Sleep bank", _font(42, True))
    _center(draw, W / 2, 1233, f"{_duration(total_in_bed)} in bed • {efficiency:.0f}% efficiency", _font(25), MUTED)
    total_phase = sum(float(row.get("milliseconds") or 0) for row in phases) or 1
    colors = [CYAN, BLUE, PURPLE, ORANGE]
    for index, row in enumerate(phases[:4]):
        row_y = 1285 + index * 48
        ms = float(row.get("milliseconds") or 0)
        fraction = ms / total_phase
        color = colors[index]
        draw.rounded_rectangle((145, row_y + 8, 175, row_y + 34), 7, fill=color)
        draw.text((198, row_y + 5), str(row.get("label") or "Phase"), font=_font(22), fill=WHITE)
        draw.rounded_rectangle((270, row_y + 9, 690, row_y + 32), 11, fill=PANEL_DARK)
        if ms:
            draw.rounded_rectangle((270, row_y + 9, 270 + round(420 * fraction), row_y + 32), 11, fill=color)
        _center(draw, 750, row_y + 5, f"{fraction:.0%}", _font(22), MUTED)
        _center(draw, 880, row_y + 5, _duration(ms), _font(22))
    _panel(draw, (118, 1480, 962, 1540), 22)
    footer = str(data.get("footer") or "Protect the next recovery window.")
    _center(draw, W / 2, 1498, footer, _fit_font(draw, footer, 25, 790), WHITE)
    image.save(output, "PNG", optimize=True)
    return output


RENDERERS = {
    "sleep_phases": render_sleep_phases,
    "post_sleep": render_post_sleep,
    "workout": render_workout,
    "daily_recap": render_daily_recap,
}


def render_report_data(report_type: str, data: dict[str, Any], output_path: str | Path | None = None) -> str:
    """Render normalized report data and return an absolute PNG path."""
    _require_pillow()
    if report_type not in RENDERERS:
        raise ValueError(f"Unknown WHOOP report type: {report_type}")
    if output_path is None:
        output = Path(tempfile.gettempdir()) / f"whoop_{report_type}_{uuid.uuid4().hex[:10]}.png"
    else:
        output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    RENDERERS[report_type](data, output)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("WHOOP visual renderer did not produce a usable PNG")
    return str(output.resolve())


def local_datetime_label(value: str, timezone_offset: str = "") -> str:
    """Format an API timestamp using its record-level UTC offset."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timezone_offset:
            sign = -1 if timezone_offset.startswith("-") else 1
            hours, minutes = timezone_offset.lstrip("+-").split(":", 1)
            from datetime import timedelta, timezone

            parsed = parsed.astimezone(timezone(sign * timedelta(hours=int(hours), minutes=int(minutes))))
        hour = parsed.hour % 12 or 12
        am_pm = "am" if parsed.hour < 12 else "pm"
        return f"{parsed.strftime('%b')} {parsed.day} • {hour}:{parsed.minute:02d}{am_pm} local"
    except Exception:
        return value
