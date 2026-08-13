# Generator State — Sprint 7 (literals, naming, provider split)

> Track: refactor foundation sprints (docs/plans/refactor/REFACTOR_PLAN.md §236).
> Branch: `feat/phase-a-free-providers`.
> Status: Sprint 7 complete — full gate green (3169 passed, 73 skipped).

## What Was Built

- Added `NIM_WHISPER_DEVICE` and the zero-import `LOCAL_PROVIDER_PATHS` map to
  `config/constants.py`; admin local-status now derives both env names and paths
  from that map.
- Renamed internal filesystem constants from `HANS_*` to `CLAUDEY_*`, preserving
  all values and user-facing environment aliases.
- Extracted the private OpenAI-compatible stream runner into
  `providers/openai_chat/streaming.py`; `provider.py` is now 294 lines while its
  public `OpenAIChatProvider` surface is unchanged.
- Updated private-runner and trace-event test imports to their new owning module.

## Justified Deviations

- L1 was skipped: merging custom-provider and provider failure classifiers risks
  changing frozen user-visible wording without a trivial shared owner.
- M3 remains resolved as planned: `NimSettings` stays in `config/nim.py` to avoid
  a forbidden config-to-providers dependency.

## Verification

- `uv run ruff format` and `uv run ruff check --fix` passed.
- `uv run ty check` passed.
- `uv run pytest -q` passed: 3169 passed, 73 skipped.
- Sprint grep gates passed: no old internal HANS constants; no non-declaration
  NVIDIA NIM code literals; `provider.py` remains below 800 lines.
