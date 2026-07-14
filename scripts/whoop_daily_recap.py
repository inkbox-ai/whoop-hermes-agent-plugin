"""Render today's WHOOP recap for a Hermes no-agent cron job."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    plugin_dir = hermes_home / "plugins" / "whoop"
    if not plugin_dir.is_dir():
        raise RuntimeError(f"Installed WHOOP plugin not found at {plugin_dir}")
    sys.path.insert(0, str(plugin_dir))
    from tools import render_visual_report

    result = render_visual_report({"report_type": "daily_recap"})
    print(result["media_directive"])


if __name__ == "__main__":
    main()
