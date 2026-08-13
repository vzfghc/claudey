# Generator State — Sprint 5 (messaging dedup I: inbound glue + queued messenger)

> Track: refactor foundation sprints (docs/plans/refactor/REFACTOR_PLAN.md §201).
> Branch: `feat/phase-a-free-providers`.
> Status: Sprint 5 complete — full CI gate green (3142 passed, 73 skipped).

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
  `delete_messages`. Retry hooks: `_send_via_retry` / `_edit_via_retry` /
  `_delete_via_retry` (identity by default) + `_delete_many_fallback` (per-message
  loop by default).
- `discord_io.py` 167→105 L and `telegram_io.py` 287→256 L now subclass
  `QueuedMessenger` and keep only platform primitives.
- **Telegram delta verified as genuine** (the plan's ~120-line check): the delta
  is `_with_retry` (network retry ×3 with 2^attempt backoff, RetryAfter
  timedelta/float sleep, "Message is not modified" / known-message suppression,
  parse-mode-drop retry) + batched bulk delete with per-chunk fallback —
  Telegram-specific SDK behavior. Exposed via the base's hooks, NOT flattened.

## What Changed This Iteration

- M1a: duplicated log-preview block in both inbound modules → one shared helper.
- Cluster A: duplicated 10-method queue-and-flush surface → `QueuedMessenger` base.
- No wire-visible behavior change: log strings byte-identical, queue methods
  signature-identical, defaults (MarkdownV2 / fire_and_forget) unchanged, retry
  budgets unchanged, ordering/coalescing preserved (tests green).

## Known Issues

- None.

## Dev Server

- URL: n/a (Python package refactor sprint; no dev server).
- Status: CI gate green.
- Command: `uv run pytest`, `uv run ty check`, `uv run ruff format --check .`
