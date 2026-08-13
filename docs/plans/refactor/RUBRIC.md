# Evaluation Rubric — claudey Phase-A Refactor (GAN code-only eval mode)

Branch: `feat/phase-a-free-providers` · Date: 2026-08-13 · Consumes: `docs/plans/refactor/REFACTOR_PLAN.md`, sprint reports, feedback history

This rubric scores **code output only** (the generator's per-sprint diff). The evaluator verifies everything itself — it never trusts the generator's report and never edits code.

---

## 1. Scoring Model

Five weighted criteria, each scored **1-10** (integer). Total = weighted sum, max 10.0.

| # | Criterion | Weight |
|---|---|---|
| C1 | CI gate green | 0.30 |
| C2 | Behavior preservation | 0.25 |
| C3 | Principle adherence | 0.20 |
| C4 | Dead-code & hygiene | 0.10 |
| C5 | Code health | 0.15 |

Formula: `Total = 0.30*C1 + 0.25*C2 + 0.20*C3 + 0.10*C4 + 0.15*C5`

**Pass threshold: 7.0.** Total < 7.0 → another generator-evaluator iteration (max 5 per sprint). Plateau rule: 2 consecutive iterations without any score gain → escalate to the orchestrator.

---

## 2. Criterion C1 — CI gate green (weight 0.30)

The evaluator runs `./scripts/ci.sh` from a clean tree on the sprint's branch state. All 7 checks must pass: **logos, icons, suppressions, ruff-format, ruff-check, ty, pytest**.

| Score | Condition |
|---|---|
| 10 | All 7 checks pass on the evaluator's first run; `git status` clean of stray artifacts. |
| 8-9 | All 7 checks pass, but only after the evaluator re-runs once because the generator's own verification output was misreported (e.g. report claimed green, first evaluator run caught a ruff-format drift). |
| 5-7 | pytest green; one non-pytest check (logos/icons/suppressions/ty) initially failed and required a code fix. |
| 2-4 | pytest failures within the sprint's own scope (import-site misses, moved-symbol stragglers). |
| 0-1 | `uv run pytest tests/contracts/test_import_boundaries.py -n0` is red at the end of **Sprint 0** (hard fail for the foundation sprint regardless of other scores); or multiple checks red. |

Notes: the local `ci.sh` repairs formatting/lint (`ruff format`, `ruff check --fix`); the evaluator must reset those files with `git checkout -- <paths>` and re-run `ruff format --check` / `ruff check` to confirm the committed state is clean (GitHub CI runs check-only). For admin-ui changes, additionally require `npm run typecheck` green.

---

## 3. Criterion C2 — Behavior preservation (weight 0.25)

Zero user-visible change per §10 of the plan. The evaluator verifies:

1. **Full pytest suite green** (`uv run pytest -v --tb=short`, ~195 files) — with the 2 boundary tests fixed.
2. **Coverage gate**: `uv run pytest --cov=claudey --cov-report=term-missing -q`, parse the final `Total` line. Requirements: ≥ **80%** and **not below the Sprint-0 baseline** (baseline recorded in the Sprint 0 report). Below 80% or below baseline → C2 is capped at **5** regardless of other evidence.
3. **Diff-based protocol audit** (evaluator reads the sprint diff): no changes to wire payload shapes or SSE event semantics, env var aliases (in `config/settings.py` and `.env.example`), admin API response payloads, CLI entry points/exit codes (127/126/1), provider retry budgets (`admission.py:27-31`, `stream_recovery.py:15-16`), or user-facing failure wording (`failure_policy.py:32-39`).
4. **User-visible string audit**: diff must not alter any string that reaches a user (wording constants, doctor output, error messages) unless the plan sanctions it (it does not).

| Score | Condition |
|---|---|
| 10 | Full suite green; coverage ≥80% and ≥baseline; protocol/env/payload/CLI/retry/wording diff audit clean; no user-visible string changed. |
| 8-9 | All of the above, plus a cosmetic deviation the generator self-corrected within the iteration (e.g. a comment/docstring string changed and restored after feedback). |
| 5-7 | A user-visible string or constant changed accidentally (e.g. a retry-adjacent constant, a help-text word) — flagged with file:line in feedback, fixed in a later iteration. Coverage at baseline but below 80% caps at 5. |
| 2-4 | Contract tests red (`test_architecture_contracts`, `test_stream_contracts`, execution-failure phase tests, retry-matrix tests) or fixtures/golden files changed without sanction. |
| 0-1 | Wire payload, env var alias, admin payload shape, CLI exit code, or retry budget changed. |

---

## 4. Criterion C3 — Principle adherence (weight 0.20)

Measured against the assessment's violation inventory and CLAUDE.md's architecture principles:

- **Sprint 0**: C1/C2/C3 resolved — zero `config→providers`, zero `application→providers` edges; the `config: {"core"}` amendment is documented in the test itself; boundary file 21/21 green.
- **Sprint 1**: zero `providers→application` imports (grep `from claudey.application` in `src/claudey/providers/` → 0 hits); no shim modules left (complete migration: moved symbols have zero importers at the old location).
- **Sprint 2**: one shared SSE parser in `core/anthropic/`; no `+=` string buffers in the flagged loops; consumers keep their event interpretation.
- **Sprint 3**: one retryability classifier; the stream-recovery variant has zero duplicated logic; the pre-merge table test exists and passes.
- **Sprint 4**: `gemini_family` facade-guarded; grep `google_openai` → 0 hits repo-wide (src, tests, smoke, docs); ARCHITECTURE.md link updated.
- **Sprints 5-6**: single implementation of the queued-messenger and the markdown token-walk; platform-specific behavior preserved via hooks (no behavior flattening).
- **Sprint 7**: constants in `config/constants.py`; no `"nvidia_nim"` code literals; `HANS_*` internal identifiers gone; provider split keeps the public API identical; M3 resolution documented (kept in config/ with justification), not silently ignored.
- **Sprint 8**: inventory deletions match the plan; no sanctioned deviations without recorded justification.
- **General**: no new violations anywhere — no new cross-layer edges, no `# type: ignore`, no `from __future__ import annotations`, no `TYPE_CHECKING`, no local imports used to dodge cycles, no per-provider duplicates introduced.

| Score | Condition |
|---|---|
| 10 | All in-scope violations resolved; all grep gates (above) at 0; zero new violations; the two sanctioned contract edits are the only edits to `test_import_boundaries.py`. |
| 8-9 | All resolved; one minor new smell introduced and fixed within the iteration (e.g. a duplicate helper noticed in feedback). |
| 5-7 | One in-scope violation unresolved at iteration end, or a workaround used (shim module, re-export kept where the plan says delete, local import). |
| 2-4 | Multiple violations unresolved; a new cross-layer edge or cycle introduced. |
| 0-1 | Boundary test red, or a violation class from Sprint 0 (config→providers / application→providers) reintroduced. |

---

## 5. Criterion C4 — Dead-code & hygiene (weight 0.10)

Sprint 8 is the primary target; earlier sprints score neutrally (7) unless they add junk.

Verified by the evaluator itself: `git ls-files` (no `beam/`), `git status --porcelain` (no root screenshots, no `.playwright-mcp/`, no `model-config-skeleton.yml`), `.gitignore` contents, `admin_ui_dist` single-build state (exactly one current hashed asset set, committed atomically with source, `?v=` equal to pyproject version), docs structure per plan step 6 (`docs/reference/` created, ARCHITECTURE.md links valid, `frontend-scaffold-plan.md` beam references updated), admin-ui inventory §2 items removed (re-grep each: tabs.tsx, separator.tsx, the 9 client.ts functions, 10 types.ts types, 2 lib/config.ts exports, 5 npm deps, 7 CSS tokens).

| Score | Condition |
|---|---|
| 10 | Every inventory item in scope removed or replaced by a recorded, justified deviation (with grep evidence); junk deleted; beam/ absent; gitignore updated; dist single-build committed; docs structure landed. |
| 8-9 | All deletions done; one documentation gap (e.g. a justification missing from the report). |
| 5-7 | Some items skipped without justification; or root junk still present; or `admin_ui_dist` left in a mixed state (stale hashed assets + new assets uncommitted). |
| 2-4 | beam/ still tracked, or inventory items removed that the plan/existing code still references (over-deletion — verified by failing tests). |
| 0-1 | Junk remains at root AND beam/ remains; or live admin API endpoints were removed alongside their dead client wrappers (endpoints must stay). |

---

## 6. Criterion C5 — Code health (weight 0.15)

Evaluator checks the diff + the files it touches:

1. **No file >800 lines** under `src/claudey/` after splits (`wc -l` over touched modules; `openai_chat/provider.py` must be <800 by end of Sprint 7).
2. **Functions <50 lines** in new/touched code.
3. **Zero suppressions**: `# type: ignore`, `# ty: ignore`, `from __future__ import annotations` (the suppressions CI check enforces this repo-wide).
4. **List accumulation not `+=`** in the flagged loops and any new loop.
5. **Platform-agnostic naming**: no `HANS_*` identifiers in shared code (env-var aliases excepted — they are frozen).
6. **No magic numbers**: named constants for thresholds/delays introduced or reused.
7. **No mutation**: moved dataclasses stay frozen; no in-place mutation added.
8. **Files small and cohesive**: new modules <800 lines, focused.

| Score | Condition |
|---|---|
| 10 | All checks pass; moved code is cleaner than it was (e.g. list-accumulation converted, constants named). |
| 8-9 | All checks pass with one minor nit (a 60-line function, a magic number in a test). |
| 5-7 | A file pushed over 800 lines, or a function >100 lines, or a `+=` string loop left in touched code. |
| 2-4 | New suppression added (type ignore / future annotations), or mutation introduced in a frozen dataclass move. |
| 0-1 | Multiple health violations in the sprint's own diff. |

---

## 7. Coverage Gate (detailed)

- Command: `uv run pytest --cov=claudey --cov-report=term-missing -q` (pytest-cov ≥7.1.0 is a dev dependency; the `-n auto` xdist addopts work with pytest-cov aggregation).
- Thresholds: **≥80% total line coverage**; **no regression below the Sprint-0 baseline**.
- The baseline is recorded in the Sprint 0 report (generator) and re-verified by the evaluator in Sprint 0 feedback.
- Violation: C2 capped at 5 (even if everything else is perfect), and the iteration count toward the plateau rule still applies.

---

## 8. Hard-Fail Conditions (total cannot pass, regardless of other scores)

1. `tests/contracts/test_import_boundaries.py` red at the end of Sprint 0.
2. Any wire protocol change, env-var alias change, admin payload shape change, CLI exit-code change, or retry-budget change in the diff.
3. Coverage <80%.
4. New `# type: ignore` / `# ty: ignore` / `from __future__ import annotations` anywhere in `src/claudey/`.
5. Live admin endpoints removed alongside dead client wrappers (Sprint 8).

---

## 9. Iteration & Feedback Rules

**Per sprint**: max 5 generator-evaluator iterations. Iteration 1 is the evaluator's first scoring of the generator's Sprint N output; feedback files are `docs/plans/refactor/feedback-<sprint>-NNN.md` (NNN = 001..005).

**Plateau rule**: if two consecutive iterations score the same total without gain, the evaluator stops, writes a final feedback file marked `ESCALATE`, and reports to the orchestrator. Do not burn remaining iterations.

**Iteration-1 ruthlessness rule**: a perfect 10 on iteration 1 signals a rubric that is too lenient, not a perfect generator. On iteration 1 the evaluator must actively probe: run adversarial greps (lingering `HANS_` identifiers, `google_openai`, `from claudey.application` in providers/, `from claudey.providers` in config/ and application/, stray `"nvidia_nim"` literals, `beam` references), re-run the boundary test with `-n0`, re-verify every inventory deletion against the current tree, and diff `admin_ui_dist/index.html` `?v=` against `pyproject.toml`. Any finding earns at least one point deduction with file:line evidence. A genuine iteration-1 pass is possible only when the diff is small, clean, and every probe comes back empty — and even then, the evaluator must state which probes were run.

---

## 10. Evaluator Operating Rules

1. **Verify, don't trust**: run `./scripts/ci.sh` (or `--only` subsets per check), `uv run pytest tests/contracts/test_import_boundaries.py -n0`, `uv run pytest --cov=claudey --cov-report=term-missing -q`, `npm run typecheck`, and any adversarial greps on the current tree. Never accept the generator's report as evidence.
2. **Never edit code**: not even formatting. Findings go into the feedback file; the generator fixes them.
3. **Feedback format** — every feedback file contains:
   - Sprint + iteration number, total score, per-criterion scores with the score-band citation.
   - Issues, each with: severity (CRITICAL/HIGH/MEDIUM/LOW), `file:line` evidence (path:line from the current tree), the rubric criterion affected, and a concrete fix directive.
   - Positive findings list (what was done correctly, so the generator doesn't churn it).
   - The exact verification commands run and their outcomes.
4. **Score ruthlessly and specifically**: cite the score band (e.g. "C2 = 8: full suite green, but `failure_policy.py:41` wording constant moved to a new module — restored by iteration 3").
5. **Sprint-specific focus** (per plan §9 mapping): Sprint 0 → C1/C3; Sprint 3 → C2 (retry matrix); Sprints 5-6 → C2 (byte-for-byte); Sprint 8 → C4 + C2 (admin payloads).
6. **Sanctioned deviations**: if the generator skips an inventory item because the Phase-3 redesign adopted it (or M3-style resolution), that is a justified deviation **only with grep evidence in the report** — otherwise it scores against C4.
7. Feedback files accumulate; the generator reads only the latest iteration's file.

---

## 11. Generator Operating Rules (mirror of the contract)

1. At iteration start, read `docs/plans/refactor/feedback-<sprint>-NNN.md` (latest) and `docs/plans/refactor/REFACTOR_PLAN.md` §7 for the sprint scope.
2. Incorporate **all** issues in the latest feedback. Never silently skip: fix, or record an explicit rebuttal with evidence in the sprint report.
3. Follow the per-sprint command order: implement → `uv run ruff format && uv run ruff check --fix` → `uv run ty check` → targeted `uv run pytest` → `uv run pytest tests/contracts/test_import_boundaries.py -n0` → report.
4. Admin-ui sprints: `npm run typecheck` after each batch; build only when dist sync is required; no visual redesign changes.
5. Write `docs/plans/refactor/sprint-report-<sprint>-NNN.md` with files changed, verification outputs, coverage delta, rebuttals, residual risks.

---

## 12. Worked Scoring Example

Sprint 3 diff: merged classifier, table test added, all pinned tests green, `ci.sh` green on first evaluator run, retry budgets untouched, no new suppressions, but the merged function is 90 lines (over the 50-line guideline) — flagged in feedback.
C1=10 (0.30→3.0), C2=9 (0.25→2.25, full suite + coverage ≥80%, one line lost for the size nit? no — size is C5), C2=10 → 2.5, C3=9 (0.20→1.8, resolved but 90-line function noted), C4=7 (neutral sprint → 0.7), C5=6 (0.15→0.9, function >50 lines).
Total = 3.0 + 2.5 + 1.8 + 0.7 + 0.9 = **8.9** → pass; feedback requires splitting the function in the next iteration.
