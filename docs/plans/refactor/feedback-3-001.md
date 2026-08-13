# Evaluation — Sprint 3, Iteration 001 (Failure classification DRY, H4)

Branch: `feat/phase-a-free-providers` · Commit: `521cea64` · 2026-08-13 · Evaluator-verified, generator report NOT trusted.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 — CI gate green | 10/10 | 0.30 | 3.00 |
| C2 — Behavior preservation | 10/10 | 0.25 | 2.50 |
| C3 — Principle adherence | 9/10 | 0.20 | 1.80 |
| C4 — Dead-code & hygiene | 7/10 | 0.10 | 0.70 |
| C5 — Code health | 9/10 | 0.15 | 1.35 |
| **TOTAL** | | | **9.35/10** |

## Verdict: PASS (threshold 7.0)

## Verification Commands Run (all by the evaluator, none trusted from the report)

| Command | Outcome |
|---|---|
| `uv run pytest tests/contracts/test_import_boundaries.py -n0` | **21 passed** |
| `./scripts/ci.sh` (full) | **All 7 checks passed, exit 0; 3142 passed, 73 skipped** (3111 baseline + 31 matrix rows — matches report exactly) |
| `git status --porcelain` after ci.sh | **Zero tracked dirt** — ci.sh repaired nothing post-commit; only pre-existing untracked baseline junk (root screenshots, `.playwright-mcp/`, `model-config-skeleton.yml` — Sprint 8 scope, not introduced here) |
| `uv run ruff format --check` + `uv run ruff check` | 504 files already formatted; all checks passed (check-only clean = GitHub CI state) |
| `uv run pytest --cov=claudey --cov-report=term-missing -q` | **TOTAL 19707 stmts / 1868 miss / 91%** — ≥80% and ≥90% baseline; matches report exactly |
| `git show 521cea64 -- tests/providers/test_stream_recovery.py` | Every change is a mechanical call-site rename; assertion logic identical (see C2 below) |
| `git show 521cea64^:src/claudey/providers/{stream_recovery,failure_policy}.py` + post-merge reads | Pre-merge tables recovered; merged classifier diffed set-by-set and order-sensitively |
| Frozen-surface greps: `admission.py` budgets, auth-latch, holdback, wording constants, `is_retryable_provider_error` call sites | All unchanged/working (see C2 below) |
| `grep -rn is_retryable_stream_error src/ tests/ smoke/` | **1 hit, docstring only** (`tests/providers/test_retryability_matrix.py:4`) — the "0 hits repo-wide" gate is technically at 1 |
| Adversarial probes: `HANS_CONFIG_DIRNAME|HANS_ENV_FILENAME|HANS_LOGS_DIRNAME`, `google_openai`, `from claudey.application` in `providers/`, `from claudey.providers` in `config/`+`application/`, `"nvidia_nim"` literals | All hits are pre-existing items owned by Sprints 7/4/1 — **none introduced by the sprint-3 diff** (verified via `git show 521cea64 --stat`: only 6 files, all sprint-scope) |
| C5 checks: `wc -l` all 5 touched files; function spans; suppression grep; `+=` loop grep | All pass (see C5 below) |

## Criterion Justifications (score bands cited)

### C1 = 10 (band: "All 7 checks pass on the evaluator's first run; git status clean of stray artifacts")
First-run green on all 7 checks; committed state check-only clean (`ruff format --check` / `ruff check` pass with zero repair); boundary contract 21/21. Untracked root junk is the pre-recorded Sprint-8 baseline (plan §2 step 3), not sprint-3 dirt — the sprint commit itself adds zero junk.

### C2 = 10 (band: "Full suite green; coverage ≥80% and ≥baseline; protocol/env/payload/CLI/retry/wording diff audit clean; no user-visible string changed")
- Full suite 3142 passed; coverage 91% ≥ 90% baseline.
- **C2 critical axis (the 12 renamed assertions in `test_stream_recovery.py`):** `git show 521cea64` shows every `is_retryable_stream_error(X)` → `is_retryable_error(X, recovery=True)` change is a pure mechanical rename; all 12 assert statements keep identical argument structure and truthiness (4+4+1+1+1+1 across the 6 tests; the timeout test was reformatted single-line→multi-line with zero semantic change). No assertion weakened, removed, or relaxed. (Note: the report says "8 assertions"; the actual count is 12 — cosmetic reporting undercount, see C5 nit.)
- **Pin-vs-reality (both corrected expectations verified against pre-merge code):** (a) `httpx.WriteError` is a `httpx.NetworkError` subclass and `httpx.NetworkError` is in the pre-merge stream tuple (`stream_recovery.py@521cea64^:193`), so WriteError was retryable in the stream context pre-merge — the pin's `httpx_write_error` → True/True row matches old code, not a changed decision. (b) `openai.APIError.__init__` in the installed SDK (openai **2.46.0**, verified via `inspect`) takes `(message, request, *, body)` with **no `response` param** — the matrix constructs it with `request=` + explicit `body=`; the statusless-APIError rows (`body={"error":{"message":"internal failure","code":500}}` → True/True; `body=None` → False/False) match my independent derivation from the pre-merge classifier (transient body-status inference → 500, bare → not in tuple). No silent decision change.
- **Merged classifier reproduces both pre-merge tables exactly.** `failure_policy.py:170-186` `_RETRYABLE_TRANSPORT_ERRORS` tuples match the pre-merge final tuples as sets (provider ctx: TimeoutError/TimeoutException/ConnectError/ReadError/WriteError/RemoteProtocolError/NetworkError/APITimeoutError/APIConnectionError/RetryableProviderProtocolError; stream ctx: TimeoutError/ReadTimeout only/ReadError/RemoteProtocolError/ConnectError/NetworkError/APITimeoutError/APIConnectionError). Order-sensitive guards preserved: leading protocol-membership check only in recovery ctx (`failure_policy.py:199-201`), `ProviderRecoveryExhausted` only in provider ctx (`:202`), permission short-circuit only in provider ctx (`:208-209`) — so `permission_denied_with_retryable_body` (False/True) and `httpx_timeout_exception` (True/False) behave per old code. I independently re-derived all 31 matrix rows from the pre-merge sources: **31/31 pins match old behavior** (incl. the 2 adversarial ordering rows, ProviderRecoveryExhausted→False in stream ctx via transient-None + no tuple member, and HTTPStatusError 400/500/429 rows).
- Diff audit: `admission.py` diff = 0 lines; retry budgets intact (`admission.py:27-31` 5/2.0/60.0/1.0, `AUTH_LATCH_TTL_SECONDS = 5.0`); holdback intact (`stream_recovery.py:13-14` 0.75 / 65_536); wording constants intact (`failure_policy.py:33-40` `_AUTHENTICATION_MESSAGE` etc. — the diff touches only the classifier region); no user-visible string changed.

### C3 = 9 (band: "All resolved; one minor new smell…")
The DRY goal is fully met: one classifier `is_retryable_error` (`failure_policy.py:192-215`, 24 lines); `stream_recovery.py`'s local copy **deleted, no shim** (grep of the old function body → gone); `is_retryable_provider_error` retained as a one-line documented delegate (`failure_policy.py:217-219`) with a sound justification (public entry point called by `admission.py:21,154` and `failure_policy.py:338,373`; frozen-surface rule). Pre-merge TDD guard exists and is committed in the same commit as the merge. **One nit:** `is_retryable_stream_error` still appears at `tests/providers/test_retryability_matrix.py:4` (docstring). The orchestrator's gate is "0 hits repo-wide"; a docstring reference to the historical name is not code and is disclosed in the report, but the gate is technically at 1. Fix is a one-word reword (see LOW-1). No new cross-layer edges, no shims, no `TYPE_CHECKING`/local imports anywhere in the diff.

### C4 = 7 (neutral sprint — no dead-code work in scope; no junk added)
Sprint 3 adds no new junk; the untracked baseline junk is Sprint 8 scope. Neutral score per rubric.

### C5 = 9 (band: "All checks pass with one minor nit")
New code is exemplary: `is_retryable_error` 24 lines (incl. docstring); `_RETRYABLE_TRANSPORT_ERRORS` is a named module constant (no magic types); matrix test 293 lines, frozen slots dataclass, parameterized, 5-line test function; `advance_failure` 45 lines; all 5 touched files <800 lines (477/173/1059→2 call lines/293/278); zero suppressions; zero `+=` string loops. **Nits:** (1) the sprint touches two pre-existing >50-line functions in `openai_chat/provider.py` — `_collect_recovery_output` (`:789-885`, ~97 L) and `_recovery_events` (`:886-982`, ~97 L); both are pre-existing (only one call line each changed) and are the explicit target of Sprint 7 M5, so no deduction beyond the nit band — the Sprint-7 split must bring them under 50. (2) Report says "8 assertions switched" — actual count is 12 call sites in `test_stream_recovery.py` (report accuracy nit, no code impact).

## Issues

### CRITICAL
None.

### HIGH
None.

### MEDIUM
None.

### LOW
1. **`tests/providers/test_retryability_matrix.py:4`** — C3. The string `is_retryable_stream_error` survives in the docstring, so `grep -rn is_retryable_stream_error src/ tests/ smoke/` returns 1 hit instead of 0. Fix: reword the header docstring to avoid the identifier literal, e.g. "the pre-merge stream-recovery classifier" — the pinned behavior documentation stays, the grep gate returns to 0.
2. **`src/claudey/providers/openai_chat/provider.py:789-885, 886-982`** — C5 (note, deferred). `_collect_recovery_output` and `_recovery_events` are ~97 lines each. Pre-existing; the sprint touched only one line of each. The Sprint 7 M5 split (`streaming.py` extraction) must reduce both below 50 lines — record them as explicit M5 targets in that sprint's report.
3. **`docs/plans/refactor/sprint-report-3-001.md` line 79** — report accuracy. "8 assertions switched" — the diff actually switches 12 call sites in `test_stream_recovery.py`. Cosmetic, but the report should match the diff count so the orchestrator's cross-checks line up.

## Positive Findings (do not churn these)

- The TDD-guard-first discipline is real: the matrix test is committed in the same commit as the merge, and every one of its 31 pins matches the pre-merge decision tables as I independently derived them from `521cea64^` sources — including the two order-sensitive adversarial rows and the two "corrected" expectations (WriteError-via-NetworkError, statusless APIError construction under openai 2.46.0).
- `_RETRYABLE_TRANSPORT_ERRORS` context-keyed table with the explanatory comment (`failure_policy.py:160-169`) is exactly the right shape for this merge — one table, per-context membership, no duplicated guard chains.
- The delegate decision (`is_retryable_provider_error` kept as one-line wrapper) is the correct reading of the frozen-surface rule; deleting it would have broken `admission.py:21,154`.
- Dead import cleanup in `stream_recovery.py` (httpx, openai, ExecutionFailure, retryable_transient_status removed with the deleted function) — no stragglers.
- The two matrix rows that differ across contexts (`openai_permission_denied_with_retryable_body`, `httpx_timeout_exception`) are exactly the rows that lock the ordering divergences — a future reorder fails loudly.

## What Improved Since Last Iteration

N/A — first iteration of Sprint 3.

## Specific Suggestions for Next Iteration

1. Fix LOW-1 (reword `test_retryability_matrix.py:4` docstring) and re-run the grep gate to 0 hits.
2. Do not touch the classifier logic otherwise — the matrix plus the two adversarial rows are the behavioral guard.
3. Pre-stage the Sprint 7 M5 note: ensure the provider split targets `_collect_recovery_output` and `_recovery_events` specifically (both ~97 L today).
