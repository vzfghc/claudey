# Evaluation — Sprint 2, Iteration 001 (SSE parsing consolidation, H3)

Branch: `feat/phase-a-free-providers` · Commit: `d14cfcf0` · 2026-08-13 · Evaluator-verified, generator report NOT trusted.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 — CI gate green | 10/10 | 0.30 | 3.00 |
| C2 — Behavior preservation | 10/10 | 0.25 | 2.50 |
| C3 — Principle adherence | 10/10 | 0.20 | 2.00 |
| C4 — Dead-code & hygiene | 7/10 | 0.10 | 0.70 |
| C5 — Code health | 9/10 | 0.15 | 1.35 |
| **TOTAL** | | | **9.55/10** |

## Verdict: PASS (threshold 7.0)

## Verification Commands Run (all by the evaluator)

| Command | Outcome |
|---|---|
| `uv run pytest tests/contracts/test_import_boundaries.py -n0` | **21 passed** |
| `./scripts/ci.sh` (full) | **All 7 checks passed, exit 0; 3111 passed, 73 skipped** |
| `git status --porcelain` after ci.sh + `git diff --stat` | **Zero tracked dirt** — ci.sh repaired nothing post-commit; only pre-existing untracked junk (Sprint 8 scope) |
| `uv run ruff format --check` + `uv run ruff check` | 503 files already formatted; all checks passed (check-only clean = GitHub CI state) |
| `uv run pytest --cov=claudey --cov-report=term-missing -q` | **TOTAL 19712 stmts / 1869 miss / 91%** — ≥80% and ≥90% baseline |
| `uv run pytest tests/core/openai_responses/test_sse.py tests/core/anthropic/ -n0 -q` | **114 passed** (incl. the 11 new parser tests) |
| `git show d14cfcf0 --stat` / `-- tests/` | Only test change: NEW `tests/core/anthropic/test_sse_parser.py` (91 L). No existing test edited, no assertion relaxed |
| `grep -rnE '\+= chunk|\+= args|\+= arguments|buffer \+='` over parser + 3 consumers + 4 accumulators | 0 hits (exit 1) |
| `grep -rn '_buffer +='` over `core/`, `application/`, `providers/openai_chat/` | 0 hits |
| `git show d14cfcf0 --check` | No whitespace errors |
| `git show d14cfcf0 --stat \| grep pyproject/.env/settings/ARCHITECTURE/smoke` | 0 hits — frozen surfaces untouched |
| Suppression grep over the diff (`type: ignore`, `ty: ignore`, `from __future__`) | 0 hits |
| sse_parser.py imports | Only `collections.abc` — core stays SDK-free |

## Criterion Justifications

**C1 = 10** (band: "All 7 checks pass on the evaluator's first run; git status clean of stray artifacts"). All 7 checks green on my first run; boundary 21/21; zero tracked dirt after ci.sh (the committed state was already format/lint-clean — check-only variants pass), and the generator's reported outputs (3111/73, 91%, 21, greps 0) all reproduced. The untracked root screenshots / `.playwright-mcp/` / `model-config-skeleton.yml` are the recorded Sprint-0 baseline junk, scheduled for deletion in Sprint 8 — not this sprint's artifacts.

**C2 = 10** (band: "Full suite green; coverage ≥80% and ≥baseline; protocol/env/payload/CLI/retry/wording diff audit clean"). Full suite green; coverage 91% ≥ 80% and ≥ 90% baseline. Diff audit of the three consumer sites (read in full, both sides):
- **Site 1** `openai_responses/anthropic_sse.py:24-27`: bytes decoded `utf-8 errors="replace"`, else `str(chunk)` — identical (`sse_parser.py:29-34`); flush-on-normal-exhaustion preserved — `iter_raw_sse_events`' flush block sits after its own `async for` (`sse_parser.py:75-78`), so a source exception propagates past it exactly like the original's in-`try` flush; `close_stream_input` finally untouched; `close_calls == 1` pinned by 6 assertions in `test_sse.py:73,90,106,135,162`, all green (verified: `async for` never acloses the iterated source).
- **Site 2** `sse_aggregation.py:90-92`: trailing partial dropped (default `flush_trailing=False`) matches the original no-flush; `parse_sse_text(raw + "\n\n")` and `handle_payload` (no break — no control-flow change) identical.
- **Site 3** `usage_recorder.py:162-176`: `yield chunk` before parse ordering preserved; the finally-flush stays gated on `not isinstance(pending, GeneratorExit | asyncio.CancelledError)`; the only merged case — whitespace-only tail (original truthy check vs new `trailing() is None`) — is provably unobservable: `parse_sse_text("   \n\n")` yields nothing (`stream_contracts.py` `_append_event` returns when no `event:`/`data:` lines; verified by reading).
- Splitter split-all-at-once vs original repeated first-delimiter split is equivalent including `"\n\n\n\n"` overlap and `"\n\n\n"` odd-newline cases (verified by hand-tracing).
- The four accumulators (`ledger.py:117,119,136`, `tool_calls.py:259-261,278`, `thinking.py:42-61`, `tools.py:98-194`) preserve join inputs byte-identically (sha256/len over `joined`, same `""`-vs-`[]` truthiness, same drop-vs-keep remainder rule in `tools.py` flush: dropped in PARSING_PARAMETERS, kept otherwise).
- No wire/SSE format/stop-reason/env/payload/wording change anywhere; only docstring touched (`core/errors.py:1` — sanctioned carry-over).

**C3 = 10** (band: "All in-scope violations resolved; all grep gates at 0; zero new violations"). One shared incremental parser in `core/anthropic/`; all three consumers import from it (`sse_aggregation.py:15`, `anthropic_sse.py:9`, `usage_recorder.py:24`); consumers keep their own event interpretation (`parse_sse_event`/`parse_sse_text` untouched — plan step 3 honored); the `SseEventSplitter` addition is a legitimate response to the tee requirement, documented in the report; zero `+=` string buffers in the flagged sites; no new cross-layer edges (new imports are core→core and application→core, both contract-legal); no shims, no local-import cycle dodges, no suppressions.

**C4 = 7** (neutral sprint — no junk added). The commit contains exactly the sprint's source files + report + new test. Pre-existing untracked junk (root screenshots, `.playwright-mcp/`, `model-config-skeleton.yml`, plus the never-committed plan docs `REFACTOR_PLAN.md`/`RUBRIC.md`/`feedback-*`) is Sprint-8 deletion scope; noted here for the orchestrator, not scored against this sprint.

**C5 = 9** (band: "All checks pass with one minor nit"). All touched files <800 lines (largest: `ledger.py` 555); new parser 78 lines with functions 5-17 lines; no suppressions; list accumulation everywhere; no magic numbers introduced; no mutation of frozen dataclasses (the `list` buffer fields are internal state of already-mutable ledgers). One nit: `HeuristicToolParser.feed` is 97 lines (`tools.py:98-194`; 93 pre-sprint) — pre-existing size, not inflated by this refactor, but it is touched code above the 50-line guideline; see finding 1.

## Findings

### LOW — C5: `HeuristicToolParser.feed` exceeds the 50-line guideline in touched code
- Evidence: `src/claudey/core/anthropic/tools.py:98-194` (97 lines; 93 lines pre-sprint).
- Why it's only LOW: the size predates this sprint; the refactor only converted the buffer mechanics and did not add logic. Not a Sprint-2 acceptance blocker (plan §7 acceptance lists the `+=` greps, not function length).
- Fix directive: optional in this iteration; if you touch `feed` again, split the three state branches (TEXT / MATCHING_FUNCTION / PARSING_PARAMETERS) into helper functions. Otherwise leave for the Sprint-7 size sweep.

### LOW — C5 (informational): pre-existing string concat in a touched file
- Evidence: `src/claudey/providers/openai_chat/tool_calls.py:371` — `tool_argument_alias_buffers.get(tc_index, "") + args`.
- Not one of the four flagged sites, does not match any acceptance grep pattern, untouched by this commit. Recorded so Sprint 7's list-accumulation sweep can pick it up. No action required this iteration.

### LOW — report accuracy nit
- `sprint-report-2-001.md` line 101 claims coverage "1871 miss"; my run shows 1869 miss. Same TOTAL (91%) and same stmts (19712); likely a run-state artifact. All other claimed outputs reproduced exactly.

### INFO — site 2 bytes tolerance (not a regression)
- `sse_aggregation.py`'s stream is typed `AsyncIterator[str]`; the old `buffer += chunk` would have raised `TypeError` on a bytes chunk, the new parser decodes it. Strictly more lenient, unreachable-by-type. No action.

## What Was Done Correctly (do not churn)

- The parser's split-all-at-once is provably equivalent to the original per-site while-loops, including the overlapping-delimiter edges — no event test needed to change, and none did.
- The three per-site trailing-partial semantics were captured correctly before merging (flush-on-exhaustion / dropped / exception-gated flush) and preserved as distinct call-site policies rather than flattened.
- The whitespace-tail merge is genuinely unobservable (verified in `stream_contracts.py`), and the report documents it honestly instead of hiding it.
- `usage_recorder.py`'s yield-before-parse tee ordering and the one-shot `recorded` flag are intact.
- The report's close-path claim (async-for does not aclose the source; `close_calls == 1` pinned) is correct and empirically green.
- New tests assert exact event content, not counts; they cover every boundary case in plan step 2 plus bytes decode replacement and whitespace-only trailing.

## Residual Risk Notes (evaluator agrees with the report)

- Mid-iteration `feed()` abandonment in the two core parsers now loses the local-frame buffer; the report's unreachability analysis (fully exhausted per chunk at `provider.py:481,497`; fresh parser on every abandonment path) is sound, and no test or production path observes the difference. Not a blocker; if a future change introduces an early `break`, revisit.
- O(n²) splitter cost is identical to the original `buffer +=` + `in` scan; not a regression.

## Probes Run (rubric §9 iteration-1 discipline)

Boundary test `-n0`; full ci.sh + post-CI dirt check + check-only ruff; coverage run; the exact acceptance greps on all eight files; extended `_buffer +=` grep across three packages; cross-layer import probes (`from claudey.application` in providers/ — only the contract-legal pre-existing `connected_accounts` imports, Sprint-1 scope, not this commit; `from claudey.providers` in config/ and application/ — 0); `git show --check`; frozen-surface file probe; suppression grep on the diff; parser-import audit (SDK-free); consumer-import audit (exactly 3 consumers); close-call pinning assertions in `test_sse.py`.
