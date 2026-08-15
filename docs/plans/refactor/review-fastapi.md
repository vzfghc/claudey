# FastAPI Review: Phase A Post-Refactor

Reviewed at `891d468c` on `feat/phase-a-free-providers`.

## 1. LOCAL_PROVIDER_PATHS URL map — correct

**File: `src/claudey/config/constants.py:14-18`**

The map keys `("lmstudio", "llamacpp", "ollama")` match `PROVIDER_CATALOG` keys at `src/claudey/config/provider_catalog.py:412-437`. The env-var values (`LM_STUDIO_BASE_URL`, `LLAMACPP_BASE_URL`, `OLLAMA_BASE_URL`) are the validation aliases on `Settings` fields (`src/claudey/config/settings.py:160-174`) and match the manifest-generated field keys (`src/claudey/config/admin/provider_manifest.py:195`, using `_settings_env_key`).

The lookup chain in `admin_routes.py:388-393` (`_local_provider_url`) reads from the `load_config_response()` value dict keyed by env-var name — the same keys the manifest emits. No drift.

## 2. admin_routes.py — bare `try/except` in local-prober is acceptable

**File: `src/claudey/api/admin_routes.py:396-427`**

`_check_local_provider` catches raw `Exception` on the HTTP probe. This is correct by design: the function is a best-effort status check (local-only, async endpoint). It never raises — it returns a structured `dict` with `error_type`. The calling endpoint `local_provider_status` (line 266) then returns this dict in a JSON envelope. A network timeout, DNS failure, or connection refused will produce `"status": "offline"` with `error_type`, never a 500. This is acceptable for an admin-only diagnostic endpoint.

## 3. Streaming — correct, no known leaks

**File: `src/claudey/api/response_streams.py`**

The `ManagedStreamingResponse` class manages cleanup via `_close` → `_cleanup` in the `__call__` finally block. The `_cleanup` task is deduplicated and shielded. `_wait_for_cleanup` correctly restores caller cancellation. `bind_response_lifetime` (line 152) handles all three cases:

- `ManagedStreamingResponse` — deferred release via `bind_release`
- Plain `StreamingResponse` — TypeError, closes iterator and releases immediately (defensive)
- Non-streaming response — calls `await release()` immediately

**File: `src/claudey/api/handlers/messages.py:152-219`**

The non-streaming path aggregates (line 166) and handles `BaseExceptionGroup`, `ExecutionFailure`, and generic `Exception` independently. The streaming path delegates to `anthropic_sse_streaming_response` which wraps via `_first_chunk_streaming_response` + `_PrefetchedStream`. The `_PrefetchedStream.__anext__` method handles `BaseExceptionGroup` from Python 3.14 `TaskGroup` semantics (line 304-305) — a Python 3.14-specific concern, correctly implemented.

No unclosed generators or silently truncated streams were found.

## 4. Error mapping — complete

**File: `src/claudey/api/app.py:47-119`**

Three exception handlers:

| Exception | Status | Wire format | Notes |
|---|---|---|---|
| `RequestValidationError` | 422 | FastAPI default | Logs shape, defers to built-in handler |
| `ApplicationError` | `error.status_code` | Anthropic / OpenAI per path | Maps `InvalidRequestError` → 400, `UnknownProviderError` → 400 (extends InvalidRequestError), `ApplicationUnavailableError` → 503 |
| `Exception` (catch-all) | 500 | Anthropic / OpenAI per path | Logs safely (traceback only when `log_api_error_tracebacks` is on) |

No holes: `ApplicationUnavailableError` has its own handler (the `ApplicationError` handler) so it correctly returns 503, not 500.

## 5. Async correctness — one blocking-dashboard issue (MEDIUM)

**File: `src/claudey/api/admin_dashboard.py`**

`dashboard_payload()` (line 216) calls:
- `latest_commits()` (line 223) — calls `subprocess.run()` (blocking, reused from prior code)
- `cost_entries()` (line 224) — file I/O (blocking)
- `usd_to_idr()` (line 237) — calls `httpx.Client` (sync, blocking, line 140)

All three block the async event loop because `get_admin_dashboard` (admin_routes.py:204) is a coroutine endpoint. For a local-only admin endpoint called at most once per page load this is tolerable, but it violates the no-blocking-in-async-routes guideline.

Fix: wrap the three blocking calls in `asyncio.to_thread()` with a timeout, or run `dashboard_payload` itself in a thread.

## 6. Static file serving — no `StaticFiles` mount, path-traversal guarded

**File: `src/claudey/api/admin_routes.py:183-191, 194-201`**

Files are served through explicit APIRouter routes with resolved-path containment checks (`root not in path.parents`). For `/admin/assets/{filename}` the root is `ADMIN_UI_DIR`, for `/admin/assets/logos/{filename}` it's `(STATIC_DIR / "logos")`. Both guard against traversal. No `StaticFiles` mount exists, which means no `starlette.staticfiles` cache headers or directory listing — correct for an admin-only surface.

## 7. Admin route paths — stable

All admin routes retain their original paths: `/admin`, `/admin/ui`, `/admin/api/dashboard`, `/admin/api/config`, `/admin/api/config/validate`, `/admin/api/config/apply`, `/admin/api/restart`, `/admin/api/status`, `/admin/api/providers/custom`, `/admin/api/providers/custom/{provider_id}`, `/admin/api/providers/custom/validate`, `/admin/api/combos`, `/admin/api/combos/{combo_id}`, `/admin/api/combos/validate`, `/admin/api/providers/local-status`, `/admin/api/providers/{provider_id}/test`, `/admin/api/providers/{provider_id}/auth`, etc. No breaking changes post-refactor.

Public routes unchanged: `/v1/messages`, `/v1/responses`, `/v1/messages/count_tokens`, `/v1/models`, `/health`, `/stop`, `/`.

## 8. Dependencies — sound

**File: `src/claudey/api/dependencies.py`**

- `get_services` reads from `request.app.state.services` — correct, no stale imports
- `resolve_provider` documents `PROVIDER_CATALOG` in error message for operator debugging
- `require_proxy_auth` uses `secrets.compare_digest` (constant-time comparison). No stale imports

## 9. Tests

Tests checked: `uv run pytest -x --tb=short` (3022 passed, 2 pre-existing failures). The 2 failures (`test_optional_model_combobox_typing_replaces_none_default` and `test_custom_provider_buttons_visible`) are documented pre-existing (admin-ui React scaffold Phase 3 work deferred by the user, tracked in `claudey-frontend-stack.md`). Both are Playwright-based tests that trace to phase-a providers-track drift, not FastAPI correctness.

## 10. Residual risk

- **None identified for FastAPI correctness.** The application factory, routing, middleware, dependencies, streaming, error handlers, and static serving are production-ready.
- The one MEDIUM issue (`admin_dashboard.py` blocking I/O) only affects the local admin page and is safe under the current load profile (one user, one browser tab). Fix if latency on the dashboard page becomes noticeable.
- The 2 pre-existing Playwright test failures are unrelated to FastAPI and are known scaffold drift.

### Findings summary

| Severity | Finding | File |
|---|---|---|
| MEDIUM | Blocking subprocess/httpx/file I/O in async dashboard endpoint | `src/claudey/api/admin_dashboard.py:45-148` |
