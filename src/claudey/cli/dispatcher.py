"""Unified ``claudey`` command that dispatches to the installed entry points.

``claudey`` is a thin wrapper over the same entrypoint functions behind the
``hans-*`` commands: ``claudey server`` behaves exactly like ``hans-server``,
``claudey claude`` like ``hans-claude``, and so on. With no arguments it prints
a short usage tree instead of failing. ``claudey doctor`` prints a diagnostics
report without launching anything.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from claudey.config import paths
from claudey.config.provider_catalog import PROVIDER_CATALOG, ProviderAuthKind
from claudey.config.server_urls import local_admin_url
from claudey.config.settings import Settings
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
    "doctor": "Print a diagnostic report (version, paths, provider keys)",
}

# Repo checks probed by ``claudey doctor``; tool name -> arguments.
_CI_CHECK_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ruff format": ("ruff", ("format", "--check")),
    "ruff check": ("ruff", ("check",)),
    "ty": ("ty", ("check",)),
    "pytest": ("pytest", ("-q",)),
}

_CI_CHECK_TIMEOUT_SECONDS = 30


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
    lines.extend(
        f"  {name:<10} {_DESCRIPTIONS[name]}" for name in (*_ENTRYPOINTS, "doctor")
    )
    return "\n".join(lines)


def _resolve(subcommand: str) -> Callable[[Sequence[str] | None], None]:
    """Import and return the entrypoint function for a subcommand."""

    module_name, attr_name = _ENTRYPOINTS[subcommand]
    module = __import__(module_name, fromlist=[attr_name])
    return getattr(module, attr_name)


def main(argv: Sequence[str] | None = None) -> None:
    """Dispatch ``claudey`` to the matching entrypoint, or print usage."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_usage_tree(), file=sys.stderr)
        raise SystemExit(2)
    if args[0] in {"-h", "--help"}:
        print(_usage_tree())
        return
    if args[0] == "--version":
        print(f"claudey {package_version()}")
        return

    subcommand, *rest = args
    if subcommand == "doctor":
        raise SystemExit(doctor())
    if subcommand not in _ENTRYPOINTS:
        print(f"claudey: unknown command '{subcommand}'", file=sys.stderr)
        print(_usage_tree(), file=sys.stderr)
        raise SystemExit(2)
    _resolve(subcommand)(rest)


def _attr_configured(settings: Settings, attr: str) -> bool:
    """Return whether a settings attribute holds a non-empty value."""

    value = getattr(settings, attr, None)
    return bool(value is not None and str(value).strip())


def _providers_with_keys(settings: Settings) -> list[str]:
    """Provider ids whose configuration is present (key, config, or account)."""

    configured: list[str] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        if descriptor.local:
            continue
        if descriptor.auth_kind is ProviderAuthKind.CONNECTED_ACCOUNT:
            if paths.openai_auth_path().is_file():
                configured.append(provider_id)
            continue
        attrs = descriptor.configuration_attrs()
        if all(_attr_configured(settings, attr) for attr in attrs):
            configured.append(provider_id)
    return configured


def _project_root() -> Path | None:
    """Repository root when running from a checkout, otherwise None."""

    candidates = (Path(__file__).resolve().parents[3], Path.cwd())
    for candidate in candidates:
        pyproject = candidate / "pyproject.toml"
        try:
            if pyproject.is_file() and 'name = "claudey"' in pyproject.read_text(
                encoding="utf-8"
            ):
                return candidate
        except OSError:
            continue
    return None


def _check_status(root: Path, tool: str, arguments: Sequence[str]) -> str:
    """Run one repo check; 'not checked' when the tool is unavailable or slow."""

    command = [tool] if shutil.which(tool) else ["uv", "run", tool]
    try:
        completed = subprocess.run(
            [*command, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_CI_CHECK_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.TimeoutExpired:
        return "not checked"
    return "ok" if completed.returncode == 0 else "fail"


def _ci_checks() -> dict[str, str]:
    """Status of the repo checks, probed concurrently when possible."""

    root = _project_root()
    if root is None:
        return dict.fromkeys(_CI_CHECK_SPECS, "not checked")
    with ThreadPoolExecutor(max_workers=len(_CI_CHECK_SPECS)) as pool:
        futures = {
            label: pool.submit(_check_status, root, tool, args)
            for label, (tool, args) in _CI_CHECK_SPECS.items()
        }
    return {label: futures[label].result() for label in _CI_CHECK_SPECS}


def doctor() -> int:
    """Print a diagnostic report for the Claudey installation."""

    try:
        settings = Settings()
    except ValueError as exc:
        print(f"Claudey v{package_version()}")
        print(f"  config error: {exc}")
        return 1

    module_path = Path(__file__).resolve().parents[1]
    config_dir = f"~/{paths.HANS_CONFIG_DIRNAME}"
    env_file = f"{config_dir}/{paths.HANS_ENV_FILENAME}"
    with_keys = _providers_with_keys(settings)
    checks = _ci_checks()

    print(f"Claudey v{package_version()}")
    print(f"  {'Module path:':<13}{module_path}")
    print(f"  {'Config dir:':<13}{config_dir}")
    print(f"  {'Env file:':<13}{env_file}")
    print(f"  {'Admin URL:':<13}{local_admin_url(settings)}")
    print(f"  {'Server port:':<13}{settings.port}")
    print(f"  Providers with keys: {', '.join(with_keys) if with_keys else 'none'}")
    print(f"  Providers total: {len(PROVIDER_CATALOG)}")
    check_text = " | ".join(f"{label}: {status}" for label, status in checks.items())
    print(f"  CI checks:    {check_text}")
    return 0


if __name__ == "__main__":
    main()
