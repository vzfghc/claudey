# Evaluation — Sprint 5, Iteration 002 (Iter-2 re-score of the messaging dedup)

Branch: `feat/phase-a-free-providers` · Commit: `1d4255bd` · 2026-08-13 · Evaluator-verified, generator report NOT trusted.

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| C1 — CI gate green | 10/10 | 0.30 | 3.00 |
| C2 — Behavior preservation | 8/10 | 0.25 | 2.00 |
| C3 — Principle adherence | 10/10 | 0.20 | 2.00 |
| C4 — Dead-code & hygiene | 7/10 | 0.10 | 0.70 |
| C5 — Code health | 9/10 | 0.15 | 1.35 |
| **TOTAL** | | | **9.05/10** |

## Verdict: PASS (threshold 7.0) — both HIGHs resolved; two report inaccuracies + one frozen-contract nit to correct in Sprint 6

Iter-1 was 7.55 → iter-2 is 9.05. Both HIGH regressions are genuinely fixed and the dead hooks are gone. This is the final Sprint 5 iteration.

## Verification Commands Run (all evaluator-run)

| Command | Outcome |
|---|---|
| `git show 1d4255bd --stat` | 4 files, all in scope: `base_messenger.py` (−96/+8), `telegram_io.py` (−35/+4), `tests/messaging/test_telegram.py` (+109), `gan-harness/generator-state.md` (report) |
| `uv run pytest -q tests/messaging/` | **496 passed** (was 514 in iter-1's combined run; standalone messaging dir green) |
| `uv run pytest tests/contracts/test_import_boundaries.py -n0` | **21/21 passed** |
| `uv run pytest -q` (full suite) | **3145 passed, 73 skipped** — matches the report's count (baseline 3142 + 3) |
| `uv run pytest --cov=claudey --cov-report=term -q` | **TOTAL 19718 stmts / 1861 miss / 91%** — ≥80% and ≥90% Sprint-0 baseline |
| `uv run ruff format --check` / `uv run ruff check` on the 3 changed source/test files | **Clean** (check-only = GitHub CI state) |
| `uv run ty check` on the 3 changed files | **All checks passed** |
| Full read of `base_messenger.py` + `telegram_io.py` post-diff | hook correct, single retry stack, no dead hooks |
| Read the 3 new tests + both new fixtures | see C2 — real-limiter path, but a wire-level assertion shortfall |
| Greps: 5 deleted hook names, `_default_parse_mode`, `queue_send_message`/`queue_edit_message` callers, `from claudey.application` in providers/, suppressions | hooks → 0 hits; `_default_parse_mode` only def + 2 uses + docstring; suppressions → 0 |
| `git status --porcelain` | untracked root junk unchanged from the pre-recorded Sprint-8 baseline; `admin-ui-check.png` deleted (D) |

## Criterion Justifications (score bands cited)

### C1 = 10 (band: "All 7 checks pass on the evaluator's first run; git status clean of stray artifacts")
Messaging suite, full suite, boundary contract, ruff format/check, ty — all green on first run, no `git checkout` repair needed. Coverage 91%. Junk in `git status` is the pre-existing Sprint-8 baseline, untouched by this commit.

### C2 = 8 (band: "All of the above, plus a cosmetic deviation the generator self-corrected within the iteration")
HIGH-1 and HIGH-2 are genuinely resolved (details below). Full suite green, coverage 91% ≥ baseline, wire/retry budgets untouched. Two deductions:
1. **Report inaccuracy (evidence-shortfall, not a code regression)**: the report states the tests assert `parse_mode="MarkdownV2"` reaches `bot.send_message`. They do not — see the test-critique below. The assertion target is the base layer, one hop short of the wire.
2. **The explicit-`parse_mode=None` deviation is a genuine frozen-contract change, not "matches pre-sprint"** (see next section). No caller passes literal None today, so the user-visible surface is not touched, but the claim as stated is wrong and the coercion is a wire-level behavior difference from the pre-sprint code.

### C3 = 10 (band: "All in-scope violations resolved; all grep gates at 0; zero new violations")
The plan's Sprints 5-6 principle — "platform-specific behavior preserved via hooks (no behavior flattening)" — is now satisfied: Telegram's `"MarkdownV2"` lives in `TelegramMessenger._default_parse_mode()`, base returns None, Discord is untouched. The outbox wiring is byte-identical to the pre-sprint `08d59425` subclasses. Zero new violations; boundary 21/21; no cross-layer edges introduced.

### C4 = 7 (neutral sprint — no dead-code work in scope; no junk added)
Diff is exactly sprint-scope (4 files, no out-of-scope edits, no test edits to other files). All five hook names deleted with zero residual references. Neutral score per rubric.

### C5 = 9 (band: "All checks pass with one minor nit")
`base_messenger.py` 120 L, `telegram_io.py` 229 L, both <800 and cleaner than before (base shrank ~64%). Functions all <50 L. Zero suppressions. No magic numbers, no mutation. **Nit:** the new tests define the `_wire_application` helper that performs the platform mock-and-inject, duplicated by hand (a shortened variant) in the edit and retry tests. Low value — a shared fixture would do.

## Issues

### CRITICAL
None.

### HIGH
None — both iter-1 HIGHs are resolved:

1. **HIGH-1 (parse_mode) — RESOLVED.** `base_messenger.py:57-59` adds `_default_parse_mode() -> None`; `telegram_io.py:123-125` overrides it to `"MarkdownV2"`; `base_messenger.py:71-72,91-92` apply it only when `parse_mode is None` at queue entry, so explicitly-passed values pass through untouched. The three affected callers (`turn_intake.py:96`, `commands.py:18,77,152`, `workflow.py:225`) omit parse_mode and are Telegram-only paths — the wire is restored. Explicit-value callers (`node_runner.py:105`, `workflow.py:204,598,690,705`, `ui_updates.py:86`, `turn_intake.py:88,152,201`) are unchanged.
2. **HIGH-2 (double retry stack) — RESOLVED.** `base_messenger.py:20-26` wires `PlatformOutbox(send=self.send_message, edit=self.edit_message, delete_many=self.delete_messages)` — byte-identical to the true pre-sprint wiring at `08d59425` (`telegram_io.py:50-55`). `_send_via_retry`/`_edit_via_retry`/`_delete_via_retry`/`_delete_many_queued`/`_delete_many_fallback` deleted; grep → 0 hits in src/ and tests/. A queued send now runs exactly one `_with_retry` stack (3 attempts, 2^attempt backoff).

### MEDIUM
1. **C2 — the generator's "explicit None" deviation claim is wrong in both its premise and its conclusion.**
   - Premise: the report claims "None IS the Telegram default" and that explicit `None` previously reached the wire as `"MarkdownV2"`. **Verified false.** Pre-sprint `TelegramMessenger.queue_send_message`/`queue_edit_message` had `parse_mode: str | None = "MarkdownV2"` defaults and passed the value down positionally; an explicit `parse_mode=None` flowed through the outbox to `send_message`'s `_do_send` as literal None (`parse_mode=None` on the wire — see `08d59425:telegram_io.py:133-152,237-264` and the outbox `_send` closure).
   - Conclusion: the generator claims the coercion "matches pre-sprint." **Verified false for explicit None.** Post-iter-2, `base_messenger.py:71-72` coerces explicit `None` to `"MarkdownV2"`. For callers that omit parse_mode (the iter-1 HIGH-1 surface) the fix is correct; for callers that pass literal None it is a behavior change on the wire.
   - Why the risk is bounded: today **no caller passes literal None to a queued Telegram send/edit.** Grep of all 14 `queue_send_message`/`queue_edit_message` call sites: `node_runner`/`workflow`/`ui_updates`/`turn_intake` explicit sites pass `self._get_parse_mode()` / `self._parse_mode` (dynamic, never None on Telegram per `profiles.py:42`); `voice_flow.py:176` passes `request.status_parse_mode`, constructed as `"MarkdownV2"` in `telegram_inbound.py:117` and Discord never hits the base coercion. So the user-visible surface is not touched — but the claim "matches pre-sprint" is wrong.
   - **Fix for Sprint 6 (LOW-effort):** either (a) implement the coercion only for the omitted case by giving Telegram's queue methods an explicit `parse_mode: str | None = "MarkdownV2"` default (drop the base hook) — then explicit None flows through untouched exactly as pre-sprint; or (b) keep the hook and correct the report text. (a) is the closer match to the pre-sprint contract and removes the medium. Note this is NOT a freeze-blocker: no caller exercises the literal-None path, so the frozen-invariant table is intact.

### LOW
1. **C2 — the 3 new tests do not assert at the wire level.** They drive a real `MessagingRateLimiter` + real `PlatformOutbox`, but the outbox's `send`/`edit` are bound to the *base's* `send_message`/`edit_message` on a `TelegramRuntime` whose `_application` is a MagicMock. That means: the hook IS exercised (good — the coercion happens in `base_messenger.py:71-72` before the outbox), but the platform-specific `telegram_io.py:123-152` defaulting (where pre-sprint behavior lived) and the `_do_send` kwargs assembly are **not**. The three assertions check the base layer's post-hook value — which, because `send_message`'s own signature default is `"MarkdownV2"`, proves little about the wire. If a future regression moved the default into `_with_retry` or dropped it from `_do_send`, the queue tests would still pass while the wire regressed.
   - **Fix:** construct a real `TelegramMessenger(get_application=lambda: platform._application, limiter=limiter)` in the fixture (or assert on the captured kwargs of a bound primitive — e.g. patch `TelegramMessenger.send_message` with an `AsyncMock` whose `assert_awaited` inspects `parse_mode`) and assert `parse_mode="MarkdownV2"` lands in the actual call kwargs. The same construction also makes the retry-count test a true single-stack proof (it currently counts `mock_bot.send_message` calls, which is valid because the mocked primitive is the retried closure's target — but the wire-path fix makes it unambiguous).
2. **C5 — test helper duplication.** `_wire_application` in the send test and the by-hand `_application`/`bot` injection in the edit and retry tests duplicate the same mock-and-inject. A single fixture parameterized on side effects would be tighter.

## Positive Findings (do not churn these)

- **The `_default_parse_mode` hook is the architecturally correct fix** — it matches the plan's "no behavior flattening" principle exactly and keeps Discord on the base's None without a conditional.
- **Outbox wiring is byte-identical to pre-sprint** (`PlatformOutbox(send=self.send_message, edit=self.edit_message, delete_many=self.delete_messages)`), so the queued-path retry contract is exactly one `_with_retry` stack — verified against `08d59425`.
- **The retry regression test is a genuinely good single-stack proof:** two `NetworkError`s then success → `bot.send_message` exactly 3 times and `asyncio.sleep` exactly 2 times. This is the test the iter-1 feedback asked for, and it would have caught the iter-1 nested-stack bug.
- **The new fixture is deterministic:** real limiter started and shut down in teardown; no timing flakes observed across 3 runs of the messaging dir.
- **Scope discipline is exact:** 4 files, no version bump, no ARCHITECTURE.md churn, no test edits outside the sprint.
- **The suite grew by exactly the 3 new tests** (3142 → 3145) with no churn elsewhere.

## What Improved Since Iteration 1
- HIGH-1 parse_mode regression fixed at the source (hook, not a Telegram-only default smeared across callers).
- HIGH-2 nested retry stacks eliminated; wiring matches pre-sprint.
- All five dead retry hooks removed.
- 3 regression tests added covering the previously-blind queued path.

## What Regressed Since Iteration 1
- None. (The explicit-None coercion is a new deviation, but it is not exercised by any caller and does not regress the iter-1-fixed surface.)

## Specific Suggestions for Next Iteration (Sprint 6)
1. Make the queue regression tests assert on the actual wire kwargs — construct a real `TelegramMessenger` bound to the platform application (or patch the concrete `send_message`/`edit_message`) so `parse_mode="MarkdownV2"` is verified in the outbound call kwargs, not just the base-layer value. This closes the evidence gap the report's overstatement exposed.
2. Decide the explicit-`None` question explicitly: prefer Telegram queue methods with `parse_mode: str | None = "MarkdownV2"` defaults (dropping the base hook) to restore the byte-for-byte pre-sprint contract; or keep the hook and record the deviation with the correct reasoning. Either way, correct the claim "None IS the Telegram default" in the sprint report — it is factually wrong.
3. Re-run the full gate after any Sprint-6 change; the suite must stay ≥ 3145 passed.
