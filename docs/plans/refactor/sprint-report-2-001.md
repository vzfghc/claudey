# Sprint Report — Sprint 2, Iteration 001

Sprint: SSE parsing consolidation (H3) · Branch: `feat/phase-a-free-providers` · 2026-08-13

## What Was Done

**H3 — one shared incremental SSE parser in `core/anthropic/`.** Created
`src/claudey/core/anthropic/sse_parser.py` with two primitives:

- `SseEventSplitter` — stateful chunk accumulator (list-of-chunks + `"".join`, no `+=`):
  bytes decoded `utf-8 errors="replace"`, str used as-is, empty chunks no-ops,
  `feed()` returns the raw event texts completed by that chunk (one/many per chunk,
  split across boundaries), `trailing()` exposes the buffered partial.
- `iter_raw_sse_events(chunks, *, flush_trailing=False)` — async iterator over
  `AsyncIterable[bytes | str]` wrapping the splitter; yields raw event bodies
  (delimiter excluded) so each consumer keeps its own event interpretation
  (`parse_sse_event` / `parse_sse_text` untouched — plan step 3).

**Semantics capture (before touching, per plan step 1).** The three loops differed in
input type and trailing-partial behavior:

| Site | Input | Trailing partial |
|---|---|---|
| `core/openai_responses/anthropic_sse.py` `iter_sse_events` | `AsyncIterable[Any]`, bytes→`decode(utf-8, errors="replace")`, else `str(chunk)` | Flushed **only on normal exhaustion** (flush sits after the `async for`, inside `try`, not `finally`); `.strip()`-checked; parsed by its own `parse_sse_event` |
| `core/anthropic/sse_aggregation.py` `aggregate_anthropic_sse_to_message` | `AsyncIterator[str]` | **Dropped** — no flush at all |
| `application/usage_recorder.py` `observe_usage` | `AsyncIterator[str]`, tees chunks unchanged before parsing | Flushed in `finally`, **skipped when pending exception is GeneratorExit/CancelledError**; truthy-checked; `parse_sse_text(raw + "\n\n")` |

All three now share `sse_parser`; per-site flush policy is a parameter
(`flush_trailing=True` for `iter_sse_events`, `False` default elsewhere) or the
splitter's `trailing()` gated on the site's existing exception check
(`usage_recorder`). The whitespace-only-tail difference (site 1 `.strip()` vs site 3
truthy) is merged into `trailing()` (returns `None` for blank buffers): both
consumers' parsers no-op on whitespace-only input (`parse_sse_event` → None,
`parse_sse_text` yields nothing), so the distinction is unobservable downstream —
verified by reasoning, not by behavior change.

**Close-path verification (empirical).** `async for` does **not** call `aclose()` on
the iterated source on normal exit, `return`, or `GeneratorExit` propagation
(reproduced with CPython). The source's `aclose` is therefore still called exactly
once — by the consumer's `close_stream_input` in `finally` — pinning
`close_calls == 1` in `test_sse.py` (`test_anthropic_sse_parser_closes_source_on_early_close`
and `..._after_normal_completion` both green). Source-failure precedence
(`preserved_error=sys.exception()`) and the no-flush-on-exception path are preserved
because the parser's trailing block sits after its own `async for`, exactly like the
original loop.

**Four string-accumulator buffers → chunk lists (plan step 4).**

- `core/anthropic/streaming/ledger.py` — `ToolBlockState.task_arg_buffer` and
  `pre_start_args` are now `list[str] = field(default_factory=list)`;
  `buffer_task_args` appends + joins at `json.loads`, `flush_task_arg_buffers` joins
  once for `json.loads`/sha256/`len` (identical digest input bytes and warning
  content).
- `providers/openai_chat/tool_calls.py:259-261,278` — `pre_start_args` appended per
  delta, `"".join` at the emit site.
- `core/anthropic/thinking.py` — `ThinkTagParser._chunks: list[str]`; `feed` joins
  once, the two `_parse_*` helpers became pure `(chunk, buffer) → (chunk|None,
  new_buffer)` functions, remainder stored back as a single chunk.
- `core/anthropic/tools.py` — `HeuristicToolParser._chunks: list[str]`; `feed`
  operates on a local buffer, `_extract_web_tool_json_calls` /
  `_split_incomplete_control_token_tail` became buffer-in/out helpers, remainder
  stored back; `flush` joins + strips, keeping the original drop-vs-keep remainder
  rule (kept in non-PARSING_PARAMETERS state, dropped in PARSING_PARAMETERS).

**Carry-over (feedback-1-001 LOW).** `src/claudey/core/errors.py:1` docstring
rewritten to "Canonical SDK-free error types shared across layers." (docstring-only).

## Files Changed

- **Created** (2): `src/claudey/core/anthropic/sse_parser.py` (parser + splitter);
  `tests/core/anthropic/test_sse_parser.py` (11 tests: one event/chunk, many
  events/chunk, split across boundaries, empty chunks, bytes+str mix, decode
  replacement, trailing dropped/flushed/whitespace-only, splitter partial across
  chunks).
- **Modified** (8):
  - `src/claudey/core/openai_responses/anthropic_sse.py:21-33` — loop replaced by
    `iter_raw_sse_events(iterator, flush_trailing=True)` + `parse_sse_event`;
    `close_stream_input` finally unchanged.
  - `src/claudey/core/anthropic/sse_aggregation.py:90-93` — loop replaced by
    `iter_raw_sse_events(stream)`; `parse_sse_text(raw_event + "\n\n")` unchanged.
  - `src/claudey/application/usage_recorder.py:119-181` — tee loop feeds
    `SseEventSplitter`; `finally` flush now `splitter.trailing()` under the same
    GeneratorExit/CancelledError gate; chunk yield order unchanged.
  - `src/claudey/core/anthropic/streaming/ledger.py:40-42,117,119,127,133-156` —
    buffer fields + join-at-use.
  - `src/claudey/providers/openai_chat/tool_calls.py:259-261,278` — join/append.
  - `src/claudey/core/anthropic/thinking.py:33-143` — chunk-list parser.
  - `src/claudey/core/anthropic/tools.py:39-213` — chunk-list parser.
  - `src/claudey/core/errors.py:1` — carry-over docstring fix.

## Verification Outputs (contract order)

| Step | Command | Outcome |
|---|---|---|
| Format | `uv run ruff format <10 touched files>` | 3 files reformatted, 7 unchanged |
| Lint | `uv run ruff check --fix <10 touched files>` | All checks passed (0 remaining) |
| Types | `uv run ty check` | All checks passed |
| Targeted | `uv run pytest <9 affected files> -n0 -q` | **192 passed** (boundary, test_sse, test_streaming_errors, core/anthropic streaming, new parser test, usage recorder, parsers, stream contracts) |
| Boundary | `tests/contracts/test_import_boundaries.py -n0` (in the batch) | green |
| Full suite | `uv run pytest -q` | **3111 passed, 73 skipped** (3100 baseline + 11 new) |
| Coverage | `uv run pytest --cov=claudey --cov-report=term-missing -q` | TOTAL 19712 stmts / 1871 miss / **91%** |

Grep gate (plan acceptance): `grep -nE '\+= chunk|\+= args|\+= arguments|buffer \+='`
across the seven touched src files → **0 hits** (exit 1). Extended grep across
`src/claudey/core/`, `src/claudey/application/`, `src/claudey/providers/openai_chat/`
for `_buffer \+=` → **0 hits**.

## Coverage Delta

Baseline (Sprint 0): 90%. Now: 91% (+1 point, +34 stmts — new parser module and
tests). Above baseline and ≥80%.

## Rebuttals

None — all plan actions executed. Two design clarifications (not deviations, per plan
step 3's "only the buffering/splitting is shared"): the parser yields **raw event
texts** (not interpreted events) so each consumer keeps its own `parse_sse_event` /
`parse_sse_text`; and `SseEventSplitter` exists because `observe_usage` must tee
chunks through unchanged before parsing, which a plain async-iterator wrapper cannot
do.

## Residual Risks

1. **Mid-iteration abandonment of `feed()` generators** (`ThinkTagParser`,
   `HeuristicToolParser`): the remaining buffer now lives in `feed`'s local frame
   instead of `self._buffer`, so abandoning a feed mid-yield loses state. Analyzed
   unreachable in practice: `provider.py:481,497` fully exhaust `feed()` per chunk
   (no `break` in the consuming loops), and every abandonment path (stream close,
   midstream recovery) discards the parser and constructs a fresh one
   (`provider.py:595-596`); all tests exhaust `feed()` via `list()`/for. No test or
   production path observes the difference.
2. **Splitter cost**: per-chunk `join`+`split` is O(n) per chunk (O(n²) over a
   stream) — identical to the original `buffer += chunk` + `"\n\n" in buffer` scan
   complexity; not a regression, kept simple per KISS.
3. Zero user-visible change: no wire/event-ordering/stop-reason surface touched; the
   1,895-line `test_streaming_errors.py` plus `test_sse.py` pin the stream behavior
   and are green. `core/` remains SDK-free (new module imports only `collections.abc`).
