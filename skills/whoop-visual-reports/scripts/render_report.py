#!/usr/bin/env python3
"""Render normalized WHOOP report JSON for offline template development."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from visuals import RENDERERS, render_report_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_type", choices=sorted(RENDERERS))
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    print(render_report_data(args.report_type, payload, args.output))


if __name__ == "__main__":
    main()
