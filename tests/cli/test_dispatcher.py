"""Tests for the unified ``claudey`` dispatcher command."""

from unittest.mock import patch

import pytest

from claudey.cli import dispatcher


def test_dispatcher_no_args_prints_usage_tree(capsys) -> None:
    with patch.object(dispatcher, "package_version", return_value="5.0.0"):
        dispatcher.main([])

    out = capsys.readouterr().out
    assert "claudey 5.0.0" in out
    assert "server" in out
    assert "claude" in out
    assert "codex" in out
    assert "pi" in out
    assert "desktop" in out


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
