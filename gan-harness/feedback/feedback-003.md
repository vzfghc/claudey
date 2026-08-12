# Evaluation — Iteration 003

## Scores

| Criterion | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Design Quality | 7/10 | 0.3 | 2.1 |
| Originality | 7/10 | 0.2 | 1.4 |
| Craft | 5/10 | 0.3 | 1.5 |
| Functionality | 3/10 | 0.2 | 0.6 |
| **TOTAL** | | | **5.6/10** |

## Verdict: FAIL (threshold: 7.0)

## Hard Gate Results

- [FAIL] All four views render **real content** — Model Config and Messaging are stuck on permanent "Syncing" skeleton. (Blocking — see Critical Issues #1.)
- [PASS] React admin serves at /admin with `id="root"` and JS asset loads (200).
- [PASS] No broken assets (JS, CSS, logos all resolve 200).
- [PASS] Zero React console errors (only favicon 404, non-blocking).
- [PASS] Design-system: heat `#ff4d00` used as accent; no Apple Blue or Firecrawl `#fa5d19` found; body 17px; no weight 500 in components examined.
- [PASS] Sidebar and UsageHero preserved (not redesigned).
- [PASS] Providers view loads real data (37 providers, status badges, combos empty state).
- [PASS] Usage view loads real data (hero, provider breakdown, heatmap, daily table all render).

## Critical Issues (must fix)

### 1. useConfigForm never calls load() on mount — Model Config + Messaging stuck on "Syncing"
- **Evidence**: Playwright snapshot at `#model_config` shows: heading "Syncing" / "Pulling the latest state from the server." Same for `#messaging`. `#providers` and `#usage` both load correctly (they use `useJson` hook, not `useConfigForm`).
- **Root cause**: `src/claudey/api/admin_static/admin-ui/src/hooks/use-config-form.ts` defines a `load()` function that calls `fetchConfig()` and sets `isLoading(false)` in its `finally` block, but **never invokes `load()` on mount**. The `isLoading` state starts `true` and stays there forever.
- **How to fix**: Add `useEffect(() => { void load(); }, [load])` to the hook body. Also import `useEffect` from react.

### 2. UsageTrendChart passes raw hex to tremor colors prop — area chart fill invisible
- **Evidence**: `src/claudey/api/admin_static/admin-ui/src/components/app/usage/usage-trend-chart.tsx` line 41: `colors={["#ff4d00"]}`. The rendered SVG has `<path fill="url(#ff4d00)">` but no matching `<defs>` gradient with that id — tremor's `colors` prop expects a **palette color name** (e.g. `"orange"`), not a raw hex string.
- **Screenshot**: `usage-full.png` shows the chart area; the fill is invisible/transparent. Only the axes grid lines are visible.
- **How to fix**: Change `colors={["#ff4d00"]}` to use a tremor palette color that maps close to heat. Options: (a) use `"orange"` (closest built-in), (b) inject a custom tremor color via the Tailwind config, or (c) override the chart fill via CSS/SVG after render. Simplest: use `"orange"` which tremor renders as a warm orange close to `#ff4d00`.

## Major Issues (should fix)

### 3. Usage chart y-axis labels have awkward spacing
- **Evidence**: The y-axis values "0", "35.0M", "70.0M", "140.0M" are present but the spacing between "70.0M" and "140.0M" is double the earlier spacing (missing the "105.0M" tick). This is a tremor auto-tick issue.
- **How to fix**: Pass explicit `tickValues` or `minValue`/`maxValue` to `AreaChart` to get evenly spaced ticks.

### 4. Empty combos state could be more helpful
- **Evidence**: The empty combos card shows instructional text but the "Add Combo" button is at the section header, not in the card. Minor UX: move the action into the empty card.
- **How to fix**: In `providers-view.tsx`, add the "Add Combo" button inside the empty-state card content so the user sees the CTA where they're looking.

## Minor Issues (nice to fix)

### 5. Sidebar active nav link doesn't follow hash navigation
- **Evidence**: Navigating via URL hash (`#model_config`, `#messaging`) renders the correct view but the sidebar's active link stays on the previously-active item (Usage, the initial page). The sidebar nav doesn't sync with hash changes on initial load from a hash URL.
- **How to fix**: In the sidebar component, read `window.location.hash` on mount and activate the matching nav link.

### 6. Console favicon 404
- **Evidence**: `/favicon.ico` returns 404. Non-blocking but noisy.
- **How to fix**: Add a `<link rel="icon">` to the React entry HTML, or serve a favicon from the backend.

## Screenshots Captured
- `usage-full.png` — Full usage view at 1440px. Hero + ProviderBreakdown + trend chart (invisible fill) + DailyTable visible. Trend chart shows grid lines and x/y axes but the area fill is missing (confirmed by SVG analysis: `fill=url(#ff4d00)` with no matching gradient definition).
- Playwright snapshots confirm: Model Config = "Syncing" skeleton, Messaging = "Syncing" skeleton, Providers = full 37-provider grid, Usage = full data with broken chart fill.