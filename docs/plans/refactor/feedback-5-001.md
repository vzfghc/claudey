# Evaluation — Sprint 5, Iteration 001 (Messaging dedup I: inbound glue + queued messenger)

Branch: `feat/phase-a-free-providers` · Commit: `746c9568` · 2026-08-13 · Evaluator-verified, generator report NOT trusted.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 — CI gate green | 10/10 | 0.30 | 3.00 |
| C2 — Behavior preservation | 5/10 | 0.25 | 1.25 |
| C3 — Principle adherence | 7/10 | 0.20 | 1.40 |
| C4 — Dead-code & hygiene | 7/10 | 0.10 | 0.70 |
| C5 — Code health | 8/10 | 0.15 | 1.20 |
| **TOTAL** | | | **7.55/10** |

## Verdict: PASS (threshold 7.0) — with 2 HIGH behavior regressions to fix in iteration 2

## Verification Commands Run (all evaluator-run)

| Command | Outcome |
|---|---|
| `uv run pytest tests/messaging/ tests/contracts/test_import_boundaries.py` | **514 passed** (inbound + boundary contract green) |
| `uv run pytest -q` (full suite) | **3142 passed, 73 skipped** — matches the generator's reported count exactly |
| `uv run pytest --cov=claudey --cov-report=term -q` | **TOTAL 19733 stmts / 1869 miss / 91%** — ≥80% and ≥90% baseline |
| `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check` | **All passed** (check-only clean = GitHub CI state; 506 files formatted, zero lint, zero type errors) |
| `uv run python scripts/fetch_provider_logos.py --check` / `generate_icons.py --check` | logos 38/38 present, icons 8/8 present |
| suppressions grep (`from __future__ import annotations`, `# type/ty: ignore`) | **0 hits** repo-wide |
| `git diff 59d14b0b..HEAD --stat` | 7 files, all messaging-scope: `base_messenger.py` (+188), `inbound_utils.py` (+34), `discord_io.py` (−70), `telegram_io.py` (−85), `discord_inbound.py` (−30), `telegram_inbound.py` (−28), `gan-harness/generator-state.md` |
| `git status --porcelain` | untracked root junk (`.playwright-mcp/`, root screenshots, `model-config-skeleton.yml`) timestamps 08-10..08-12 — **pre-existing baseline, not sprint-5 dirt** |
| Full read of new files + both inbound consumers + both `*_io.py` | see C2/C3 below |

## Criterion Justifications (score bands cited)

### C1 = 10 (band: "All 7 checks pass on the evaluator's first run; git status clean of stray artifacts")
First-run green on all 7 checks. No `git checkout` repair needed — the committed state is check-only clean. Boundary contract 21/21. Untracked junk is the pre-recorded Sprint-8 baseline (plan §2 step 3), untouched by this commit.

### C2 = 5 (band: "A user-visible string or constant changed accidentally … flagged with file:line in feedback")
Full suite green and coverage 91% ≥ baseline — but the diff audit found **two genuine user-visible behavior regressions on the Telegram wire**, both self-inflicted by flattening the queue wrappers into the base. Full detail in HIGH-1/HIGH-2 below. Neither is caught by the suite because the handler-level tests mock `OutboundMessenger` (`tests/conftest.py:133`) and the real `TelegramMessenger` tests never assert a queued-send with `parse_mode` omitted.

### C3 = 7 (band: "One in-scope violation unresolved at iteration end, or a workaround used")
The inbound glue and the QueuedMessenger extraction are architecturally sound (single `text_preview` implementation, no `+=` accumulation, hooks not flattening). But the base's flattened `parse_mode: str | None = None` default silently erased Telegram's `"MarkdownV2"` queue default — the one place where the "shared bookkeeping" layer leaked a platform-specific behavior. That is a new (behavior) divergence introduced by the extraction rather than resolved. Cluster B and `VoiceNoteRequest` deviations are correctly recorded and match the plan's conditional ("otherwise leave them and note why").

### C4 = 7 (neutral sprint — no dead-code work in scope; no junk added)
Sprint 5 adds no junk; diff is exactly sprint-scope (7 files, no out-of-scope edits, no test edits). Neutral score per rubric.

### C5 = 8 (band: "All checks pass with one minor nit")
`base_messenger.py` 188 L, focused, ABC with a sane 4-primitive/4-hook surface; `inbound_utils.py` 34 L; `discord_io.py` 105 L; `telegram_io.py` 256 L — all <800. Functions all <50 L. Zero suppressions. List accumulation in `inbound_utils.py:17` (`"".join([raw_content[:80], "..."])[:80]`), no `+=`. **Nits:** (1) `telegram_io.py:254-256` — `_delete_many_fallback` is a verbatim override that just calls `super()`. It is dead weight: nothing calls `_delete_many_fallback` (grep: only base def + this override + the docstring). Remove the override (and the base hook if it stays unused — see HIGH-2). (2) The base's three default hooks `_send_via_retry`/`_edit_via_retry`/`_delete_via_retry` are identity pass-throughs and `_delete_via_retry` is never overridden nor invoked — the send-path wiring added a `_with_retry` wrapper that did not exist on the old queued path (see HIGH-2); the base retry indirection is more machinery than the two subclasses need.

## Issues

### CRITICAL
None.

### HIGH
1. **`base_messenger.py:137,156` — Telegram queued sends/edits lost the `"MarkdownV2"` default.** Pre-sprint `TelegramMessenger.queue_send_message`/`queue_edit_message` defaulted `parse_mode="MarkdownV2"` (`telegram_io.py@59d14b0b`). The base flattens the default to `None` and Telegram no longer overrides it. Consequences on the Telegram wire:
   - `turn_intake.py:96` (`queue_send_message(chat_id, status_text, reply_to=..., fire_and_forget=False)` without `parse_mode`) previously sent the initial status ("⏳ *Launching new Claude CLI instance\.\.\.*" — MarkdownV2 bold markup from `telegram_markdown.py:44-49`) with `parse_mode="MarkdownV2"`; now sends `None` → **raw `*...*` asterisks rendered literally** for every new conversation status.
   - `commands.py:18,77,152` (`/stop`, `/stats`, `/clear` feedback, also `parse_mode`-less) — same regression. `/stop` currently sends "⏹ *Stopped\\.* Nothing to stop\\." as literal text.
   - Edit path equivalent: `node_runner.py:105`-style edits already pass `parse_mode=` explicitly, so the higher-risk surface is the send path above, but the base default is still wrong for Telegram's API.
   - **Fix:** move the default to the Telegram override — `queue_send_message(..., parse_mode: str | None = "MarkdownV2")` and `queue_edit_message(..., parse_mode="MarkdownV2")` in `telegram_io.py`, or (preferred) re-add a per-class `_default_parse_mode` hook on the base and override it in Telegram. The plan's "platform-specific behavior preserved via hooks (no behavior flattening)" requires exactly this. Note: `telegram.py:272` (direct `send_message`) and `telegram_inbound.py:117` already pass `"MarkdownV2"` explicitly, so those paths are fine — only the queued path regressed.

2. **Queued Telegram sends now route through an extra `_with_retry` wrapper — a real retry-behavior change on the wire.** Pre-sprint wiring: `outbox.send=self.send_message` → queue's `_send()` called `send_message` **directly**, i.e. queued sends were NOT retried (only the retry *inside* `send_message`'s `_do_send` closure applied — one shot). Post-sprint: `base._send_queued` → `_send_via_retry` → `_with_retry(func, *args, **kwargs)`. Because the primitives themselves already carry `_with_retry` internally, a transient network error mid-send now causes **two retry stacks** (the queued wrapper's 3-attempt loop around a closure that itself retries 3×), changing both the retry count (up to ~9 attempts), the sleep pattern (2^attempt from two nested loops), and the suppression semantics (the queued wrapper's default `suppress_known_message_errors=True` is now applied to the outer call where the old queued path had none). Under the frozen-invariant table (`§10`: messaging behavior guarded by `tests/messaging/`) this is a violation that the suite cannot see because no test exercises the queued path through the real messenger with a network error injected. Same logic applies to the edit path (`_edit_via_retry`). **Fix:** wire the outbox straight to the platform primitives as before — `PlatformOutbox(send=self.send_message, edit=self.edit_message, delete_many=self.delete_messages)` in `base.__init__` (as the pre-sprint subclasses did), and drop the `_send_via_retry`/`_edit_via_retry`/`_delete_via_retry` hooks entirely unless a genuine per-operation policy difference can be demonstrated. The delete-many path (HIGH-candidate) did not change: both old and new wire `delete_many=delete_messages` (batched + inline per-chunk fallback), and `_delete_many_fallback` is never called.

### MEDIUM
None beyond the two HIGHs (the second is partly a C5-machinery nit too).

### LOW
1. **`telegram_io.py:254-256`** — C5. Dead override `_delete_many_fallback` (verbatim `super()` call, zero callers). Remove it; if no subclass needs the hook after the HIGH-2 fix, remove the base hook too.
2. **`base_messenger.py:59-84`** — C5 (note). The three default identity hooks are unused indirection for both current subclasses (discord uses no overrides; telegram's override only matters if the HIGH-2 wiring is kept). Prefer `send_message`-style direct wiring over a hook surface nobody parameterizes.

## Positive Findings (do not churn these)

- **Inbound glue is exactly right.** `inbound_utils.log_incoming_text_message` produces byte-identical log lines to both pre-sprint blocks (verified by diffing `telegram_inbound.py`/`discord_inbound.py` pre/post — same `{}_MSG: chat_id={} ... text_preview={!r}` and `text_len={}` shapes, same `raw_content[:80]` + `"..."` truncation semantics for both the ≤80 and >80 cases, parameterized by `platform_label`). List accumulation, no `+=`. Zero remaining `text_preview` implementations outside `inbound_utils.py` (grep → 1 hit, the single source).
- **Cluster B and VoiceNoteRequest deviations are legitimately recorded.** `_download_to`/`_reply_text` differ in the SDK primitive (`download_to_drive(custom_path=...)` vs `attachment.save(...)`, `reply_text` vs `reply`); abstracting would force thunks with no platform-neutral name. `VoiceNoteRequest` construction differs in real fields (`status_parse_mode`, `temp_suffix` provenance). Both match the plan's "otherwise leave them and note why" — correctly not folded.
- **The base class shape is right where it matters:** queue/edit-batching/delete-coalescing/dedup/timer/fire-and-forget all genuinely shared via `PlatformOutbox`; `close()` semantics preserved; signature order and defaults for `queue_delete_messages`/`fire_and_forget`/`close` byte-identical to both pre-sprint classes.
- **Hook-surface intent is sound** (retry + delete-many-fallback) — it just needs the wiring fix in HIGH-2 to match the actual per-platform policies.
- The diff is tight: no out-of-scope edits, no test edits, no version bump, no `ARCHITECTURE.md` churn needed.

## What Improved Since Last Iteration

N/A — first iteration of Sprint 5.

## Specific Suggestions for Next Iteration

1. Fix HIGH-1: restore `parse_mode="MarkdownV2"` defaults on Telegram's queued send/edit (via override or a `_default_parse_mode` hook). Add a regression test that runs a real `TelegramMessenger.queue_send_message("chat_1", status_text, fire_and_forget=False)` through a stubbed bot and asserts `parse_mode="MarkdownV2"` reaches `app.bot.send_message` — the current suite has a gap here (handler tests mock the messenger; `test_telegram.py` queue test asserts only `enqueue` called once).
2. Fix HIGH-2: wire the outbox directly to the primitives (`PlatformOutbox(send=self.send_message, edit=self.edit_message, delete_many=self.delete_messages)`), drop the unused retry hooks or keep only hooks with a demonstrated per-platform policy difference. After the fix, re-verify: queued path = one `_with_retry` stack (the primitive's own), matching pre-sprint.
3. Fix LOW-1 (delete `_delete_many_fallback` override) and reconsider the base's identity hooks.
4. Re-run the full gate after the fixes; the suite should stay at 3142 passed with the two new regression tests added.
