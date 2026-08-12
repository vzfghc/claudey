# Sprint Report — Sprint 3, Iteration 001

Sprint: Failure classification DRY (H4) · Branch: `feat/phase-a-free-providers` · 2026-08-13

## What Was Done

**H4 — one retryability classifier; zero duplicated decision tables.**

The two pre-merge decision tables were read and diffed first:

- `providers/failure_policy.py` `is_retryable_provider_error` — guard order:
  `ProviderRecoveryExhausted` → False, `ExecutionFailure` → `.retryable`,
  `openai.AuthenticationError | PermissionDeniedError | BadRequestError` → False,
  transient-status inference → True, final transport-family tuple (incl.
  `httpx.TimeoutException`, `httpx.WriteError`, `RetryableProviderProtocolError`).
- `providers/stream_recovery.py` `is_retryable_stream_error` — guard order:
  `RetryableProviderProtocolError` → True, `ExecutionFailure` → `.retryable`,
  `openai.AuthenticationError | BadRequestError` → False (no `PermissionDeniedError`),
  transient-status inference → True, final tuple narrowed to `httpx.ReadTimeout`
  (not `httpx.TimeoutException`) with no `httpx.WriteError` / no protocol-error member.

Effective decision differences (verified empirically while writing the pin test):
the stream context rejects `ConnectTimeout` / `WriteTimeout` / `PoolTimeout` /
bare `httpx.TimeoutException` (provider retries them) and keeps a permission error
with a retryable body retryable (the provider context short-circuits permission
errors before body inspection). `httpx.WriteError` is *not* a behavioral
divergence — it is a `httpx.NetworkError` subclass and stays retryable in both
contexts through the shared `NetworkError` member; the plan's "omits WriteError"
refers to the explicit tuple listing only.

**TDD guard first (mandatory, pre-merge).** `tests/providers/test_retryability_matrix.py`
was written and run against the pre-merge code BEFORE any merge: a 31-row
table-driven matrix covering every exception family appearing in either function
(all `httpx.*` + `openai.*` + `RetryableProviderProtocolError` / `RetryableToolProtocolError` /
`TruncatedProviderStreamError` / `ProviderRecoveryExhausted` / `ExecutionFailure` /
builtin `TimeoutError` / control `RuntimeError`), each row asserting the decision in
BOTH contexts (provider-retry and stream-recovery). Pre-merge run: **31 passed**
(pinned today's behavior; two of my hand-derived expectations were corrected by the
pin — `httpx.WriteError` retryable in the stream context via `NetworkError`
inheritance, and openai 2.46 `APIError` requires `body=None` — the pin did its job).
The same table, with the stream-context assertion switched to the merged entry
point, passed 31/31 post-merge. The test is committed in the same commit as the
merge (cardinal-sin guard).

**Merge.** Single classifier in `providers/failure_policy.py`:

- `is_retryable_error(exc, *, recovery: bool = False)` — one exception-family
  table (`_RETRYABLE_TRANSPORT_ERRORS: dict[bool, tuple[type[BaseException], ...]]`)
  keyed by context, plus the per-context guard differences (leading
  protocol-membership check and permission-error short-circuit only in their
  original contexts). Reproduces both decision tables exactly, including the
  stream-context inlined openai bad-request branch and the narrowed timeout family.
- `is_retryable_provider_error(exc)` — kept as a one-line delegate
  (`return is_retryable_error(exc)`); it is the public entry point `admission.py:21,154`
  and `test_failure_policy.py:343,456` call, signature unchanged.
- `stream_recovery.py` — imports `is_retryable_error`, its `advance_failure` calls
  `is_retryable_error(error, recovery=True)`; the local `is_retryable_stream_error`
  is DELETED (no shim). `openai_chat/provider.py` (two call sites: `_collect_recovery_output`
  retry gate and `_recovery_events` entry) switched to
  `is_retryable_error(error, recovery=True)`. `tests/providers/test_stream_recovery.py`
  updated to the same call. Grep `is_retryable_stream_error` in `src/`, `tests/`,
  `smoke/` → 0 code hits (one historical docstring mention in the matrix test).

## Files Changed

- **Created** (1): `tests/providers/test_retryability_matrix.py` — 31-row pinned
  matrix, both contexts, parameterized (GREEN pre-merge and post-merge).
- **Modified** (4):
  - `src/claudey/providers/failure_policy.py:160-215` — `_RETRYABLE_TRANSPORT_ERRORS`
    context table + `is_retryable_error(exc, *, recovery)`; `is_retryable_provider_error`
    now a one-line delegate.
  - `src/claudey/providers/stream_recovery.py:8-11,129-131` — imports
    `is_retryable_error`; `advance_failure` calls it with `recovery=True`;
    `is_retryable_stream_error` deleted (file 200 → 173 lines; unused `httpx`,
    `openai`, `ExecutionFailure`, `retryable_transient_status` imports removed).
  - `src/claudey/providers/openai_chat/provider.py:50-56,852,894` — import swap +
    two `recovery=True` call sites.
  - `tests/providers/test_stream_recovery.py:6-12,25-90` — 8 assertions switched to
    `is_retryable_error(..., recovery=True)`; existing pinned assertions unchanged.

## Verification Outputs (contract order)

| Step | Command | Outcome |
|---|---|---|
| TDD pin (pre-merge) | `uv run pytest tests/providers/test_retryability_matrix.py -n0 -q` | **31 passed** against current code (2 wrong hand-derived expectations corrected by the pin) |
| Format | `uv run ruff format <5 touched files>` | 5 files left unchanged |
| Lint | `uv run ruff check --fix <5 touched files>` | 6 unused imports auto-removed (`stream_recovery.py`), 0 remaining |
| Types | `uv run ty check` | All checks passed |
| Targeted | `uv run pytest <matrix + 6 pinned retry files> -n0 -q` | **113 passed** |
| Consumers | `test_failure_policy.py test_provider_admission.py test_openai_chat_*.py -n0` | **112 passed** |
| Boundary | `tests/contracts/test_import_boundaries.py -n0` (in the batch) | green |
| Full gate | `./scripts/ci.sh` | **All 7 checks passed; 3142 passed, 73 skipped** (3111 baseline + 31 new matrix tests) |
| Coverage | `uv run pytest --cov=claudey --cov-report=term-missing -q` | TOTAL 19707 stmts / 1868 miss / **91%** |
| Grep gate | `grep -rn is_retryable_stream_error src/ tests/ smoke/` | 0 code hits (one docstring mention in the matrix test header) |

## Coverage Delta

Baseline (Sprint 0): 90%; Sprint 2: 91%; now: **91%** (19707 stmts / 1868 miss;
+31 matrix tests offset by the ~30-line classifier consolidation). Above baseline
and ≥80%.

## Rebuttals

None — all plan actions executed. Two evidence-backed clarifications (not
deviations): (1) the plan's "omits the `httpx.WriteError` … variants" describes the
explicit tuple membership; the effective stream decision for `WriteError` is
unchanged because it is a `NetworkError` subclass, and the matrix pins it as
retryable in both contexts. (2) `is_retryable_provider_error` remains as a
one-line delegate rather than being deleted, because `admission.py` and
`test_failure_policy.py` call it and the orchestrator's frozen-surface rule
requires public signatures the rest of the code calls to stay stable; the decision
table lives in exactly one place.

## Residual Risks

1. The `recovery: bool` context switch is order-sensitive by design (permission
   short-circuit before vs after transient-status inference; leading protocol
   membership). The matrix test pins both contexts on 31 families, and the two
   adversarial rows (`permission_denied_with_retryable_body`, `httpx_timeout_exception`)
   lock the ordering divergences — any future reordering fails loudly.
2. Zero user-visible change: retry budgets/backoff constants untouched
   (`admission.py` 5 attempts / 2.0s / 60s / 1.0; auth-latch TTL; `stream_recovery.py`
   holdback `0.75s` / `64KiB` — verified in the diff), wording constants in
   `failure_policy.py` untouched, signatures stable.
