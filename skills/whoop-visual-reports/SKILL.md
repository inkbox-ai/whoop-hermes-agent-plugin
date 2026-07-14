---
name: whoop-visual-reports
description: Render WHOOP sleep, workout, and daily report cards.
---

# WHOOP Visual Reports Skill

Render consistent, mobile-friendly PNG reports from official WHOOP data. Use the
plugin renderer instead of writing one-off chart code or embedding personal data
inside a template.

## When to Use

- The user asks for a visual, chart, card, image, or polished report.
- A workout or recovery webhook warrants a proactive visual recap.
- A sleep, run, workout, or daily WHOOP summary should be glanceable.

Use text-only coaching when the user did not ask for a visual and an image would
add noise.

## Prerequisites

- WHOOP OAuth must be connected.
- The `whoop` toolset must be enabled.
- Inkbox must be connected when the result should be delivered through
  iMessage.

## How to Run

Call `whoop_render_report` with one report type:

- `sleep_phases` — stage distribution plus recovery metrics.
- `post_sleep` — recovery, sleep efficiency, stages, and sleep scores.
- `workout` — duration/distance, Strain, HR, energy, and Zone 0–5 time.
- `daily_recap` — Recovery, day Strain, sleep, activities, and a short action.

The tool fetches live WHOOP records, normalizes them, writes a PNG, and returns
both `media_path` and `media_directive`.

## Quick Reference

| Request | Tool arguments |
|---|---|
| Latest sleep chart | `report_type="sleep_phases"` |
| Combined morning card | `report_type="post_sleep"` |
| Latest run | `report_type="workout", sport_name="running"` |
| Specific workout | `report_type="workout", workout_id="..."` |
| Today's recap | `report_type="daily_recap"` |
| Prior local day | `report_type="daily_recap", date="YYYY-MM-DD"` |

## Procedure

1. Call `whoop_render_report` directly; do not fetch the same records first
   unless the user also asked for a detailed analysis.
2. Check that the result is successful and contains an absolute `media_path`.
3. Inspect the generated image when a vision tool is available. Confirm that
   text is legible and no content overlaps or clips.
4. Deliver exactly once:
   - Current Inkbox iMessage thread: write one concise caption and include the
     returned `MEDIA:/absolute/path.png` directive in that same normal reply.
   - Different/proactive iMessage conversation: call `inkbox_send_imessage`
     once with `mediaPaths=[media_path]`; do not add another confirmation to
     that destination.
5. Keep accompanying prose short. The card contains the metrics.

## Pitfalls

- Do not call `inkbox_send_imessage` for the iMessage that triggered the
  current turn; Hermes already delivers the final response there.
- Do not put a local path in `mediaUrls`; use `MEDIA:` for the current thread
  or `mediaPaths` for an explicit different-thread send.
- Do not recreate these templates with ad hoc Python.
- Do not claim continuous HR samples, GPS routes, Journal data, Stress Monitor,
  Healthspan, or WHOOP Coach conversation access.
- Daily reports use the configured `WHOOP_TIMEZONE`; provide an explicit date
  when the user's target day is ambiguous.
- Treat absent fields as unavailable rather than inventing values.

## Verification

- The selected WHOOP record IDs appear in the tool result under `source`.
- The output is a non-empty PNG at the returned absolute path.
- The report type matches the user's request.
- Current-thread iMessage delivery contains one caption and one `MEDIA:` line.
- Proactive delivery uses one explicit Inkbox media send.

For normalized input fields and renderer behavior, read
`references/report-schema.md`. For offline template development, run
`scripts/render_report.py` with a report type and normalized JSON file.
