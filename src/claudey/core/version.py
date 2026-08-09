"""Canonical Claudey package version and static-asset cache-buster."""

import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

_DISTRIBUTION_NAME = "claudey"
_UNKNOWN_VERSION = "0+unknown"
_SOURCE_PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def package_version() -> str:
    """Return installed metadata, or an explicit source-only fallback."""
    try:
        return distribution_version(_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return _UNKNOWN_VERSION


def asset_version() -> str:
    """Return the cache-buster version for admin static assets.

    Single source of truth is the source ``pyproject.toml`` ``[project].version``,
    so a stale/mismatched installed distribution can never serve stale assets and
    the admin guard test stays deterministic against SOURCE rather than installed
    ``importlib.metadata``.

    Falls back to :func:`package_version` only for non-source installs where the
    project file is absent from disk.
    """
    try:
        data = tomllib.loads(_SOURCE_PYPROJECT.read_text("utf-8"))
        return str(data["project"]["version"])
    except FileNotFoundError, KeyError, OSError, tomllib.TOMLDecodeError:
        return package_version()
