"""Unified ``claudey`` command that dispatches to the installed entry points.

``claudey`` is a thin wrapper over the same entrypoint functions behind the
``hans-*`` commands: ``claudey server`` behaves exactly like ``hans-server``,
``claudey claude`` like ``hans-claude``, and so on. With no arguments it prints
a short usage tree instead of failing.
"""

import sys
from collections.abc import Callable, Sequence

from claudey.core.version import package_version

_ENTRYPOINTS: dict[str, tuple[str, str]] = {
    "server": ("claudey.cli.entrypoints", "serve"),
    "claude": ("claudey.cli.launchers.claude", "launch"),
    "codex": ("claudey.cli.launchers.codex", "launch"),
    "pi": ("claudey.cli.launchers.pi", "launch"),
    "desktop": ("claudey.cli.desktop_entrypoint", "launch"),
}

_DESCRIPTIONS = {
    "server": "Start the local proxy server (hans-server)",
    "claude": "Launch Claude Code through the proxy (hans-claude)",
    "codex": "Launch Codex CLI through the proxy (hans-codex)",
    "pi": "Launch Pi through the proxy (hans-pi)",
    "desktop": "Open the desktop tray app (hans-desktop)",
}


def _usage_tree() -> str:
    lines = [
        f"claudey {package_version()} - unified command for the Claudey proxy",
        "",
        "Usage:",
        "  claudey <command> [args...]",
        "  claudey --version",
        "",
        "Commands:",
    ]
    lines.extend(f"  {name:<10} {_DESCRIPTIONS[name]}" for name in _ENTRYPOINTS)
    return "\n".join(lines)


def _resolve(subcommand: str) -> Callable[[Sequence[str] | None], None]:
    """Import and return the entrypoint function for a subcommand."""

    module_name, attr_name = _ENTRYPOINTS[subcommand]
    module = __import__(module_name, fromlist=[attr_name])
    return getattr(module, attr_name)


def main(argv: Sequence[str] | None = None) -> None:
    """Dispatch ``claudey`` to the matching entrypoint, or print usage."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(_usage_tree())
        return
    if args[0] == "--version":
        print(f"claudey {package_version()}")
        return

    subcommand, *rest = args
    if subcommand not in _ENTRYPOINTS:
        print(f"claudey: unknown command '{subcommand}'", file=sys.stderr)
        print(_usage_tree(), file=sys.stderr)
        raise SystemExit(2)
    _resolve(subcommand)(rest)


if __name__ == "__main__":
    main()
