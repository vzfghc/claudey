param(
    [switch] $DryRun,
    [switch] $Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [object[]] $RemainingArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PackageName = "claudey"
$HansHomeDirname = ".fcc"
$HansCommands = @(
    # Include retired entry points so older installations are fully stopped and removed.
    "hans-desktop",
    "hans-server",
    "hans-claude",
    "hans-codex",
    "hans-pi",
    "hans-init",
    "claudey"
)
# Legacy fcc-* deprecation shims installed via install.ps1 -LegacyFcc.
$LegacyFccCommands = @(
    "fcc-server",
    "fcc-claude",
    "fcc-codex",
    "fcc-pi",
    "fcc-desktop"
)
$script:UvPath = ""
$script:UvToolBin = ""

function Show-Usage {
    @"
Usage: uninstall.ps1 [options]

Removes the Claudey uv tool and deletes ~/.fcc/ after removal is verified.
Also removes the legacy fcc-* deprecation shims installed by -LegacyFcc.
Does not remove uv, Claude Code, Codex, Pi, the uv-managed Python runtime, or shared PATH entries.

Options:
  -DryRun                Print commands without running them.
  -Help                  Show this help text.
"@
}

function Write-Step {
    param([string] $Message)

    Write-Host ""
    Write-Host "==> $Message"
}

function Format-Argument {
    param([string] $Value)

    if ($Value -match '^[A-Za-z0-9_./:@%+=,\[\]\\-]+$') {
        return $Value
    }
    return "'" + ($Value -replace "'", "''") + "'"
}

function Format-Command {
    param(
        [string] $FilePath,
        [string[]] $Arguments = @()
    )

    $parts = @($FilePath) + $Arguments
    return ($parts | ForEach-Object { Format-Argument ([string] $_) }) -join " "
}

function Get-ApplicationCommand {
    param([string] $Name)

    $commands = @(Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)
    if ($commands.Count -eq 0) {
        return $null
    }
    return $commands[0]
}

function Invoke-NativeResult {
    param(
        [string] $FilePath,
        [string[]] $Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $global:LASTEXITCODE = 0
        $output = (& $FilePath @Arguments 2>&1 | Out-String).Trim()
        return [pscustomobject] @{
            ExitCode = $LASTEXITCODE
            Output = $output
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Test-MissingUvToolError {
    param([string] $Output)

    $normalized = $Output.ToLowerInvariant()
    return $normalized.Contains($PackageName) -and $normalized.Contains("is not installed")
}

function Add-PathEntry {
    param([string] $PathEntry)

    if ([string]::IsNullOrWhiteSpace($PathEntry)) {
        return
    }
    $separator = [IO.Path]::PathSeparator
    $entries = @()
    if (-not [string]::IsNullOrEmpty($env:Path)) {
        $entries = $env:Path -split [regex]::Escape([string] $separator)
    }
    if ($entries -notcontains $PathEntry) {
        $env:Path = "$PathEntry$separator$env:Path"
    }
}

function Add-KnownUvPaths {
    Add-PathEntry (Join-Path $env:USERPROFILE ".local\bin")
    Add-PathEntry (Join-Path $env:USERPROFILE ".cargo\bin")
}

function Assert-NoHansProcessesRunning {
    $running = @()
    foreach ($commandName in $HansCommands) {
        $processes = @(Get-Process -Name $commandName -ErrorAction SilentlyContinue)
        if ($processes.Count -gt 0) {
            $running += $commandName
        }
    }
    if ($running.Count -gt 0) {
        throw "Claudey is still running ($($running -join ', ')). Stop those processes, then rerun uninstall."
    }
}

function Initialize-UvContext {
    Add-KnownUvPaths

    if ($DryRun) {
        Write-Host "+ uv tool dir --bin"
        return
    }

    $uvCommand = Get-ApplicationCommand "uv"
    if (-not $uvCommand) {
        throw "uv is required to remove the Claudey tool. Install uv, then rerun this uninstaller; ~/.fcc was not deleted."
    }
    $script:UvPath = $uvCommand.Source

    $commandText = Format-Command -FilePath $script:UvPath -Arguments @("tool", "dir", "--bin")
    Write-Host "+ $commandText"
    $result = Invoke-NativeResult -FilePath $script:UvPath -Arguments @("tool", "dir", "--bin")
    if ($result.ExitCode -ne 0) {
        if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
            [Console]::Error.WriteLine($result.Output)
        }
        throw "Could not determine the uv tool bin directory (exit code $($result.ExitCode)); ~/.fcc was not deleted."
    }
    $script:UvToolBin = $result.Output.Trim()
    if ([string]::IsNullOrWhiteSpace($script:UvToolBin)) {
        throw "uv returned an empty tool bin directory; ~/.fcc was not deleted."
    }
}

function Uninstall-FreeClaudeCode {
    Write-Host "+ uv tool uninstall $PackageName"
    if ($DryRun) {
        return
    }

    $result = Invoke-NativeResult -FilePath $script:UvPath -Arguments @(
        "tool",
        "uninstall",
        $PackageName
    )
    if ($result.ExitCode -eq 0) {
        if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
            Write-Host $result.Output
        }
        return
    }
    if (Test-MissingUvToolError -Output $result.Output) {
        Write-Host "Claudey uv tool is already absent; verifying its entry points."
        return
    }
    if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
        [Console]::Error.WriteLine($result.Output)
    }
    throw "uv tool uninstall $PackageName failed with exit code $($result.ExitCode); ~/.fcc was not deleted."
}

function Confirm-HansCommandsRemoved {
    if ($DryRun) {
        Write-Host "+ verify all Claudey entry points are absent from the uv tool bin directory"
        return
    }

    $remaining = @()
    $extensions = @("", ".exe", ".cmd", ".bat", ".ps1")
    foreach ($commandName in $HansCommands) {
        foreach ($extension in $extensions) {
            $commandPath = Join-Path $script:UvToolBin "$commandName$extension"
            if (Test-Path -LiteralPath $commandPath) {
                $remaining += $commandPath
            }
        }
    }
    if ($remaining.Count -gt 0) {
        throw "Claudey entry points remain after uv uninstall: $($remaining -join ', '); ~/.fcc was not deleted."
    }
}

function Remove-LegacyFccShims {
    if ($DryRun) {
        Write-Host "+ remove legacy fcc-* deprecation shims from the uv tool bin directory"
        return
    }
    if ([string]::IsNullOrWhiteSpace($script:UvToolBin)) {
        return
    }

    foreach ($name in $LegacyFccCommands) {
        $shimPath = Join-Path $script:UvToolBin "$name.cmd"
        if (-not (Test-Path -LiteralPath $shimPath -PathType Leaf)) {
            continue
        }
        $content = Get-Content -LiteralPath $shimPath -Raw -ErrorAction SilentlyContinue
        if ($null -ne $content -and $content.Contains("is deprecated: use hans-")) {
            Write-Host "+ Remove-Item -LiteralPath $(Format-Argument $shimPath) -Force"
            Remove-Item -LiteralPath $shimPath -Force
        }
        else {
            Write-Host "A file not managed by Claudey exists at $shimPath; leaving it unchanged."
        }
    }
}

function Test-EquivalentPath {
    param(
        [string] $Left,
        [string] $Right
    )

    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
        return $false
    }
    try {
        return [string]::Equals(
            [IO.Path]::GetFullPath($Left),
            [IO.Path]::GetFullPath($Right),
            [StringComparison]::OrdinalIgnoreCase
        )
    }
    catch {
        return $false
    }
}

function Test-HansDesktopShortcutTarget {
    param([string] $TargetPath)

    foreach ($extension in @("", ".exe", ".cmd", ".bat", ".ps1")) {
        $expectedTarget = Join-Path $script:UvToolBin "hans-desktop$extension"
        if (Test-EquivalentPath -Left $TargetPath -Right $expectedTarget) {
            return $true
        }
    }
    return $false
}

function Remove-HansDesktopShortcuts {
    $shortcutPaths = @(
        (Join-Path $env:USERPROFILE "Desktop\Claudey.lnk"),
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Claudey.lnk")
    )
    $shell = New-Object -ComObject WScript.Shell
    foreach ($shortcutPath in $shortcutPaths) {
        if (-not (Test-Path -LiteralPath $shortcutPath)) {
            continue
        }
        try {
            $shortcut = $shell.CreateShortcut($shortcutPath)
            $isHansShortcut = Test-HansDesktopShortcutTarget -TargetPath $shortcut.TargetPath
        }
        catch {
            $isHansShortcut = $false
        }
        if (-not $isHansShortcut) {
            Write-Host "A shortcut not managed by Claudey exists at $shortcutPath; leaving it unchanged."
            continue
        }
        Write-Host "+ Remove-Item -LiteralPath $(Format-Argument $shortcutPath) -Force"
        if (-not $DryRun) {
            Remove-Item -LiteralPath $shortcutPath -Force
        }
    }
}

function Purge-HansHome {
    $hansHome = Join-Path $env:USERPROFILE $HansHomeDirname
    if (-not (Test-Path -LiteralPath $hansHome)) {
        Write-Host "No Claudey config directory at $hansHome; skipping purge."
        return
    }

    $commandText = @(
        "Remove-Item",
        "-LiteralPath",
        (Format-Argument $hansHome),
        "-Recurse",
        "-Force"
    ) -join " "
    Write-Host "+ $commandText"
    if ($DryRun) {
        return
    }

    Remove-Item -LiteralPath $hansHome -Recurse -Force
    if (Test-Path -LiteralPath $hansHome) {
        throw "Claudey config directory still exists after deletion: $hansHome"
    }
}

if ($Help) {
    Show-Usage
    return
}
if ($RemainingArgs.Count -gt 0) {
    Show-Usage
    throw "Unknown option: $($RemainingArgs -join ' ')"
}
if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    throw "USERPROFILE is not set; cannot locate Claudey data."
}

Write-Step "Checking for running Claudey processes"
Assert-NoHansProcessesRunning

Write-Step "Locating the uv-managed Claudey installation"
Initialize-UvContext

Write-Step "Removing the Claudey uv tool"
Uninstall-FreeClaudeCode

Write-Step "Verifying Claudey entry points were removed"
Confirm-HansCommandsRemoved

Write-Step "Removing legacy fcc-* deprecation shims"
Remove-LegacyFccShims

Write-Step "Removing Claudey desktop shortcuts"
Remove-HansDesktopShortcuts

Write-Step "Purging Claudey config and data from ~/.fcc"
Purge-HansHome

Write-Host ""
if ($DryRun) {
    Write-Host "Dry run complete. No changes were made."
}
else {
    Write-Host "Claudey has been removed and verified."
    Write-Host "uv, Claude Code, Codex, Pi, the uv-managed Python runtime, and shared PATH entries were left installed."
}
