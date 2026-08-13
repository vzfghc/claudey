# Generator State — Sprint 5 (messaging dedup I: inbound glue + queued messenger)

> Track: refactor foundation sprints (docs/plans/refactor/REFACTOR_PLAN.md §201).
> Branch: `feat/phase-a-free-providers`.
> Status: Sprint 5 iteration 2 complete — full CI gate green (3145 passed, 73 skipped).

## What Was Built

- **M1a — inbound glue.** New `src/claudey/messaging/platforms/inbound_utils.py`
  with the single `log_incoming_text_message` implementation of the raw-content
  log-preview block (log lines byte-identical, `platform_label` parameterized).
  Uses list accumulation (`"".join([raw_content[:80], "..."])[:80]`), no `+=`.
  Both `telegram_inbound.py` and `discord_inbound.py` consume it; the parallel
  `VoiceNoteRequest` construction was already distinct per platform (telegram:
  `status_parse_mode="MarkdownV2"`, `temp_suffix` from voice metadata; discord:
  `status_parse_mode=None`, `temp_suffix` from attachment filename/metadata) —
  kept as-is.
- **Cluster B decision — NOT folded.** `_download_to` / `_reply_text` are
  structurally parallel but differ per platform in the primitive and its
  arguments (telegram: `context.bot.get_file(...).download_to_drive(custom_path)`,
  `message.reply_text`; discord: `attachment.save(str(tmp_path))`,
  `message.reply`). Abstracting them would force a 1-arg closure thunk with no
  platform-neutral name — real churn, zero dedup value. Left in place (matches
  the plan's "otherwise leave them and note why").
- **Cluster A — QueuedMessenger base.** New `src/claudey/messaging/platforms/base_messenger.py`:
  `QueuedMessenger(ABC)` owns `_outbox = PlatformOutbox(...)` (send/edit/delete-many
  wiring) plus `queue_send_message`, `queue_edit_message`, `queue_delete_messages`,
  `fire_and_forget`, `close`, `__init__` — the shared 10-method interface.
  Abstract primitives: `send_message`, `edit_message`, `delete_message`,
  `delete_messages`.
- `discord_io.py` 167→105 L and `telegram_io.py` 287→230 L now subclass
  `QueuedMessenger` and keep only platform primitives.

## What Changed This Iteration (iteration 2 — evaluator feedback 5-001)

- **HIGH-1 fixed — Telegram queued `parse_mode` restored.** Base
  `QueuedMessenger._default_parse_mode()` returns `None`; `TelegramMessenger`
  overrides it to return `"MarkdownV2"`. `queue_send_message`/`queue_edit_message`
  apply the hook when `parse_mode` is omitted, so `turn_intake.py:96` and
  `commands.py:18,77,152` send MarkdownV2 again (no literal `*...*` on the wire).
  Explicitly-passed parse modes still pass through untouched (e.g.
  `node_runner.py`/`workflow.py`/`ui_updates.py` via `_get_parse_mode()`).
- **HIGH-2 fixed — single retry stack.** Outbox wired directly to the platform
  primitives (`PlatformOutbox(send=self.send_message, edit=self.edit_message,
  delete_many=self.delete_messages)`), exactly as the pre-sprint subclasses did.
  Removed `_send_via_retry` / `_edit_via_retry` / `_delete_via_retry` /
  `_delete_many_queued` from the base and `_send_via_retry` / `_edit_via_retry` /
  `_delete_via_retry` / `_delete_many_fallback` from Telegram. Telegram's
  `_with_retry` now lives only inside its own `send_message`/`edit_message`/
  `delete_message`/`delete_messages` primitives — queued sends are retried
  exactly 3 attempts with 2^attempt backoff, matching pre-sprint.
- **Regression tests added** to `tests/messaging/test_telegram.py` (3 new):
  - `test_telegram_queued_send_uses_markdown_v2_default` — real
    `TelegramMessenger` + real `PlatformOutbox` + real started
    `MessagingRateLimiter`; asserts `parse_mode="MarkdownV2"` reaches
    `bot.send_message` on a queued send.
  - `test_telegram_queued_edit_uses_markdown_v2_default` — same for
    `bot.edit_message_text`.
  - `test_telegram_queued_send_retries_once_per_primitive` — two transient
    `NetworkError`s then success → `bot.send_message` called exactly 3 times
    and `asyncio.sleep` exactly 2 times (one retry stack, not ~9).
  New fixture `telegram_platform_with_real_limiter` (started real limiter,
  shut down in teardown).

## Known Issues

- None in sprint scope. One pre-existing flaky environmental test
  (`tests/cli/test_codex_model_catalog.py::..._accepted_by_installed_codex`
  spawns the real `/opt/homebrew/bin/codex` binary with a 10s subprocess
  timeout) intermittently times out; passes on re-run, unaffected by this
  sprint's changes.

## Dev Server

- URL: n/a (Python package refactor sprint; no dev server).
- Status: CI gate green.
- Command: `uv run pytest`, `uv run ty check`, `uv run ruff format --check .`
