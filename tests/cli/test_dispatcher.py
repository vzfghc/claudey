"""Tests for the unified ``claudey`` dispatcher command."""

from pathlib import Path
from unittest.mock import patch

import pytest

from claudey.cli import dispatcher
from claudey.config.provider_catalog import PROVIDER_CATALOG


def test_dispatcher_no_args_prints_usage_tree_and_exits_2(capsys) -> None:
    with (
        patch.object(dispatcher, "package_version", return_value="5.0.0"),
        pytest.raises(SystemExit) as exc,
    ):
        dispatcher.main([])

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "claudey 5.0.0" in captured.err
    assert "server" in captured.err
    assert "claude" in captured.err
    assert "codex" in captured.err
    assert "pi" in captured.err
    assert "desktop" in captured.err
    assert "doctor" in captured.err


def test_dispatcher_version_flag_prints_branded_version(capsys) -> None:
    with patch.object(dispatcher, "package_version", return_value="5.0.0"):
        dispatcher.main(["--version"])

    assert capsys.readouterr().out == "claudey 5.0.0\n"


def test_dispatcher_forwards_server_args_to_entrypoint() -> None:
    from claudey.cli import entrypoints

    with patch.object(entrypoints, "serve") as serve:
        dispatcher.main(["server", "--version"])

    serve.assert_called_once_with(["--version"])


def test_dispatcher_forwards_claude_args_to_launcher() -> None:
    from claudey.cli.launchers import claude

    with patch.object(claude, "launch") as launch:
        dispatcher.main(["claude", "exec", "hello"])

    launch.assert_called_once_with(["exec", "hello"])


def test_dispatcher_unknown_command_prints_error_and_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        dispatcher.main(["bogus"])

    assert exc.value.code == 2
    assert "unknown command 'bogus'" in capsys.readouterr().err


def test_dispatcher_usage_tree_lists_doctor(capsys) -> None:
    with patch.object(dispatcher, "package_version", return_value="5.2.0"):
        dispatcher.main(["--help"])

    out = capsys.readouterr().out
    assert "doctor" in out
    assert "diagnostic report" in out


class _FakeDoctorSettings:
    host = "0.0.0.0"
    port = 8082
    nvidia_nim_api_key = "test-key"
    openai_api_key = ""


def test_dispatcher_doctor_prints_diagnostic_report(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dispatcher, "Settings", _FakeDoctorSettings)
    monkeypatch.setattr(
        dispatcher,
        "package_version",
        lambda: "5.2.0",
    )
    monkeypatch.setattr(
        dispatcher,
        "_ci_checks",
        lambda: {
            "ruff format": "ok",
            "ruff check": "ok",
            "ty": "ok",
            "pytest": "not checked",
        },
    )
    monkeypatch.setattr(
        dispatcher.paths,
        "openai_auth_path",
        lambda: Path("/nonexistent/auth/openai.json"),
    )

    assert dispatcher.doctor() == 0

    out = capsys.readouterr().out
    assert "Claudey v5.2.0" in out
    assert "  Module path:" in out
    assert "Config dir:  ~/.fcc" in out
    assert "Env file:    ~/.fcc/.env" in out
    assert "Admin URL:   http://127.0.0.1:8082/admin" in out
    assert "Server port: 8082" in out
    assert "Providers with keys: nvidia_nim" in out
    assert f"Providers total: {len(PROVIDER_CATALOG)}" in out
    assert "CI checks:    ruff format: ok | ruff check: ok | ty: ok" in out
    assert "pytest: not checked" in out


def test_dispatcher_doctor_main_routes_and_exits_zero(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dispatcher, "Settings", _FakeDoctorSettings)
    monkeypatch.setattr(dispatcher, "package_version", lambda: "5.2.0")
    monkeypatch.setattr(
        dispatcher,
        "_ci_checks",
        lambda: dict.fromkeys(dispatcher._CI_CHECK_SPECS, "not checked"),
    )
    monkeypatch.setattr(
        dispatcher.paths,
        "openai_auth_path",
        lambda: Path("/nonexistent/auth/openai.json"),
    )

    with pytest.raises(SystemExit) as exc:
        dispatcher.main(["doctor"])

    assert exc.value.code == 0
    assert "Providers total:" in capsys.readouterr().out
