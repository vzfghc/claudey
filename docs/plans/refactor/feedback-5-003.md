# Evaluation — Sprint 5, Iteration 003 (Iter-3 re-score)

Branch: `feat/phase-a-free-providers` · Commit: `eb4f16dd` · 2026-08-13 · Evaluator-verified, generator report NOT trusted.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 — CI gate green | 10/10 | 0.30 | 3.00 |
| C2 — Behavior preservation | 10/10 | 0.25 | 2.50 |
| C3 — Principle adherence | 10/10 | 0.20 | 2.00 |
| C4 — Dead-code & hygiene | 8/10 | 0.10 | 0.80 |
| C5 — Code health | 10/10 | 0.15 | 1.50 |
| **TOTAL** | | | **9.80/10** |

## Verdict: PASS (threshold 7.0) — both iter-2 findings resolved; proceed to Sprint 6

Iter-1 was 7.55 → iter-2 was 9.05 → iter-3 is 9.80. The MEDIUM (explicit-None coercion) and LOW-1 (tests didn't reach the wire) are both resolved. The subclass-override pattern is a cleaner expression of the plan's "platform-specific behavior preserved" principle than the hook was.

## Verification Commands Run (all evaluator-run)

| Command | Outcome |
|---|---|
| `git show eb4f16dd --stat` | 3 files, all in scope: `base_messenger.py` (−10), `telegram_io.py` (+36/−4), `tests/messaging/test_telegram.py` (+60/−59) |
| `git diff 1d4255bd..eb4f16dd` | full diff read and analyzed — hook removed, subclass overrides added, fixture consolidated, wire-level assertions added |
| `grep -rn "_default_parse_mode" src/` | **0 hits** — hook deleted entirely |
| `grep -rn "_send_via_retry\|_edit_via_retry\|..." src/` | **0 hits** — dead retry hooks remain absent |
| `uv run pytest -v --tb=short -k "preserves_parse_mode"` | **4 passed** (send+edit x 2 parametrize cases each) — all wire-level assertions hit |
| `uv run pytest -v --tb=short tests/messaging/ tests/contracts/test_import_boundaries.py` | **519 passed** (messaging dir + boundary contracts) |
| `uv run pytest -q` (full suite) | **3147 passed, 73 skipped** (iter-2 baseline was 3145; the +2 are the new parametrize cases) |
| `uv run pytest --cov=claudey --cov-report=term -q` | **TOTAL 19714 stmts / 1861 miss / 91%** — ≥80% and ≥ Sprint-0 baseline |
| `uv run ruff format --check .` | **506 files already formatted** |
| `uv run ruff check .` | **All checks passed!** |
| `uv run ty check src/claudey/messaging/platforms/base_messenger.py src/claudey/messaging/platforms/telegram_io.py` | **All checks passed!** |
| `uv run python scripts/fetch_provider_logos.py --check` | **all 38 provider logos present** |
| `uv run python scripts/generate_icons.py --check` | **all 8 app icon assets present** |
| `grep -rE '# type: ignore\|# ty: ignore\|from __future__' --include='*.py' . --exclude-dir=.venv --exclude-dir=.git` | **0 hits** |
| `git status --porcelain` | only pre-existing untracked root junk (unchanged from Sprint-8 baseline); `admin-ui-check.png` deletion pre-existing |
| Diff `08d59425:telegram_io.py:232-265` vs `HEAD:telegram_io.py:227-261` | queue method signatures match pre-sprint baseline; `self._outbox` → `super()` is the only structural change |
| Full read of `base_messenger.py` + `telegram_io.py` | outbox wiring byte-identical to pre-sprint; no dead hooks; subclass overrides clean |

## Resolution of Iter-2 Findings

### MEDIUM (iter-2): "explicit None coerced to MarkdownV2" — RESOLVED

**Iter-2 state:** `base_messenger.py:71-72` applied `_default_parse_mode()` hook when `parse_mode is None`, coercing explicit `None` → `"MarkdownV2"`. This was a deviation from the pre-sprint contract.

**Iter-3 fix:** The hook is deleted. Telegram's `queue_send_message` (line 227-244) and `queue_edit_message` (line 246-261) now have `parse_mode: str | None = "MarkdownV2"` as Python signature defaults, matching the pre-sprint baseline byte-for-byte. They delegate to `super().queue_send_message(...)` / `super().queue_edit_message(...)` with the resolved value.

**Behavior matrix verified:**

| Caller action | Telegram default | Value reaching base | Value on wire | Matches pre-sprint? |
|---|---|---|---|---|
| Omit parse_mode | `"MarkdownV2"` (signature default) | `"MarkdownV2"` | `"MarkdownV2"` | Yes |
| `parse_mode=None` | Overridden by caller | `None` | `None` | Yes |
| `parse_mode="HTML"` | Overridden by caller | `"HTML"` | `"HTML"` | Yes |

The parametrized wire-level tests confirm both the omitted case (`parse_mode_kwargs={}` → `expected_parse_mode="MarkdownV2"`) and the explicit-None case (`parse_mode_kwargs={"parse_mode": None}` → `expected_parse_mode=None`).

### LOW-1 (iter-2): "tests do not assert at the wire level" — RESOLVED

**Iter-2 state:** Tests drove through `platform.outbound.queue_send_message(...)` and asserted on `mock_bot.send_message`. The assertion checked the base-layer post-hook value, not the wire kwargs assembled by `TelegramMessenger.send_message` / `_do_send`.

**Iter-3 fix:** The `telegram_messenger_with_real_limiter` fixture constructs a real `TelegramMessenger(get_application=lambda: application, limiter=limiter)` with an `AsyncMock` bot. Tests call `messenger.queue_send_message(...)` — the actual Telegram override — which flows through:
1. `TelegramMessenger.queue_send_message(parse_mode="MarkdownV2")` (signature default resolved)
2. → `super().queue_send_message(...)` (base outbox enqueue)
3. → outbox calls `self.send_message` (bound to `TelegramMessenger.send_message`)
4. → `send_message` calls `_do_send` which calls `app.bot.send_message(**kwargs)`
5. → `app.bot` is the `AsyncMock` asserted against

The assertion at `bot.send_message.assert_awaited_once_with(... parse_mode=expected_parse_mode)` is a true wire-level assertion — it verifies the exact kwargs that reach the bot's `send_message` call, which is the outbound wire boundary.

### LOW-2 (iter-2): "test helper duplication" — RESOLVED

**Iter-2 state:** `_wire_application()` helper in the send test, and by-hand `_application`/`bot` injection in the edit and retry tests.

**Iter-3 fix:** The `telegram_messenger_with_real_limiter` fixture centralizes all mock-and-inject setup. All three wire-level tests (send, edit, retry) use the same fixture. The `_wire_application` helper is deleted.

## Criterion Justifications (score bands cited)

### C1 = 10 (band: "All 7 checks pass on the evaluator's first run; git status clean of stray artifacts")
All 7 CI gates green: logos, icons, suppressions, ruff-format, ruff-check, ty, pytest (3147 passed). The 1 pre-existing flaky codex test (`test_generated_catalog_schema_is_accepted_by_installed_codex`) passes on re-run. Coverage 91%. Git status junk is the pre-existing Sprint-8 baseline, untouched by this commit.

### C2 = 10 (band: "Full suite green; coverage ≥80% and ≥baseline; protocol/env/payload/CLI/retry/wording diff audit clean; no user-visible string changed")
Full suite green (3147 passed, +2 from iter-2 due to parametrize expansion). Coverage 91% ≥ 80% and ≥ baseline. Protocol audit clean: no wire payload changes, no env var alias changes, no admin payload changes, no CLI exit code changes, no retry budget changes. Only docstring changes ("Queue a Telegram send with MarkdownV2 as the default parse mode") — no user-facing string changed. Queue method signatures restored to byte-for-byte pre-sprint contract. Wire-level tests prove both omitted and explicit-None cases match pre-sprint behavior.

### C3 = 10 (band: "All in-scope violations resolved; all grep gates at 0; zero new violations")
All Sprint 5-6 principles satisfied: single queued-messenger implementation, platform-specific behavior preserved via subclass defaults (no behavior flattening). `_default_parse_mode` hook → 0 hits. Boundary contract tests: 21/21 passed. Zero new violations. The subclass-override pattern (`TelegramMessenger.queue_send_message(parse_mode="MarkdownV2")` → `super()`) is actually a cleaner expression of "platform-specific behavior preserved" than the hook was — the default lives at the only layer that needs it, with no indirection.

### C4 = 8 (neutral sprint, improved from iter-2's 7)
The `_default_parse_mode` hook is deleted entirely (base definition + Telegram override) with zero residual references. The `_wire_application` helper is deleted. All five dead retry hooks remain absent. One point above neutral for removing code cleanly in direct response to feedback without introducing new junk.

### C5 = 10 (band: "All checks pass; moved code is cleaner than it was")
- `base_messenger.py`: 112 lines (down from 120), all functions <50 lines
- `telegram_io.py`: 261 lines (up from 229 due to queue method overrides), still <800, all functions <50 lines
- `test_telegram.py`: 415 lines, well-structured, fixture consolidation eliminated duplication
- Zero suppressions, no mutation, no magic numbers in production code
- Platform-agnostic naming: no platform-specific identifiers in shared code
- Cleaner than iter-2: the subclass-override pattern is more idiomatic and discoverable than the hook indirection

## Issues

### CRITICAL
None.

### HIGH
None.

### MEDIUM
None.

### LOW
None.

## Positive Findings (do not churn these)

- **The subclass-override pattern is the correct fix.** By putting `parse_mode: str | None = "MarkdownV2"` on Telegram's queue methods and delegating to `super()`, the default lives at the only layer that needs it, with no indirection. This is cleaner than the hook and matches the pre-sprint baseline byte-for-byte.
- **Wire-level tests are now genuine.** The fixture constructs a real `TelegramMessenger` bound to an `AsyncMock` bot, and assertions check the exact kwargs at `bot.send_message` / `bot.edit_message_text` — the outbound wire boundary.
- **Both parse_mode cases are parametrized and deterministic.** The omitted case (`{}` → `"MarkdownV2"`) and the explicit-None case (`{"parse_mode": None}` → `None`) are distinct parametrize cases. Each test runs through a real limiter with deterministic lifecycle (start → yield → shutdown).
- **The retry regression test is preserved and improved.** Now drives through the real `TelegramMessenger` via the shared fixture instead of the old `TelegramRuntime` outbox. Still proves single retry stack: 2 NetworkErrors + 1 success = exactly 3 `bot.send_message` calls and 2 `asyncio.sleep` calls.
- **Outbox wiring remains byte-identical to pre-sprint.** `PlatformOutbox(send=self.send_message, edit=self.edit_message, delete_many=self.delete_messages)` — verified against `08d59425`.
- **Scope discipline is exact.** 3 files, no version bump, no ARCHITECTURE.md churn, no test edits outside the sprint. The diff is net +24 lines (97 insertions, 73 deletions).
- **The suite grew by exactly 2 test cases** (3145 → 3147, the +2 are the parametrize expansion from 2 tests to 4 cases). No churn elsewhere.

## What Improved Since Iteration 2
- MEDIUM (explicit-None coercion) resolved: Telegram queue methods restored to pre-sprint signature defaults, explicit None flows through untouched.
- LOW-1 (tests not at wire level) resolved: tests now drive through real `TelegramMessenger` and assert at `bot.send_message` / `bot.edit_message_text`.
- LOW-2 (test helper duplication) resolved: `_wire_application` deleted, all wire tests use shared `telegram_messenger_with_real_limiter` fixture.
- The hook indirection (`_default_parse_mode`) is gone — replaced by straightforward subclass overrides that are more idiomatic and discoverable.

## What Regressed Since Iteration 2
- None.

## Recommendation

**Proceed to Sprint 6.** Both iter-2 findings are resolved. All 7 CI gates green. Coverage 91%. Wire-level tests prove the pre-sprint contract is restored. No remaining issues of any severity.