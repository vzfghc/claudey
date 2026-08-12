# Sprint Report 0-001 — Foundation: import-boundary contract green (C1, C2, C3)

Branch: `feat/phase-a-free-providers` · Date: 2026-08-13 · Iteration 1 of Sprint 0

## Outcome

`uv run pytest tests/contracts/test_import_boundaries.py -n0` → **21 passed** (was 2 failed, 19 passed). Both previously failing tests (`test_package_dependencies_follow_declarative_policy`, `test_external_consumers_use_owned_package_facades`) are green via the three sanctioned actions below.

## Files Changed

### C1 — wire URL constants promoted to `core/anthropic/`
- `src/claudey/core/anthropic/urls.py` (new): `ANTHROPIC_VERSION_HEADER`, `anthropic_messages_url`, `openai_v1_base_url` with docstrings (module + per-name). Zero imports (true leaf).
- `src/claudey/config/custom_provider_check.py:16-20`: imports repointed from `providers.anthropic.messages` + `providers.openai_chat.base_url` to `claudey.core.anthropic.urls` (this also removes the facade-breach edge the second failing test flagged).
- `src/claudey/providers/anthropic/messages.py:20` (import added), `:31-43` (local defs deleted; `ANTHROPIC_COMPATIBLE_TAG` stays). Uses at `:45,:48` now resolve via the core import.
- `src/claudey/providers/openai_chat/profiles.py:12`: `openai_v1_base_url` now imported from `claudey.core.anthropic.urls` (was `.base_url` at :14).
- `src/claudey/providers/openai_chat/__init__.py:3`: facade re-export `openai_v1_base_url` now sourced from `claudey.core.anthropic.urls`; `__all__` unchanged (`:61`). This keeps the public facade symbol so `smoke/lib/local_providers.py:8` (imports the facade) needs no change.
- `src/claudey/providers/openai_chat/base_url.py`: **deleted** (`git rm`) after grep confirmed zero importers remain (see Verification).

### C2 — `providers/health.py` → `application/health.py`
- `git mv src/claudey/providers/health.py src/claudey/application/health.py` (pure relocation; only claudey import is `core.failures.FailureKind`).
- `git mv tests/providers/test_health.py tests/application/test_health.py`.
- `src/claudey/application/failover.py:29` (`from .health import HealthRegistry, health_registry` — intra-application; was `providers.health` at :27).
- `tests/conftest.py:35`, `tests/api/test_failover_executor.py:14`, `tests/application/test_health.py:5-9`: imports updated to `claudey.application.health`.

### C3 — sanctioned contract amendment
- `tests/contracts/test_import_boundaries.py:14`: `"config": set()` → `"config": {"core"}` with a comment documenting config→core as a legitimate downward edge to a true leaf (`core.anthropic.urls` + `core.secret_crypto`). No other assertion touched.
- `ARCHITECTURE.md:86`: dependency table cell `| config | none |` → `| config | core |`, plus a note paragraph after the table (same rationale as the test comment).

## Verification (exact outputs)

| Step | Command | Result |
|---|---|---|
| Format/lint | `uv run ruff format && uv run ruff check --fix && uv run ruff check` | All checks passed; 503 files left unchanged (ruff auto-sorted one import block in `tests/api/test_failover_executor.py`) |
| Type check | `uv run ty check` | All checks passed |
| Boundary contract | `uv run pytest tests/contracts/test_import_boundaries.py -n0` | **21 passed** in 4.22s |
| Targeted tests | `uv run pytest tests/application/test_health.py tests/api/test_failover_executor.py tests/contracts/test_architecture_contracts.py tests/config/test_custom_providers.py tests/api/test_admin.py -n auto -q` | 192 passed |
| Provider suite | `uv run pytest tests/providers/ -n auto -q` | 937 passed |
| Full gate | `./scripts/ci.sh` | ruff/ty/pytest: 1 failed, 3111 passed (see Residual Risks) |

## Coverage

- Baseline (recorded before any change, this branch): `TOTAL 19681 1872 90%`
- After Sprint 0: `TOTAL 19682 1874 90%`
- Delta: +1 statement / +2 missed lines (the new `urls.py` module docstring block and one relocated def), **90% ≥ 80% and not below baseline** → coverage gate passes.

## Acceptance Greps (plan §7)

- `grep -rn "from claudey\.providers\|import claudey\.providers" src/claudey/config/ src/claudey/application/` → **0 hits**.
- `grep "providers.health" src/ tests/ smoke/` → **0 hits** (remaining hits are only in the dated plan/assessment snapshot docs, which the plan forbids editing).
- `grep "openai_chat\.base_url" src/ tests/ smoke/` → **0 hits**; deleted module has zero importers (only snapshot-doc references remain).
- `git status --porcelain`: only this sprint's changes + the pre-existing untracked junk (root screenshots, `.playwright-mcp/`, `model-config-skeleton.yml`) — junk untouched per orchestrator instruction (Sprint 8 scope).

## Rebuttals

1. **Plan's C1 importer list was incomplete.** The plan states the only src importers of the three names are `config/custom_provider_check.py:16-20` and the two owner modules. Grep on the current tree found two additional src importers: `providers/openai_chat/profiles.py:14` and `providers/openai_chat/__init__.py:6` (facade re-export, `__all__:61`); `smoke/lib/local_providers.py:8` imports the name from the facade. Resolved: both src sites repointed to `core.anthropic.urls`; the facade keeps re-exporting the symbol (sanctioned by ARCHITECTURE.md "package initializers may import dependency leaves to publish supported exports"), so smoke is untouched. `base_url.py` was deleted because zero module importers remained — this is a complete migration, no shim.
2. **Pre-existing suite failure, out of scope.** `tests/runtime/test_provider_manager.py::test_catalog_publication_tracks_warm_refresh_and_direct_cache` fails in the full suite. Evidence it is not caused by this sprint: it failed identically in the pre-change baseline coverage run, and re-running it on the stashed (pre-change) tree still fails (`git stash` + isolated run → 1 failed in 0.18s, restored after). Sprint 0 scope is C1/C2/C3; this test belongs to provider runtime and is not on the sprint's affected list. Deferred.

## Residual Risks

- The `config: {"core"}` amendment is a deliberate contract change; it is documented in both the test comment and ARCHITECTURE.md. Any future config→providers or config→application import fails the boundary test.
- `test_catalog_publication_tracks_warm_refresh_and_direct_cache` (pre-existing, unrelated) keeps `./scripts/ci.sh` pytest from full green; unchanged from baseline.
- The facade re-export of `openai_v1_base_url` on `claudey.providers.openai_chat` remains a public symbol (used by smoke); if Sprint 8 later removes it, `smoke/lib/local_providers.py:8` must be updated in the same change.
