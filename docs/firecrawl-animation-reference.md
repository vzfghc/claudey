# Firecrawl Animation Reference

> Reverse-engineered from live analysis of firecrawl.dev (marketing site + authenticated dashboard + playground).
> Date: 2026-08-05 · Verified via DOM instrumentation, per-frame inline-style sampling, and stylesheet rule extraction.

---

## 1. Stack Overview

- **Framework:** Next.js / React (server-rendered, client-side route transitions)
- **Motion model:** CSS keyframes + CSS transitions + **JS-tweened inline styles** + 2× WebGL2 canvases
- **Libraries:** Sonner (toasts), prismjs (syntax highlight), Lucide (icons)
- **Design tokens:** `--heat-*` (orange #FA5D19), `--accent-black`, `--black-alpha-*`, `--border-*`

---

## 2. Design-System Keyframes (18)

| Keyframe | Selector | Behavior |
|---|---|---|
| `cursor-blink` | `.cursor` | Terminal caret opacity blink |
| `spin` | `.animate-spin`, `.sonner-loading-bar` | 360° rotation |
| `spin-reverse` | `.animate-spin-reverse` | Counter-rotation (orbit pairs) |
| `fade-in-up` | `.animate-fade-in-up` | Opacity 0→1 + translateY(10px)→0 |
| `bounce` | `.animate-bounce` | Eased bounce |
| `ping` | `.animate-ping`, `.hero-scraping-highlight::before` | Scale-to-2 + fade radar pulse |
| `pulse` | `.animate-pulse`, `.motion-safe:animate-pulse` | Opacity 0.5 pulse |
| `snowfall` | `.animate-snowfall` | Falling particles (dormant on home) |
| `ai-chats-chat-shine` | chat demo | background-position shine sweep |
| `ai-chats-realtime-indicator` | chat demo | Scale 0.5→4 + blur live ring |
| `hero-scraping-highlight-before` | hero scrape card | Border-color pulse |
| `swipe-out-left/right/up/down` | Sonner toasts | 4-direction swipe-to-dismiss |
| `sonner-fade-in` / `sonner-fade-out` | toasts | Scale 0.8↔1 enter/exit |
| `sonner-spin` | toast loading icon | Opacity fade spinner |

**Reduced-motion:** `spin`/`pulse` gated behind `(prefers-reduced-motion: no-preference)`; `motion-safe:` utilities.

---

## 3. Marketing Landing Page

### Continuous / always-on
- **2× WebGL2 canvases** (rAF-driven): hero `2628×1012` + "open-source" banner `2224×408` (y≈11603)
- **Orbit rings** — `spin 32s` + `spin-reverse 32s` concentric pairs behind hero title
- **Chat realtime indicator** — `3s infinite` scale/blur ring
- **Pulse cursor** — `0.5s` accent block in terminal
- **Logo marquee** — **JS-driven** translateX (~32px/s): 2 mirrored tracks × 16 logos in the *People love building with Firecrawl* section (y≈10951)
- Measured ~13,600 rAF callbacks / 6s ≈ 38 concurrent 60fps loops

### Section map
| Section | Animations |
|---|---|
| Announcement banner | Hover color shift |
| Hero | WebGL2 bg · orbit rings · terminal badges (`[200 OK] [.JSON] [SCRAPE] [.MD]` fade-in-up) · GitHub ⭐ count-up `161.4K` · scrape-card `ping` border |
| Start scraping today | Rotating SVG cards (JS transform 90/180/270°) · prismjs JSON · typing caret · `[01 / 06]` step carousel |
| Connect with AI agents | Clipped logo grid (80 imgs, `overflow-x-clip`) · MCP/CLI copy buttons |
| Open-source | WebGL2 banner · "Read story" blog cards |
| We handle the hard stuff | Horizontally sliding feature cards (sw/cw 1.39) |
| Transform web data | Feature cards, spotlight-on-hover borders |
| People love building | **JS logo marquee** (2×16) · testimonial avatars |
| FAQ | **27-item accordion**, chevron rotate |
| Footer | Hover transitions |

---

## 4. Dashboard Sidebar — "Why it feels satisfying"

Verified at `/app/t/dkwhALj4VNq`. The `<aside>` is fixed, 256px, `transition-[top,height] 0.2s ease-out`, `z-50`, `bg-background-base`, `border-r border-border-faint`.

### 4.1 JS-tweened width (the core)
- **Collapse:** `256 → 204 → 91 → 67 → 64px` (~350ms, eased)
- **Expand:** `64 → 132 → 234 → 253 → 256px` (~200ms)
- Inline style rewritten **every frame**: `width: 188.451px → 80.6072px → 64.0543px`
- **Not** a CSS transition (`getComputedStyle().transitionProperty` = `top, height`), **not** WAAPI (`getAnimations()` = `[]`), **not** framer-motion — a custom JS tween writes eased width values to the inline style. Full control of the easing curve (snappy start, gentle settle).

### 4.2 Label crossfade + unmount
- Labels fade out as rail shrinks: `opacity 1 → 0.986 → 0.806 → 0.270`
- Then React **unmounts** them once fully collapsed — no clipped text
- Icons pinned at fixed 36px, stay centered (label container `flex-1` shrinks to 0)

### 4.3 Two sliding pills (the glide)
Inside a `relative` nav, **one shared absolute pill** per state translates between items (`transition: all`):

| Pill | Class | Behavior |
|---|---|---|
| Active route | `bg-heat-8 rounded-10` | Orange tint, opacity 1, follows current route (top 72) |
| Hover | `bg-black-alpha-4 rounded-10` | opacity 0 idle → slides to hovered item (`top: 386 → 169`) |

A single gliding indicator reads far more refined than per-item highlights.

### 4.4 Micro-interactions
- **Nav links:** `h-36 w-full rounded-10 transition-all`, `active:scale-…` press-down, `group relative overflow-hidden`
- **Collapse button:** `hover:bg-black-alpha-6`, `active:scale-[0.98]`, chevron crossfades via an `opacity` wrapper
- **Header:** `h-64 border-b` brand row · **Footer:** `px-6 py-6 border-t` (collapse toggle + What's New + user)
- **Mobile:** `< lg` the aside is `display:none` (`hidden lg:flex`) → becomes a slide-in drawer

### 4.5 Recipe
1. JS-tweened width with custom easing (not `transition: width`)
2. Fade-then-unmount labels
3. Icon-rail mode with centered icons
4. One sliding hover pill
5. Press-scale feedback on every row
6. Two-tone pills (orange active / gray hover)

---

## 5. Playground — Tab Switch + Button

Verified at `/app/t/dkwhALj4VNq/playground?endpoint=search`.

### 5.1 Endpoint tab bar (Search / Scrape / Parse / Map / Crawl)

**Structure:** `bg-black-alpha-4 flex items-center rounded-10 p-2 relative` — a **segmented control**.

**Sliding pill:** `absolute top-2 left-2 h-32 bg-surface rounded-8` with inline `box-shadow` (layered elevation) and `transition: all`.

Measured switch (Search → Scrape):
- Pill translates via **transform**: `matrix(0.994, 0, 0, 0.994, 8.29, 0)` → `matrix(1, 0, 0, 1, 96.1, 0)` (left 632 → 728)
- **Subtle scale mid-flight:** matrix scale 0.994 → 0.975 → 1 — the pill slightly shrinks then settles, a "breathing" glide
- **Icon grayscale crossfade:** canvas icons toggle `filter: grayscale(N)`; both interpolate simultaneously (old `0→1`, new `1→0`) for a smooth color swap
- **Text color interpolates** (oklab) during the switch; active `text-accent-black` / inactive `text-black-alpha-56`
- Tab switch is a **client-side route change** (`?endpoint=scrape`), the pill animates across the transition

### 5.2 Primary button ("Start scraping", heat-orange)

**Base `.button`:** `transition: 0.2s, scale 0.1s, box-shadow 0.1s`
**Active `.button:active`:** `transition: 0.2s, scale 50ms, box-shadow 50ms` — press is snappier

**Layered box-shadow (`.button-primary`):**
```
inset 0 -6px 12px rgba(heat-red, 0.2)   ← inner bottom glow
0 2px 4px  rgba(heat, 0.12)             ← ambient drop
0 1px 1px  rgba(heat, 0.12)             ← contact shadow
```

**Hover (0.2s):** shadow **lifts** — `0 2px 4px` → `0 4px 8px`, opacity `0.12 → 0.16` (button appears to rise), plus a spread glow.

**Sheen overlay (`.button-background`):** `opacity: 0.06`, `background: linear-gradient(white → transparent)`, `transition: opacity 0.2s`
- `:hover` → `0.08` (brightens)
- `:active` → `0`, `transition: opacity 50ms` (vanishes on press)

**Press:** `active:[scale:0.995]` → scale 99.5% (50ms) + shadows contract + sheen gone — the button *sinks*.

**Loading crossfade:** the label is wrapped in `transition-all` with inline `opacity: 1; filter: blur(0px)`. On state change (run/loading) the text fades + blurs out (`opacity → 0`, `blur → 4px`) while a spinner crossfades in.

**Scale variants present:** `active:scale-[0.95] / [0.96] / [0.98] / [0.995] / [0.999]` — press depth tuned per button role.

---

## 6. Component Mapping (Magic UI / shadcn)

| Firecrawl effect | Equivalent |
|---|---|
| Orbit rings | Magic UI `orbiting-circles` / orb |
| Logo marquee | Magic UI `marquee` |
| Star count `161.4K` | Magic UI `number-ticker` |
| Chat shine sweep / live indicator | Magic UI `animated-shiny-text`, `shine-border`, realtime indicator |
| Scrape-card border pulse | Magic UI `border-beam` |
| Feature card spotlight hover | Magic UI `magic-card` |
| Toasts + swipe-dismiss | shadcn `sonner` |
| FAQ accordion | shadcn `accordion` |
| Hero WebGL | Magic UI `globe` (concept) |
| Segmented tab pill | shadcn `tabs` + custom sliding pill |
| Lift-and-press button | shadcn `button` + layered shadow + sheen overlay |
| JS-tweened sidebar width | Custom (rAF tween → inline style) |

---

## 7. Key Takeaways for Reimplementation

1. **JS-tweened inline styles** (not CSS transitions) give custom easing on structural widths — used for the sidebar collapse.
2. **Sliding shared pills** (absolute + `transition: all` + transform) for active/hover indicators.
3. **Grayscale-filter crossfade** for icon color swaps between states.
4. **Layered box-shadows** (inset glow + ambient + contact) make buttons feel physical; changing the shadow on hover/press is the whole "tactile" illusion.
5. **Sheen overlay** (`white→transparent` gradient, 6→8% opacity) adds polish cheaply.
6. **Press scale variants** (0.95 → 0.999) tune tactile feedback per element.
7. **Fade-then-unmount** for collapsing content avoids jarring clipping.
8. **Reduced-motion:** `motion-safe:` gates + `prefers-reduced-motion` keyframe variants.
