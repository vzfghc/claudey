import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest

import claudey.core.version as version_module


def test_package_version_uses_installed_distribution_metadata() -> None:
    assert version_module.package_version() == distribution_version("claudey")


def test_package_version_has_explicit_uninstalled_source_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_distribution_name: str) -> str:
        raise PackageNotFoundError("claudey")

    monkeypatch.setattr(version_module, "distribution_version", missing)

    assert version_module.package_version() == "0+unknown"


def test_package_version_does_not_hide_invalid_installed_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(_distribution_name: str) -> str:
        raise ValueError("invalid metadata")

    monkeypatch.setattr(version_module, "distribution_version", invalid)

    with pytest.raises(ValueError, match="invalid metadata"):
        version_module.package_version()


def test_asset_version_matches_source_pyproject_version() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text("utf-8"))

    # Source truth, not installed metadata: deterministic even when the venv
    # lags the source tree, so a stale distribution can never desync cache-busters.
    assert version_module.asset_version() == pyproject["project"]["version"]


def test_asset_version_falls_back_to_installed_metadata_when_pyproject_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingPyproject:
        def read_text(self, *args: object, **kwargs: object) -> str:
            raise FileNotFoundError("pyproject.toml")

    monkeypatch.setattr(version_module, "_SOURCE_PYPROJECT", MissingPyproject())

    assert version_module.asset_version() == distribution_version("claudey")
