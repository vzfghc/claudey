# Sprint Report — Sprint 1, Iteration 001

Sprint: Kill providers→application (H1, L3) · Branch: `feat/phase-a-free-providers` · 2026-08-13

## What Was Done

**H1 — `ProviderModelInfo` → `core/model_metadata.py`.** Both `ProviderModelInfo` and
`ProviderModelRefreshResult` moved (the plan's grep rule applied: `providers/runtime/discovery.py:12`
imports `ProviderModelRefreshResult`, so it moved too). `application/model_metadata.py` became empty
and was **deleted** — complete migration, no shims, no re-exports.

**L3 — errors → `core/errors.py`.** Grep decided four classes move, not one:
`ApplicationUnavailableError` (plan-mandated), `ApplicationError` (its base — core cannot import
application), and `InvalidRequestError` + `UnknownProviderError` (provider-imported per grep:
`openai_codex/provider.py:12`, `deepseek/compat.py:8`, `openai_chat/request_policy.py:10`,
`openai_chat/profiles.py:8`, `google_openai/reasoning.py:6`, `providers/runtime/factory.py:5-7`).
`application/errors.py` became empty and was **deleted**.

**Docs.** `ARCHITECTURE.md` updated in the same change: the model-metadata owner paragraph
(`:623-626` → `core/model_metadata.py`, now naming both values), the application package description
(`:48-52`, dropped "deterministic request/readiness errors" from application's ownership), and the
core package description (`:61-65`, now lists model metadata + readiness errors). Link-validity
contract test green.

## Files Changed

- **Created** (2): `src/claudey/core/model_metadata.py` (classes verbatim, frozen/slots intact);
  `src/claudey/core/errors.py` (classes verbatim; imports `Iterable` + `core.failures.FailureKind` only).
- **Deleted** (2): `src/claudey/application/model_metadata.py`, `src/claudey/application/errors.py`.
- **Import rewrites** (71): 32 in `src/claudey/` (providers/base, kilo/client, kilo/models,
  model_listing, open_router, openai_codex/provider, cloudflare/client, runtime/discovery,
  runtime/config, runtime/model_cache, runtime/factory, github_models/client, deepseek/compat,
  anthropic/messages, vertex/endpoint, vertex/client, openai_chat/request_policy, openai_chat/profiles,
  google_openai/reasoning, openai_chat/provider, runtime/provider_manager, runtime/application,
  api/ports, api/routes, api/request_errors, api/dependencies, api/admin_routes, api/app,
  api/handlers/{messages,token_count,responses}, application/routing); 38 in `tests/`; 1 in
  `scripts/hans_schemathesis_app.py` (live consumer found outside the plan's src/tests/smoke grep
  scope — updated because the module was deleted).
- **Relative-import fix** (1): `src/claudey/application/ports.py:11` `from .model_metadata` →
  `from claudey.core.model_metadata`.
- **Docs** (1): `ARCHITECTURE.md:48-52, 61-65, 623-626`.

## Verification Outputs (contract order)

| Step | Command | Outcome |
|---|---|---|
| Format | `uv run ruff format` | 501 files left unchanged |
| Lint | `uv run ruff check --fix` | 66 errors fixed (import-sorting after rewrites), 0 remaining |
| Types | `uv run ty check` | All checks passed |
| Targeted | `uv run pytest <39 affected files> -n0 -q` | **805 passed** |
| Boundary | `tests/contracts/test_import_boundaries.py -n0` (in the batch) | green |
| Full suite | `uv run pytest -q` | **3100 passed, 73 skipped** (matches orchestrator baseline) |
| Coverage | `uv run pytest --cov=claudey --cov-report=term-missing -q` | TOTAL 19678 stmts / 1874 miss / **90%** |

Grep gates:
- `grep -rn "from claudey.application" src/claudey/providers/` → **2 hits, both out of scope**
  (see Residual Risks).
- `grep -rn "claudey.application.model_metadata|claudey.application.errors|from .model_metadata"`
  across src/tests/scripts/smoke → **0 hits**.
- `grep -rl "from claudey.core.model_metadata|from claudey.core.errors"` → 70 importer files.

## Coverage Delta

Baseline (Sprint 0): 90%. Now: 90%. **Delta 0** — pure relocation; the moved modules are exercised
by the same tests from the new owner.

## Rebuttals

None — every plan action executed; no plan deviation required.

## Residual Risks

1. **`providers→application.connected_accounts` edge remains** (2 sites:
   `providers/openai_codex/auth.py:18`, `providers/anthropic/auth.py:5`, importing
   `ConnectedAccountLoginMode/State/Status`). This module has **no assessment ID** and **no sprint in
   plan §7**; Sprint 1's actions are H1 + L3 only, and the edge is contract-sanctioned
   (`providers: {application, config, core}`). Not moved to avoid scope expansion and behavior risk in
   auth-state code. Recorded with grep evidence as required; suggest a future sprint item.
2. `scripts/hans_schemathesis_app.py` was not in the plan's grep scope but was a live importer;
   updated mechanically (same import shape). Not executed by pytest — smoke script, low risk.
3. Zero behavior change: class bodies, docstrings, frozen/slots dataclass semantics, and
   `UnknownProviderError.for_provider` wording all verbatim; the full suite pins the moved symbols'
   behavior via the same tests.
