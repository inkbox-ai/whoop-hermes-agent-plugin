"""WHOOP Coach plugin registration for Hermes Agent + Inkbox."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from .cli import handle_cli, setup_argparse
    from .oauth import register_route
    from .provider import register_provider
    from .tools import register_tools
except ImportError:  # pragma: no cover
    from cli import handle_cli, setup_argparse
    from oauth import register_route
    from provider import register_provider
    from tools import register_tools


logger = logging.getLogger(__name__)


def _inkbox_plugin():
    module = sys.modules.get("hermes_plugins.inkbox")
    if module is None:
        raise RuntimeError(
            "WHOOP requires the Inkbox Hermes plugin. Install and enable "
            "inkbox-ai/hermes-agent-plugin before enabling WHOOP."
        )
    return module


def _register_skills(ctx) -> None:
    skills = Path(__file__).parent / "skills"
    for child in sorted(skills.iterdir()) if skills.exists() else []:
        skill = child / "SKILL.md"
        if child.is_dir() and skill.exists():
            ctx.register_skill(child.name, skill)


def register(ctx) -> None:
    inkbox = _inkbox_plugin()
    register_provider(inkbox)
    register_route(inkbox)
    register_tools(ctx)
    _register_skills(ctx)
    ctx.register_cli_command(
        name="whoop",
        help="Configure and inspect the WHOOP Coach integration",
        setup_fn=setup_argparse,
        handler_fn=handle_cli,
        description="Official WHOOP OAuth, data tools, and verified webhook coaching.",
    )
    logger.info("WHOOP Coach plugin registered")
