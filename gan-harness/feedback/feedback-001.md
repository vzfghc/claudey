# Generator Feedback — Iteration 1 → 2

> Source: direct user design review (authoritative — supersedes the automated evaluator for this round).
> Iteration 1 (commit be937799) is the base; apply these changes on top.

## 1. Active nav pill: rounded, borderless, lighter text

- The active pill (`nav-pill-active`) currently has `border: 1px solid var(--accent-border)` — **remove the border line entirely** (border: none / border-color: transparent).
- Make it **fully rounded** (pill shape — e.g. `border-radius: 999px` or a radius that visually reads as a rounded pill, matching the nav item's rounded look but softer).
- **Reduce text weight** of nav labels (`.nav-label`): lighter font-weight (e.g. 450→400 or a `font-weight` below the current value) — both idle and active states should feel lighter than the current implementation.

## 2. Sidebar: hover-to-expand, collapse on cursor leave (keep the JS tween)

- Change the trigger from click-toggle to **hover**: when the cursor enters the sidebar (especially from the collapsed 64px rail), the sidebar **expands with the existing JS tween** (per-frame inline width, easeOutQuint, ~220ms); when the cursor leaves the sidebar, it **collapses back with the tween** (~350ms).
- Keep the existing tween machinery (inline width/padding, `--sidebar-w`, label fade, `body.sidebar-rail`) — only the trigger changes.
- Keep the `#sidebarToggle` click as a **pin/unpin override** (clicking pins the sidebar open so it doesn't collapse on cursor leave; clicking again unpins). Update `aria-expanded`/`aria-controls`/title semantics accordingly (aria-expanded should reflect the visually expanded state; title/aria-label can describe the pin action).
- Edge cases: rapid hover in/out mid-tween → cancel and reverse from current width (existing behavior); cursor leaves during expand → collapse from current width; reduced motion → instant jump, no tween; mobile (<901px) → unchanged (no hover behavior; existing mobile nav collapse works).
- When pinned, hovering other nav areas must not fight the pin; when unpinned, hover-out always collapses.

## 3. Buttons: revert lift-and-press; heat style ONLY on .card-configure hover

- **Revert** the lift-and-press treatment (layered shadows, sheen `::before`, `scale(0.995)` press, shadow-lift hover) from `.primary-button` and `.secondary-button` back to their **pre-animation styles** (the original flat design from before iteration 1; check git history `be937799^` for the original `.primary-button`/`.secondary-button` rules and restore them).
- Do NOT add the sheen/overlay to primary/secondary.
- Apply the heat "configure" style **only to the `.card-configure` button ("Configure") on hover** — exact CSS the user specified:
  ```css
  background: #ff4c00;
  box-shadow: inset 0 -6px 12px #f003, 0 2px 4px #ff4d001f, 0 1px 1px #ff4d001f, 0 .5px .5px #ff4d0029, 0 .25px .25px #ff4d0033;
  ```
  (User note: "the color is gradient" — the layered box-shadow stack creates the heat gradient feel; keep the transition smooth, ~0.2s.)
- Ghost/test/other buttons stay flat — no shadows anywhere else.

## 4. Replace the logo marquee with the firecrawl "User → Firecrawl → Index" flow diagram

Remove the marquee strip added in iteration 1. Instead, at the top of `#view-providers` (same location), build the mechanism firecrawl uses in its "Live web data" section ("A complete index, search and scrape..."):

**Structure** (measured from live firecrawl.dev):
- A horizontal flex row, centered, max-width ~704px, vertically centered (column-stacked on narrow widths).
- **Three node cards** in order: **User → Firecrawl → Index**. Each card: `border-radius: 16px`, 1px faint border (`before:inside-border` style — inset border), padding 8px, inner surface ~96×96px node with corner dots (4 small dots at corners), a faint center grid line cross, and a centered node visual:
  - **User node**: avatar image in a circle; a **spinning heat-orange loading arc** (SVG arc path ~270°, `stroke: var(--heat-100)`-equivalent `#FA5D19`, `animate-spin` 1s linear infinite) overlaying/rotating around the avatar.
  - **Firecrawl node**: center logo/icon (use the Claudey brand mark or firecrawl-style logo — adapt to the Claudey admin; a circle with the brand svg) + similar spinning arc.
  - **Index node**: an index/database-style icon with a spinning arc.
- **Connectors between cards**: each gap contains a `flex-1` connector column with animated elements — small spinning rings/arcs (e.g. `spin 1s` heat arc + `spin-reverse` orbit) plus a connecting line/arrow SVG between the cards.
- Cards keep the subtle drop shadow from firecrawl (`rgba(0,0,0,0.02-0.03)` layered) and `position: relative; z-index` so arcs overlay cleanly.
- Labels: the firecrawl section labels the cards "User", "Firecrawl", "Index" — for the Claudey admin, adapt to the claudey context (e.g. "You" / "Claudey" / "Providers & models" — use tasteful short labels under or inside each card, monospace small caps like the existing section labels).
- Motion gating: spinning arcs/connectors run only when `prefers-reduced-motion` is not set (consistent with the rest of the module); static otherwise. `aria-hidden` on the decorative diagram; an accessible caption ("Data flows through your Claudey server to your providers" or similar) as the only accessible text.
- Remove the now-unused marquee CSS/JS and the marquee markup; keep the `logos/` directory untouched.

## Constraints (unchanged from spec)
- Keep all existing ids/classes/aria. No new libraries/CDN. Vanilla CSS/JS.
- Files stay cohesive; new rules belong in `admin-animations.css` / `admin-animations.js`; surgical edits only to `admin.css`/`admin.js`.
- CI green (`./scripts/ci.sh`), static tests still pass, semver stays 5.10.0 (already bumped in iteration 1) — if more commits land on main, keep version consistent and `uv lock` in sync.
- Conventional commit message for this round (e.g. `fix: admin nav/button/marquee per design review (v5.10.0)` or similar).
