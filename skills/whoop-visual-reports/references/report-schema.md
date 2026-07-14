# WHOOP visual report schema

The plugin normally builds these payloads from live API records. The schemas
below are for renderer development and offline testing.

## Shared sleep fields

- `total_in_bed_milli`
- `sleep_efficiency`
- `sleep_performance`
- `sleep_consistency`
- `disturbances`
- `recovery_score`
- `hrv`
- `rhr`
- `spo2`
- `skin_temp`
- `phases`: four rows with `label` and `milliseconds`

## Workout fields

- `sport_name`, `title`, `subtitle`
- `duration_second`, `distance_meter`
- `strain`, `average_heart_rate`, `max_heart_rate`
- `kilojoule`, `altitude_gain_meter`, `percent_recorded`
- `zones_milli`: Zone 0 through Zone 5 milliseconds

## Daily recap fields

Daily recap combines the shared sleep fields with:

- `title`, `subtitle`
- `strain`, `max_hr`, `calories`
- `workouts`: normalized workout rows
- `coach_read`, `next_action`, `footer`

Renderers tolerate missing optional fields and display an em dash or zero-state
layout. Values must come from WHOOP or an explicitly labeled calculation.
