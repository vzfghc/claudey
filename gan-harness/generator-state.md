# Generator State — Iteration 004

## What Was Built

Sprint 4 (Polish & Legacy) of the Claudey rebrand, per `gan-harness/spec.md` — features #14–#17, plus the three Major issues from feedback-002:

- **#14 Legacy `fcc-*` shims** — `install.sh`/`install.ps1` gained a `--legacy-fcc` (`-LegacyFcc`) flag that writes deprecation shims for `fcc-server`, `fcc-claude`, `fcc-codex`, `fcc-pi`, `fcc-desktop` into the uv tool bin dir (shell scripts on POSIX, `.cmd` batches on Windows). Each prints `<name> is deprecated: use <hans-name>` to stderr and exits 2. `uninstall.sh`/`uninstall.ps1` remove them, but only when the file content contains the "is deprecated: use hans-" marker (foreign files are left untouched). Dry-run modes print the write/remove commands without mutating.
- **#15 Dark theme** — `@media (prefers-color-scheme: dark)` block appended to `admin.css` that re-tokens the chrome with the original pre-Sprint-2 dark palette (`--bg #090a0f`, `--panel #11131c`, `--card #151822`, `--text #f3f4f6`, dark shadows, dark chevron, scrollbar overrides). No structural changes; the coral accent and status colors stay. Verified served live at `/admin/assets/admin.css`.
- **#16 `claudey doctor`** — new subcommand in `dispatcher.py`: prints `Claudey v<version>`, module path (from `__file__`, no package-facade import), `~/.fcc` config/env paths, admin URL (via `server_urls.local_admin_url`), server port, providers with keys (per `PROVIDER_CATALOG` `configuration_attrs()` non-empty, `openai` = auth file exists, local providers skipped), provider total, and CI-check statuses (ruff format/check, ty, pytest run concurrently from the repo root when found; "not checked" when unavailable/timeout). Registered in the usage tree; bare `claudey` now exits 2 with usage on stderr (feedback-002 minor).
- **#17 App icon assets** — `assets/claudey-icon.svg` (Anthropic starburst, coral `#D97757`, white rounded square with hairline border) and `scripts/generate_icons.py` (Pillow, 4x supersampled, LANCZOS) emitting `assets/claudey-icon.png` (512 master) + `assets/icons/claudey-icon-{512,256,128,64,32,16}.png`. The center triangle of the logo path is punched out as a hole (opposite winding). `ci.sh` gained an `icons` check (runs `generate_icons.py --check`; no Pillow needed to verify).
- **feedback-002 Major fixes** — `beforeunload` dirty guard in `admin.js` (suppressed during apply-triggered restart navigation via `suppressBeforeUnload`); all primary/secondary/ghost/test buttons bumped `min-height` 36px → 40px; sidebar nav now renders inline SVG icons per view and collapses to a centered icon rail with labels hidden below 900px (44px targets; 600px keeps a centered 44px icon row).
- **Version**: `5.2.0 → 5.3.0` (MINOR — doctor, icons, legacy shims, dark theme) with `uv lock` in the same change.

## What Changed This Iteration

- `scripts/install.sh|ps1`, `scripts/uninstall.sh|ps1`: `--legacy-fcc` flag, shim install/removal functions, usage text, dry-run support.
- `src/claudey/api/admin_static/admin.css`: dark `prefers-color-scheme` block; `nav-icon`/`nav-label` styles; icon-rail rules at ≤900px/≤600px; button touch targets 40px.
- `src/claudey/api/admin_static/admin.js`: `beforeunload` guard + suppress flag; per-view inline SVG nav icons; `renderNav` builds icon+label spans.
- `src/claudey/cli/dispatcher.py`: `doctor()`, `_providers_with_keys`, `_project_root`, `_check_status`, `_ci_checks`; bare-`claudey` exits 2.
- `scripts/generate_icons.py` (new), `assets/claudey-icon.svg` (new), `assets/claudey-icon.png` + `assets/icons/*` (new).
- `scripts/ci.sh`: `icons` check added to order/usage/validation/dispatch.
- Tests: doctor report + main routing (`tests/cli/test_dispatcher.py`), `--legacy-fcc` POSIX + PowerShell install/uninstall tests, uninstaller shim removal + foreign-file preservation, ci.sh icons dry-run, `beforeunload`/icon-rail/40px static assertions in `tests/api/test_admin.py`.

## Known Issues

- `claudey doctor` CI checks show "not checked" when run outside a checkout or when the tool isn't on PATH (documented behavior per spec).
- Dark theme is token-only: the action-bar shadow stays `rgba(28,25,23,…)` (a dark-on-dark shadow is invisible, no breakage) and the sidebar wash uses `var(--bg)` so it follows the theme.
- PowerShell installer/uninstaller changes are covered by tests that run only on Windows hosts (skipped on macOS, as before).

## Dev Server

- URL: http://127.0.0.1:8082/admin
- Status: running (serves updated admin.css/admin.js from disk; no restart needed for static assets)
- Command: `uv run hans-server` (background)
