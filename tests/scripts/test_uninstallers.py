import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

HANS_COMMANDS = (
    "hans-desktop",
    "hans-server",
    "hans-claude",
    "hans-codex",
    "hans-pi",
    "hans-init",
    "claudey",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _powershells() -> tuple[str, ...]:
    candidates = (shutil.which("pwsh"), shutil.which("powershell"))
    return tuple(dict.fromkeys(path for path in candidates if path is not None))


def _create_windows_shortcut(
    powershell: str,
    shortcut_path: Path,
    target_path: Path,
) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ | {
        "HANS_TEST_SHORTCUT": str(shortcut_path),
        "HANS_TEST_TARGET": str(target_path),
    }
    subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-Command",
            (
                "$shell = New-Object -ComObject WScript.Shell; "
                "$shortcut = $shell.CreateShortcut($env:HANS_TEST_SHORTCUT); "
                "$shortcut.TargetPath = $env:HANS_TEST_TARGET; "
                "$shortcut.Save()"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


@dataclass
class PosixUninstallHarness:
    home: Path
    bin_dir: Path
    tool_bin: Path
    hans_home: Path
    log: Path
    env: dict[str, str]

    def run(
        self,
        *args: str,
        fail_step: str = "",
        include_uv: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        uv = self.bin_dir / "uv"
        if not include_uv and uv.exists():
            uv.unlink()
        return subprocess.run(
            ["/bin/sh", str(_repo_root() / "scripts" / "uninstall.sh"), *args],
            check=False,
            capture_output=True,
            text=True,
            env=self.env | {"FAIL_STEP": fail_step},
        )

    def calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()

    def remove_entry_points(self) -> None:
        for name in HANS_COMMANDS:
            (self.tool_bin / name).unlink(missing_ok=True)

    def use_process_list_fallback(self, process_line: str) -> None:
        fallback_bin = self.home.parent / "fallback-bin"
        fallback_bin.mkdir()
        _write_executable(
            fallback_bin / "ps",
            """#!/bin/sh
printf '%s\n' "$HANS_PS_OUTPUT"
""",
        )
        awk = shutil.which("awk", path=self.env["PATH"])
        if awk is None:
            pytest.skip("awk is required for the POSIX process fallback scenario")
        # Symlink, not copy: copying the system awk breaks its arm64e code
        # signature, so the copied binary is killed on execution on macOS.
        os.symlink(awk, fallback_bin / "awk")
        self.env["HANS_PS_OUTPUT"] = process_line
        self.env["PATH"] = str(fallback_bin)


@pytest.fixture
def posix_uninstall_harness(tmp_path: Path) -> PosixUninstallHarness:
    if os.name == "nt":
        pytest.skip("POSIX uninstaller scenarios run on POSIX hosts")

    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    tool_bin = tmp_path / "tool-bin"
    hans_home = home / ".claudey"
    log = tmp_path / "calls.log"
    for path in (bin_dir, tool_bin, hans_home):
        path.mkdir(parents=True)
    (hans_home / "config.json").write_text("{}", encoding="utf-8")
    for name in HANS_COMMANDS:
        _write_executable(tool_bin / name, "#!/bin/sh\nexit 0\n")

    _write_executable(bin_dir / "claude", "#!/bin/sh\nexit 0\n")
    _write_executable(bin_dir / "codex", "#!/bin/sh\nexit 0\n")
    _write_executable(bin_dir / "pi", "#!/bin/sh\nexit 0\n")
    _write_executable(
        bin_dir / "pgrep",
        """#!/bin/sh
# Hermetic pgrep: never consult the real process table, which races with
# concurrent installer-test subprocesses named like hans-* in CI workers.
[ -n "${HANS_RUNNING_COMMAND:-}" ] || exit 1
case "$*" in
    *"$HANS_RUNNING_COMMAND"*) printf '4242\n'; exit 0 ;;
    *) exit 1 ;;
esac
""",
    )
    _write_executable(
        bin_dir / "uv",
        """#!/bin/sh
echo "uv:$*" >> "$CALL_LOG"
if [ "${1:-}" = "tool" ] && [ "${2:-}" = "dir" ] && [ "${3:-}" = "--bin" ]; then
    if [ "$FAIL_STEP" = "tool-dir" ]; then
        echo "tool directory unavailable" >&2
        exit 41
    fi
    printf '%s\n' "$FAKE_TOOL_BIN"
    exit 0
fi
if [ "${1:-}" = "tool" ] && [ "${2:-}" = "uninstall" ]; then
    if [ "$FAIL_STEP" = "uninstall" ]; then
        echo "permission denied while removing tool" >&2
        exit 42
    fi
    if [ "$FAIL_STEP" = "missing" ] || [ "$FAIL_STEP" = "stale-entrypoint" ]; then
        echo 'Tool `claudey` is not installed' >&2
        exit 2
    fi
    for name in hans-desktop hans-server hans-claude hans-codex hans-pi hans-init claudey; do
        /bin/rm -f "$FAKE_TOOL_BIN/$name"
    done
    echo "Uninstalled claudey"
    exit 0
fi
exit 43
""",
    )
    _write_executable(
        bin_dir / "rm",
        """#!/bin/sh
echo "rm:$*" >> "$CALL_LOG"
if [ "$FAIL_STEP" = "purge" ] && [ "$*" = "-rf $HOME/.claudey" ]; then
    echo "simulated purge failure" >&2
    exit 44
fi
exec /bin/rm "$@"
""",
    )
    _write_executable(
        bin_dir / "uname",
        """#!/bin/sh
printf '%s\n' "$FAKE_UNAME"
""",
    )

    app = home / "Applications" / "Claudey.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    (contents / ".claudey-owner").write_text(
        "io.github.vzfghc.claudey\n",
        encoding="utf-8",
    )
    desktop = home / "Desktop"
    desktop.mkdir()
    (desktop / "Claudey.app").symlink_to(app, target_is_directory=True)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CALL_LOG": str(log),
            "FAKE_TOOL_BIN": str(tool_bin),
            "FAKE_UNAME": "Darwin",
            "FAIL_STEP": "",
        }
    )
    env.pop("XDG_BIN_HOME", None)
    return PosixUninstallHarness(home, bin_dir, tool_bin, hans_home, log, env)


def test_uninstall_sh_removes_and_verifies_only_hans(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    result = posix_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "Claudey has been removed and verified." in result.stdout
    assert not posix_uninstall_harness.hans_home.exists()
    assert all(
        not (posix_uninstall_harness.tool_bin / name).exists() for name in HANS_COMMANDS
    )
    assert (posix_uninstall_harness.bin_dir / "uv").exists()
    assert (posix_uninstall_harness.bin_dir / "claude").exists()
    assert (posix_uninstall_harness.bin_dir / "codex").exists()
    assert (posix_uninstall_harness.bin_dir / "pi").exists()
    assert posix_uninstall_harness.calls() == [
        "uv:tool dir --bin",
        "uv:tool uninstall claudey",
        f"rm:-f {posix_uninstall_harness.home / 'Desktop' / 'Claudey.app'}",
        f"rm:-rf {posix_uninstall_harness.home / 'Applications' / 'Claudey.app'}",
        f"rm:-rf {posix_uninstall_harness.hans_home}",
    ]


def test_uninstall_sh_removes_legacy_fcc_shims(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    tool_bin = posix_uninstall_harness.tool_bin
    for name in ("fcc-server", "fcc-claude", "fcc-codex", "fcc-pi", "fcc-desktop"):
        _write_executable(
            tool_bin / name,
            f"#!/bin/sh\nprintf '%s\\n' '{name} is deprecated: use hans-server' >&2\nexit 2\n",
        )
    foreign = tool_bin / "fcc-other"
    foreign.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = posix_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "Removing legacy fcc-* deprecation shims" in result.stdout
    for name in ("fcc-server", "fcc-claude", "fcc-codex", "fcc-pi", "fcc-desktop"):
        assert not (tool_bin / name).exists(), name
    assert foreign.exists()
    assert not posix_uninstall_harness.hans_home.exists()


def test_uninstall_sh_is_idempotent_when_tool_is_already_absent(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    posix_uninstall_harness.remove_entry_points()

    result = posix_uninstall_harness.run(fail_step="missing")

    assert result.returncode == 0, result.stderr
    assert not posix_uninstall_harness.hans_home.exists()
    assert "already absent" in result.stdout


def test_uninstall_sh_preserves_unrelated_macos_desktop_link(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    desktop_link = posix_uninstall_harness.home / "Desktop" / "Claudey.app"
    desktop_link.unlink()
    unrelated = posix_uninstall_harness.home / "Unrelated.app"
    unrelated.mkdir()
    desktop_link.symlink_to(unrelated, target_is_directory=True)

    result = posix_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "non-Claudey link" in result.stdout
    assert desktop_link.readlink() == unrelated


def test_uninstall_sh_preserves_unowned_macos_app_bundle(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    app = posix_uninstall_harness.home / "Applications" / "Claudey.app"
    owner_file = app / "Contents" / ".claudey-owner"
    owner_file.unlink()
    sentinel = app / "foreign.txt"
    sentinel.write_text("keep", encoding="utf-8")
    desktop_link = posix_uninstall_harness.home / "Desktop" / "Claudey.app"

    result = posix_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "not managed by Claudey" in result.stdout
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert desktop_link.is_symlink()


def test_uninstall_sh_does_not_touch_macos_paths_on_linux(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    posix_uninstall_harness.env["FAKE_UNAME"] = "Linux"
    app = posix_uninstall_harness.home / "Applications" / "Claudey.app"
    desktop_link = posix_uninstall_harness.home / "Desktop" / "Claudey.app"

    result = posix_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert app.is_dir()
    assert desktop_link.is_symlink()


@pytest.mark.parametrize("failure", ["tool-dir", "uninstall", "stale-entrypoint"])
def test_uninstall_sh_preserves_config_when_tool_removal_is_unconfirmed(
    posix_uninstall_harness: PosixUninstallHarness,
    failure: str,
) -> None:
    result = posix_uninstall_harness.run(fail_step=failure)

    assert result.returncode != 0
    assert posix_uninstall_harness.hans_home.exists()
    assert "Claudey has been removed and verified." not in result.stdout
    assert not any(call.startswith("rm:") for call in posix_uninstall_harness.calls())


def test_uninstall_sh_requires_uv_before_deleting_config(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    result = posix_uninstall_harness.run(include_uv=False)

    assert result.returncode != 0
    assert posix_uninstall_harness.hans_home.exists()
    assert "uv is required" in result.stderr
    assert posix_uninstall_harness.calls() == []


def test_uninstall_sh_reports_purge_failure_after_verified_tool_removal(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    result = posix_uninstall_harness.run(fail_step="purge")

    assert result.returncode != 0
    assert posix_uninstall_harness.hans_home.exists()
    assert all(
        not (posix_uninstall_harness.tool_bin / name).exists() for name in HANS_COMMANDS
    )
    assert "Claudey has been removed and verified." not in result.stdout


def test_uninstall_sh_dry_run_is_non_mutating(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    result = posix_uninstall_harness.run("--dry-run")

    assert result.returncode == 0, result.stderr
    assert posix_uninstall_harness.hans_home.exists()
    assert all(
        (posix_uninstall_harness.tool_bin / name).exists() for name in HANS_COMMANDS
    )
    assert posix_uninstall_harness.calls() == []
    assert "Dry run complete. No changes were made." in result.stdout


def test_uninstall_sh_rejects_invalid_options_before_mutation(
    posix_uninstall_harness: PosixUninstallHarness,
) -> None:
    result = posix_uninstall_harness.run("--unknown")

    assert result.returncode != 0
    assert posix_uninstall_harness.hans_home.exists()
    assert posix_uninstall_harness.calls() == []


@pytest.mark.parametrize(
    ("command_name", "process_args"),
    (
        ("claudey", "/home/user/.local/bin/claudey"),
        ("hans-server", "/usr/bin/python3 /home/user/.local/bin/hans-server"),
    ),
)
def test_uninstall_sh_process_fallback_reads_full_command_line(
    posix_uninstall_harness: PosixUninstallHarness,
    command_name: str,
    process_args: str,
) -> None:
    posix_uninstall_harness.use_process_list_fallback(f"4242 {process_args}")

    result = posix_uninstall_harness.run()

    assert result.returncode != 0
    assert posix_uninstall_harness.hans_home.exists()
    assert posix_uninstall_harness.calls() == []
    assert command_name in result.stderr


@dataclass
class PowerShellUninstallHarness:
    home: Path
    bin_dir: Path
    tool_bin: Path
    hans_home: Path
    log: Path
    env: dict[str, str]
    powershell: str
    wrapper: Path

    def run(
        self,
        *,
        fail_step: str = "",
        include_uv: bool = True,
        dry_run: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        uv = self.bin_dir / "uv.cmd"
        if not include_uv and uv.exists():
            uv.unlink()
        return subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.wrapper),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=self.env
            | {
                "FAIL_STEP": fail_step,
                "UNINSTALL_DRY_RUN": "1" if dry_run else "0",
            },
        )

    def calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()

    def remove_entry_points(self) -> None:
        for name in HANS_COMMANDS:
            (self.tool_bin / f"{name}.cmd").unlink(missing_ok=True)


@pytest.fixture(
    params=_powershells() or (None,),
    ids=lambda path: Path(path).name if path is not None else "unavailable",
)
def powershell_uninstall_harness(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> PowerShellUninstallHarness:
    powershell = request.param
    if powershell is None or os.name != "nt":
        pytest.skip("PowerShell uninstaller scenarios run on Windows hosts")

    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    tool_bin = tmp_path / "tool-bin"
    hans_home = home / ".claudey"
    app_data = tmp_path / "app-data"
    log = tmp_path / "calls.log"
    for path in (bin_dir, tool_bin, hans_home, app_data):
        path.mkdir(parents=True)
    (hans_home / "config.json").write_text("{}", encoding="utf-8")
    for name in HANS_COMMANDS:
        (tool_bin / f"{name}.cmd").write_text(
            "@echo off\nexit /b 0\n", encoding="utf-8"
        )
    for name in ("claude", "codex", "pi"):
        (bin_dir / f"{name}.cmd").write_text("@echo off\nexit /b 0\n", encoding="utf-8")

    uv_commands = " ".join(HANS_COMMANDS)
    (bin_dir / "uv.cmd").write_text(
        rf"""@echo off
echo uv:%*>>"%CALL_LOG%"
if "%1"=="tool" if "%2"=="dir" if "%3"=="--bin" goto tool_bin
if "%1"=="tool" if "%2"=="uninstall" goto uninstall
exit /b 53
:tool_bin
if "%FAIL_STEP%"=="tool-dir" echo tool directory unavailable 1>&2 & exit /b 51
echo %FAKE_TOOL_BIN%
exit /b 0
:uninstall
if "%FAIL_STEP%"=="uninstall" echo permission denied while removing tool 1>&2 & exit /b 52
if "%FAIL_STEP%"=="missing" echo Tool `claudey` is not installed 1>&2 & exit /b 2
if "%FAIL_STEP%"=="stale-entrypoint" echo Tool `claudey` is not installed 1>&2 & exit /b 2
for %%C in ({uv_commands}) do del /q "%FAKE_TOOL_BIN%\%%C.cmd" 2>nul
echo Uninstalled claudey
exit /b 0
""",
        encoding="utf-8",
    )

    wrapper = tmp_path / "run-uninstaller.ps1"
    wrapper.write_text(
        r"""Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
function Remove-Item {
    [CmdletBinding()]
    param(
        [string] $LiteralPath,
        [switch] $Recurse,
        [switch] $Force
    )
    Add-Content -LiteralPath $env:CALL_LOG -Value "remove:$LiteralPath"
    if (
        $env:FAIL_STEP -eq "purge" -and
        $LiteralPath -eq (Join-Path $env:USERPROFILE ".claudey")
    ) {
        throw "simulated purge failure"
    }
    Microsoft.PowerShell.Management\Remove-Item @PSBoundParameters
}
$installer = [scriptblock]::Create([IO.File]::ReadAllText($env:HANS_UNINSTALLER))
if ($env:UNINSTALL_DRY_RUN -eq "1") {
    & $installer -DryRun
}
else {
    & $installer
}
""",
        encoding="utf-8",
    )

    desktop_shortcut = home / "Desktop" / "Claudey.lnk"
    start_shortcut = (
        app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Claudey.lnk"
    )
    for shortcut in (desktop_shortcut, start_shortcut):
        _create_windows_shortcut(
            powershell,
            shortcut,
            tool_bin / "hans-desktop.cmd",
        )

    system_root = os.environ["SYSTEMROOT"]
    env = os.environ.copy()
    env.update(
        {
            "PATH": os.pathsep.join(
                [str(bin_dir), str(Path(system_root) / "System32"), system_root]
            ),
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(app_data),
            "CALL_LOG": str(log),
            "FAKE_TOOL_BIN": str(tool_bin),
            "HANS_UNINSTALLER": str(_repo_root() / "scripts" / "uninstall.ps1"),
            "FAIL_STEP": "",
            "UNINSTALL_DRY_RUN": "0",
        }
    )
    return PowerShellUninstallHarness(
        home, bin_dir, tool_bin, hans_home, log, env, powershell, wrapper
    )


def test_uninstall_ps1_removes_and_verifies_only_hans(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    result = powershell_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "Claudey has been removed and verified." in result.stdout
    assert not powershell_uninstall_harness.hans_home.exists()
    assert all(
        not (powershell_uninstall_harness.tool_bin / f"{name}.cmd").exists()
        for name in HANS_COMMANDS
    )
    assert (powershell_uninstall_harness.bin_dir / "uv.cmd").exists()
    assert (powershell_uninstall_harness.bin_dir / "claude.cmd").exists()
    assert (powershell_uninstall_harness.bin_dir / "codex.cmd").exists()
    assert (powershell_uninstall_harness.bin_dir / "pi.cmd").exists()
    assert powershell_uninstall_harness.calls() == [
        "uv:tool dir --bin",
        "uv:tool uninstall claudey",
        f"remove:{Path(powershell_uninstall_harness.env['USERPROFILE']) / 'Desktop' / 'Claudey.lnk'}",
        f"remove:{Path(powershell_uninstall_harness.env['APPDATA']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Claudey.lnk'}",
        f"remove:{powershell_uninstall_harness.hans_home}",
    ]


def test_uninstall_ps1_removes_legacy_fcc_shims(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    tool_bin = powershell_uninstall_harness.tool_bin
    for name in ("fcc-server", "fcc-claude", "fcc-codex", "fcc-pi", "fcc-desktop"):
        (tool_bin / f"{name}.cmd").write_text(
            f"@echo off\necho {name} is deprecated: use hans-server 1>&2\nexit /b 2\n",
            encoding="utf-8",
        )
    foreign = tool_bin / "fcc-other.cmd"
    foreign.write_text("@echo off\nexit /b 0\n", encoding="utf-8")

    result = powershell_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "Removing legacy fcc-* deprecation shims" in result.stdout
    for name in ("fcc-server", "fcc-claude", "fcc-codex", "fcc-pi", "fcc-desktop"):
        assert not (tool_bin / f"{name}.cmd").exists(), name
    assert foreign.exists()
    assert not powershell_uninstall_harness.hans_home.exists()


def test_uninstall_ps1_preserves_unowned_desktop_shortcut(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    desktop_shortcut = (
        Path(powershell_uninstall_harness.env["USERPROFILE"])
        / "Desktop"
        / "Claudey.lnk"
    )
    unrelated_target = powershell_uninstall_harness.home / "unrelated.cmd"
    unrelated_target.write_text("@echo off\n", encoding="utf-8")
    _create_windows_shortcut(
        powershell_uninstall_harness.powershell,
        desktop_shortcut,
        unrelated_target,
    )
    original_shortcut = desktop_shortcut.read_bytes()

    result = powershell_uninstall_harness.run()

    assert result.returncode == 0, result.stderr
    assert "not managed by Claudey" in result.stdout
    assert desktop_shortcut.read_bytes() == original_shortcut


def test_uninstall_ps1_is_idempotent_when_tool_is_already_absent(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    powershell_uninstall_harness.remove_entry_points()

    result = powershell_uninstall_harness.run(fail_step="missing")

    assert result.returncode == 0, result.stderr
    assert not powershell_uninstall_harness.hans_home.exists()
    assert "already absent" in result.stdout


@pytest.mark.parametrize("failure", ["tool-dir", "uninstall", "stale-entrypoint"])
def test_uninstall_ps1_preserves_config_when_tool_removal_is_unconfirmed(
    powershell_uninstall_harness: PowerShellUninstallHarness,
    failure: str,
) -> None:
    result = powershell_uninstall_harness.run(fail_step=failure)

    assert result.returncode != 0
    assert powershell_uninstall_harness.hans_home.exists()
    assert "Claudey has been removed and verified." not in result.stdout
    assert not any(
        call.startswith("remove:") for call in powershell_uninstall_harness.calls()
    )


def test_uninstall_ps1_requires_uv_before_deleting_config(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    result = powershell_uninstall_harness.run(include_uv=False)

    assert result.returncode != 0
    assert powershell_uninstall_harness.hans_home.exists()
    assert "uv is required" in result.stderr
    assert powershell_uninstall_harness.calls() == []


def test_uninstall_ps1_reports_purge_failure_after_verified_tool_removal(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    result = powershell_uninstall_harness.run(fail_step="purge")

    assert result.returncode != 0
    assert powershell_uninstall_harness.hans_home.exists()
    assert all(
        not (powershell_uninstall_harness.tool_bin / f"{name}.cmd").exists()
        for name in HANS_COMMANDS
    )
    assert "Claudey has been removed and verified." not in result.stdout


def test_uninstall_ps1_dry_run_is_non_mutating(
    powershell_uninstall_harness: PowerShellUninstallHarness,
) -> None:
    result = powershell_uninstall_harness.run(dry_run=True)

    assert result.returncode == 0, result.stderr
    assert powershell_uninstall_harness.hans_home.exists()
    assert all(
        (powershell_uninstall_harness.tool_bin / f"{name}.cmd").exists()
        for name in HANS_COMMANDS
    )
    assert powershell_uninstall_harness.calls() == []
    assert "Dry run complete. No changes were made." in result.stdout


def test_uninstallers_guard_running_commands_and_preserve_shared_owners() -> None:
    shell = (_repo_root() / "scripts" / "uninstall.sh").read_text(encoding="utf-8")
    powershell = (_repo_root() / "scripts" / "uninstall.ps1").read_text(
        encoding="utf-8"
    )

    assert "pgrep" in shell
    assert "Get-Process" in powershell
    for text in (shell, powershell):
        for command in HANS_COMMANDS:
            assert command in text
        assert "npm uninstall" not in text
        assert "uv self uninstall" not in text
        assert "uv python uninstall" not in text
        assert "is not installed" in text
        assert "no tool" not in text
        assert "nothing to uninstall" not in text


def test_readme_uninstall_uses_raw_urls_and_verification_contract() -> None:
    text = (_repo_root() / "README.md").read_text(encoding="utf-8")

    assert (
        'curl -fsSL "https://raw.githubusercontent.com/'
        'vzfghc/claudey/main/scripts/uninstall.sh" | sh'
    ) in text
    assert (
        '& ([scriptblock]::Create((irm "https://raw.githubusercontent.com/'
        'vzfghc/claudey/main/scripts/uninstall.ps1")))'
    ) in text
    assert "verifies every HANS command is gone" in text
