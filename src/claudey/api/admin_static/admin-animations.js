/* ============================================
   admin-animations.js — firecrawl-style motion layer
   ES module loaded after admin.js. Owns decorative
   motion: the JS-tweened sidebar collapse (hover-peek
   expansion plus click pin/unpin), the sliding nav pills,
   toast swipe-to-dismiss, and the scout activity
   dashboard (typed query, decrypting rows, endless
   marquee, count-up stats). Persistent state, inert, and
   localStorage stay owned by admin.js; this module only
   mirrors the visually expanded state into aria-expanded
   while the cursor hovers the sidebar. All loops are gated
   behind prefers-reduced-motion.
   ============================================ */

/* 0. Guards & constants */
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const DESKTOP = window.matchMedia("(min-width: 901px)");

const SIDEBAR_W = {
  expanded: 256,
  collapsed: 64,
  padExpanded: 20,
  padCollapsed: 12,
  collapseMs: 350,
  expandMs: 220,
};
const LABEL_FADE_END = 120; // px of sidebar width where labels reach opacity 0
const NAV_ITEM_HEIGHT = 40; // px per nav item
const NAV_PITCH = NAV_ITEM_HEIGHT + 6; // 40px item + 6px grid gap
const PILL_GLIDE_MS = 160; // hover-pill glide duration, frame-tweened
const PILL_DIP = 0.07; // mid-glide scale dip — bottoms at 1 - PILL_DIP
const SWIPE_DISMISS_AT = 70; // px of horizontal drag that dismisses a toast
const SWIPE_FADE_OVER = 220; // px of drag that fully fades a toast
const SWIPE_CLICK_AT = 10; // px of drag that suppresses click-to-dismiss
const SWIPE_FLICK_PX = 30; // minimum drag for a velocity-based dismiss
const SWIPE_FLICK_VELOCITY = 1.2; // px per ms that counts as a flick

const SCOUT_QUERY = "claudey latest commits";
const SCOUT_ROW_H = 132; // px per row — must match .scout-row in the CSS
const SCOUT_ROW_MS = 500; // stagger between rows revealed after typing
const SCOUT_SPEED = 16; // px/s marquee speed (firecrawl runs 774px/50s)
const SCOUT_CHAR_MIN = 100; // typing jitter bounds, ms per char
const SCOUT_CHAR_MAX = 200;
const SCOUT_COUNTUP_MS = 75; // stats count-up tick
const SCOUT_ENCRYPT_MS = 100; // row-field decrypt tick
const SCOUT_DOT_MS = 200; // title "..." cycling tick
const SCOUT_RANDOM_CHANCE = 0.4; // decrypt: chance a scrambled char shows real
const SCOUT_FALLBACK_RATE = 18000; // USD→IDR when the endpoint has no rate
const SCOUT_ENCRYPT_CHARS = "a-zA-Z0-9*=?!";

const byId = (id) => document.getElementById(id);

/* 1. Sidebar — JS-tweened width (per-frame inline styles,
      not a CSS transition) with an easeOutQuint curve. */
let sidebarTweenId = null;
let sidebarTweenTarget = null; // direction the running tween heads (null = idle)

/**
 * Ease-out quintic: snappy start, gentle settle.
 * @param {number} t - progress in [0, 1]
 * @returns {number} eased progress in [0, 1]
 */
function easeOutQuint(t) {
  return 1 - Math.pow(1 - t, 5);
}

/**
 * Ease-out quartic — the JS twin of the pills' CSS curve
 * cubic-bezier(0.22, 1, 0.36, 1). Snappy start with a short
 * settle; unlike quint it never crawls at the end.
 * @param {number} t - progress in [0, 1]
 * @returns {number} eased progress in [0, 1]
 */
function easeOutQuart(t) {
  return 1 - Math.pow(1 - t, 4);
}

/** @param {number} width - current sidebar width in px */
function labelOpacityFor(width) {
  const range = SIDEBAR_W.expanded - LABEL_FADE_END;
  return Math.min(1, Math.max(0, (width - LABEL_FADE_END) / range));
}

/** @param {string} opacity - CSS opacity value, or "" to clear */
function setLabelOpacity(opacity) {
  document.querySelectorAll(".nav-label, .brand-text").forEach((label) => {
    label.style.opacity = opacity;
  });
}

/** Clear the per-frame layout inline styles (nav gap/padding-left,
    label widths, brand gap/text width). Label opacity and the
    sidebar's own width/padding are managed separately. */
function clearSidebarLayout() {
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.style.gap = "";
    link.style.paddingLeft = "";
  });
  document.querySelectorAll(".nav-label").forEach((label) => {
    label.style.width = "";
  });
  const brand = document.querySelector(".brand");
  if (brand) {
    brand.style.gap = "";
    const text = brand.querySelector(".brand-text");
    if (text) text.style.width = "";
  }
}

/** Jump straight to a collapsed/expanded state (no tween). */
function snapSidebar(collapsed) {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;
  clearSidebarLayout();
  if (collapsed) {
    sidebar.style.width = `${SIDEBAR_W.collapsed}px`;
    sidebar.style.paddingLeft = `${SIDEBAR_W.padCollapsed}px`;
    sidebar.style.paddingRight = `${SIDEBAR_W.padCollapsed}px`;
    document.documentElement.style.setProperty("--sidebar-w", `${SIDEBAR_W.collapsed}px`);
    setLabelOpacity("0");
    document.body.classList.add("sidebar-rail");
  } else {
    // Keep the final inline width. A hover-peek leaves
    // body.sidebar-collapsed in place (the peek is transient),
    // and that class's CSS width would snap the sidebar back to
    // 64px if the inline width were cleared here.
    sidebar.style.width = `${SIDEBAR_W.expanded}px`;
    sidebar.style.paddingLeft = `${SIDEBAR_W.padExpanded}px`;
    sidebar.style.paddingRight = `${SIDEBAR_W.padExpanded}px`;
    document.documentElement.style.setProperty("--sidebar-w", `${SIDEBAR_W.expanded}px`);
    setLabelOpacity("1");
    document.body.classList.remove("sidebar-rail");
  }
}

/** Tween the sidebar width/padding frame by frame. */
function tweenSidebar(targetCollapsed) {
  // Already heading toward this state — don't restart (hover
  // enter/leave and pin clicks can otherwise fight each other).
  if (sidebarTweenTarget === targetCollapsed && sidebarTweenId !== null) {
    return;
  }
  if (sidebarTweenId !== null) {
    cancelAnimationFrame(sidebarTweenId);
    sidebarTweenId = null;
  }
  sidebarTweenTarget = targetCollapsed;
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;
  const duration = targetCollapsed ? SIDEBAR_W.collapseMs : SIDEBAR_W.expandMs;
  const startW = parseFloat(sidebar.style.width) || SIDEBAR_W.expanded;
  const startPad = parseFloat(sidebar.style.paddingLeft) || SIDEBAR_W.padExpanded;
  const endW = targetCollapsed ? SIDEBAR_W.collapsed : SIDEBAR_W.expanded;
  const endPad = targetCollapsed ? SIDEBAR_W.padCollapsed : SIDEBAR_W.padExpanded;
  // Capture the layout so the icons glide to center as the rail
  // closes — instead of snapping when body.sidebar-rail lands with
  // justify-content: center. scrollWidth reads the natural label
  // width even while the rail has collapsed it to 0.
  const navLinks = Array.from(document.querySelectorAll(".nav-link")).map((link) => {
    const label = link.querySelector(".nav-label");
    return {
      link,
      label,
      labelW: label ? label.scrollWidth : 0,
      startGap: targetCollapsed ? 10 : 0,
      endGap: targetCollapsed ? 0 : 10,
      startPadLeft: targetCollapsed ? 14 : 10,
      endPadLeft: targetCollapsed ? 10 : 14,
    };
  });
  const brand = document.querySelector(".brand");
  const brandText = brand ? brand.querySelector(".brand-text") : null;
  const brandTextW = brandText ? brandText.scrollWidth : 0;
  const startedAt = performance.now();
  if (!targetCollapsed) {
    document.body.classList.remove("sidebar-rail");
  }
  const frame = (now) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    const eased = easeOutQuint(progress);
    const width = startW + (endW - startW) * eased;
    const pad = startPad + (endPad - startPad) * eased;
    sidebar.style.width = `${width}px`;
    sidebar.style.paddingLeft = `${pad}px`;
    sidebar.style.paddingRight = `${pad}px`;
    document.documentElement.style.setProperty("--sidebar-w", `${width}px`);
    setLabelOpacity(String(labelOpacityFor(width)));
    navLinks.forEach(({ link, label, labelW, startGap, endGap, startPadLeft, endPadLeft }) => {
      link.style.gap = `${startGap + (endGap - startGap) * eased}px`;
      link.style.paddingLeft = `${startPadLeft + (endPadLeft - startPadLeft) * eased}px`;
      if (label) {
        label.style.width = `${targetCollapsed ? labelW * (1 - eased) : labelW * eased}px`;
      }
    });
    if (brand) {
      brand.style.gap = `${targetCollapsed ? 12 * (1 - eased) : 12 * eased}px`;
      if (brandText) {
        brandText.style.width = `${targetCollapsed ? brandTextW * (1 - eased) : brandTextW * eased}px`;
      }
    }
    if (progress < 1) {
      sidebarTweenId = requestAnimationFrame(frame);
    } else {
      sidebarTweenId = null;
      sidebarTweenTarget = null;
      clearSidebarLayout();
      if (targetCollapsed) {
        document.body.classList.add("sidebar-rail");
      } else {
        // Keep the final inline width. A hover-peek leaves
        // body.sidebar-collapsed in place (the peek is transient),
        // and that class's CSS width would snap the sidebar back to
        // 64px if the inline width were cleared here.
        sidebar.style.width = `${SIDEBAR_W.expanded}px`;
        sidebar.style.paddingLeft = `${SIDEBAR_W.padExpanded}px`;
        sidebar.style.paddingRight = `${SIDEBAR_W.padExpanded}px`;
        document.documentElement.style.setProperty("--sidebar-w", `${SIDEBAR_W.expanded}px`);
        setLabelOpacity("1");
      }
    }
  };
  sidebarTweenId = requestAnimationFrame(frame);
}

/** Installed as window.__sidebarTweenToggle by admin.js's click hook. */
function onSidebarToggleClick() {
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  const next = !collapsed;
  if (typeof window.applySidebarCollapsed === "function") {
    window.applySidebarCollapsed(next);
  }
  if (REDUCED_MOTION || !DESKTOP.matches) {
    // Mobile collapse is handled by the sidebar-collapsed CSS
    // rules; only desktop needs an explicit snap.
    if (DESKTOP.matches) {
      snapSidebar(next);
    }
    return;
  }
  tweenSidebar(next);
}
window.__sidebarTweenToggle = onSidebarToggleClick;

/* 1b. Sidebar hover-peek — the collapsed rail expands on
      cursor enter and collapses on leave, both with the tween.
      Transient and purely visual: body.sidebar-collapsed,
      localStorage, and inert stay owned by admin.js (the
      toggle click is the pin/unpin override). aria-expanded
      mirrors the visually expanded state while peeking. */
const sidebarEl = document.querySelector(".sidebar");
const sidebarToggleEl = byId("sidebarToggle");

function isSidebarCollapsed() {
  return document.body.classList.contains("sidebar-collapsed");
}

/** Expand/collapse for a peek; instant snap when motion is
    reduced, tween otherwise. */
function peekSidebar(expanded) {
  if (sidebarToggleEl) {
    sidebarToggleEl.setAttribute("aria-expanded", String(expanded));
  }
  if (REDUCED_MOTION || !DESKTOP.matches) {
    snapSidebar(!expanded);
    return;
  }
  tweenSidebar(!expanded);
}

if (sidebarEl) {
  sidebarEl.addEventListener("mouseenter", () => {
    if (!DESKTOP.matches || !isSidebarCollapsed()) return;
    peekSidebar(true);
  });
  sidebarEl.addEventListener("mouseleave", () => {
    if (!DESKTOP.matches || !isSidebarCollapsed()) return;
    // Pinned (class removed) → hover-out must not collapse.
    peekSidebar(false);
  });
}

/* 2. Section nav — one shared active pill + one shared hover
      pill, both absolute and sliding between items. The hover
      pill's position AND scale are JS-tweened per frame (never a
      CSS transition): retargeting mid-glide reads the last
      written frame, so the pill keeps gliding from where it is
      — no keyframe restart, no scale snap, and fast crossings
      never blank it out (it just rides the dip it was in). */
let activePill = null;
let hoverPill = null;

// Hover-pill glide state. pillFromY/pillFromScale are the last
// written frame values — a retarget starts the tween from them.
let pillTweenId = null;
let pillFromY = 0;
let pillFromScale = 1;
let pillTargetIndex = -1;
let pillTargetY = 0;
let pillStart = 0;
let pillY = 0;
let pillScale = 1;

function navLinks() {
  const nav = byId("sectionNav");
  return nav ? Array.from(nav.querySelectorAll(".nav-link")) : [];
}

/** @returns {number} index of the active link, clamped to >= 0 */
function activeNavIndex() {
  return Math.max(0, navLinks().findIndex((link) => link.classList.contains("active")));
}

function positionActivePill() {
  if (!activePill) return;
  activePill.style.transform = `translateY(${activeNavIndex() * NAV_PITCH}px)`;
}

/** Drop the pill onto an item instantly and park the tween there. */
function resetPillTween(index) {
  if (pillTweenId !== null) {
    cancelAnimationFrame(pillTweenId);
    pillTweenId = null;
  }
  pillTargetIndex = index;
  pillTargetY = index * NAV_PITCH;
  pillFromY = pillY = pillTargetY;
  pillFromScale = pillScale = 1;
}

/**
 * Glide the hover pill to another item. If one is already
 * gliding, the tween retargets: it continues from the last
 * written frame instead of restarting, so the scale keeps
 * riding the dip it was in.
 *
 * The no-op guard compares against the LIVE heading, not the
 * last settle: during a glide the settled index is stale, so
 * checking it would swallow a genuine redirect; and re-hovering
 * the current heading must not restart the tween — a restart
 * from a fraction of a pixel off-target makes travel jump to
 * mid-range instantly, re-sinking the pill in place.
 * @param {number} index - target nav item index
 */
function glidePillTo(index) {
  if (!hoverPill || index === pillTargetIndex) return;
  if (REDUCED_MOTION) {
    resetPillTween(index);
    hoverPill.style.transform = `translateY(${pillY}px)`;
    return;
  }
  pillFromY = pillY;
  pillFromScale = Math.min(pillScale, 1); // never inherit a polluted scale
  pillTargetIndex = index;
  pillTargetY = index * NAV_PITCH;
  pillStart = performance.now();
  if (pillTweenId === null) {
    pillTweenId = requestAnimationFrame(tickPillGlide);
  }
}

/**
 * One glide frame: eased translateY plus a sine-shaped scale dip
 * that bottoms mid-travel at 1 - PILL_DIP and returns to 1 as the
 * pill approaches the next item — the Firecrawl "breathing" glide.
 * @param {number} now - rAF timestamp
 */
function tickPillGlide(now) {
  if (!hoverPill) {
    pillTweenId = null;
    return;
  }
  // Clamp at BOTH ends: a retarget can set pillStart to a time
  // newer than this frame's vsync timestamp, so a stale tick can
  // compute negative progress — without the bottom clamp that
  // would write a backward frame with scale > 1 (the bounce).
  const progress = Math.max(0, Math.min(1, (now - pillStart) / PILL_GLIDE_MS));
  const eased = easeOutQuart(progress);
  pillY = pillFromY + (pillTargetY - pillFromY) * eased;
  // The dip is anchored to TRAVEL progress (how far the pill has
  // physically moved toward its target), not to eased time: a
  // retarget restarts the easing, so a time-anchored dip would
  // re-sink the pill even while it is parked on an item — the
  // in-place bounce during fast hovering. Anchored to travel, a
  // retarget near the target barely dips at all, the full dip
  // happens only mid-journey between items, and the pill is
  // always exactly full-size once it arrives. For a from-rest
  // glide travel === eased, so the dip shape is unchanged.
  const span = pillTargetY - pillFromY;
  const travel = span === 0 ? 0 : (pillY - pillFromY) / span;
  pillScale =
    pillFromScale + (1 - pillFromScale) * eased -
    PILL_DIP * Math.sin(travel * Math.PI);
  hoverPill.style.transform = `translateY(${pillY}px) scale(${pillScale.toFixed(4)})`;
  if (progress < 1) {
    pillTweenId = requestAnimationFrame(tickPillGlide);
  } else {
    pillTweenId = null;
    pillFromY = pillY;
    pillFromScale = 1;
  }
}

function buildPills() {
  const nav = byId("sectionNav");
  if (!nav) return;
  nav.querySelectorAll(".nav-pill").forEach((pill) => pill.remove());
  nav.classList.remove("nav-pills-ready");
  activePill = document.createElement("div");
  activePill.className = "nav-pill nav-pill-active";
  activePill.setAttribute("aria-hidden", "true");
  hoverPill = document.createElement("div");
  hoverPill.className = "nav-pill nav-pill-hover";
  hoverPill.setAttribute("aria-hidden", "true");
  // Hover pill last so its tint paints over the active pill.
  nav.append(activePill, hoverPill);
  positionActivePill();
  // Rest the hover pill on the active item until the pointer moves.
  hoverPill.style.transform = `translateY(${activeNavIndex() * NAV_PITCH}px)`;
  resetPillTween(activeNavIndex());
  // Gate the glide: pills must be settled before transitions arm.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      nav.classList.add("nav-pills-ready");
    });
  });
}

function syncPills() {
  const nav = byId("sectionNav");
  if (!nav) return;
  const wantPills = DESKTOP.matches && nav.querySelector(".nav-link") !== null;
  const hasPills = nav.querySelector(".nav-pill") !== null;
  if (wantPills && !hasPills) {
    buildPills();
  } else if (!wantPills && hasPills) {
    activePill = null;
    hoverPill = null;
    nav.querySelectorAll(".nav-pill").forEach((pill) => pill.remove());
  }
}

const navObserver = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.type === "childList") {
      syncPills();
      positionActivePill();
    } else if (mutation.type === "attributes" && mutation.attributeName === "class") {
      positionActivePill();
    }
  }
});
const sectionNav = byId("sectionNav");
if (sectionNav) {
  navObserver.observe(sectionNav, {
    childList: true,
    subtree: true,
    attributeFilter: ["class"],
  });
  sectionNav.addEventListener("pointermove", (event) => {
    if (!hoverPill) return;
    const link = event.target.closest(".nav-link");
    if (!link) return;
    const index = navLinks().indexOf(link);
    if (index >= 0) glidePillTo(index);
  });
}

/* 3. Toasts — swipe-to-dismiss with springy snap-back. */
const toastContainer = byId("toastContainer");
let toastDrag = null;

function cancelToastDrag() {
  if (!toastDrag) return;
  toastDrag.toast.classList.remove("swiping");
  toastDrag.toast.classList.add("snap-back");
  toastDrag.toast.style.transform = "";
  toastDrag.toast.style.opacity = "";
  window.setTimeout(() => {
    toastDrag.toast.classList.remove("snap-back");
  }, 300);
  toastDrag = null;
}

function finishToastDrag() {
  if (!toastDrag) return;
  const { toast, dx, flick } = toastDrag;
  toast.classList.remove("swiping");
  if (Math.abs(dx) > SWIPE_DISMISS_AT || flick) {
    const direction = dx > 0 ? 1 : -1;
    toast.style.transition = "transform 0.18s ease, opacity 0.18s ease";
    toast.style.transform = `translateX(${dx + direction * 120}px)`;
    toast.style.opacity = "0";
    window.setTimeout(() => toast.remove(), 180);
  } else {
    toast.classList.add("snap-back");
    toast.style.transform = "";
    toast.style.opacity = "";
    window.setTimeout(() => toast.classList.remove("snap-back"), 300);
  }
  if (Math.abs(dx) > SWIPE_CLICK_AT) {
    suppressToastClick();
  }
  toastDrag = null;
}

/** Swallow the click that follows a drag so it can't dismiss. */
function suppressToastClick() {
  if (!toastContainer) return;
  const guard = (event) => event.stopPropagation();
  toastContainer.addEventListener("click", guard, true);
  window.setTimeout(() => {
    toastContainer.removeEventListener("click", guard, true);
  }, 0);
}

if (toastContainer) {
  toastContainer.addEventListener("pointerdown", (event) => {
    const toast = event.target.closest(".toast");
    if (!toast || toast.classList.contains("toast-leaving")) return;
    toastDrag = {
      toast,
      startX: event.clientX,
      startY: event.clientY,
      dx: 0,
      flick: false,
      downAt: performance.now(),
    };
    toast.classList.add("swiping");
  });

  window.addEventListener("pointermove", (event) => {
    if (!toastDrag) return;
    const dx = event.clientX - toastDrag.startX;
    const dy = event.clientY - toastDrag.startY;
    if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
    if (Math.abs(dy) > Math.abs(dx)) {
      // Vertical intent — hand the gesture back to the page.
      cancelToastDrag();
      return;
    }
    toastDrag.dx = dx;
    const elapsed = Math.max(1, performance.now() - toastDrag.downAt);
    toastDrag.flick =
      Math.abs(dx) > SWIPE_FLICK_PX && Math.abs(dx) / elapsed > SWIPE_FLICK_VELOCITY;
    toastDrag.toast.style.transform = `translateX(${dx}px)`;
    toastDrag.toast.style.opacity = String(1 - Math.min(Math.abs(dx) / SWIPE_FADE_OVER, 0.6));
  });

  window.addEventListener("pointerup", () => finishToastDrag());
  window.addEventListener("pointercancel", () => cancelToastDrag());
}

/* 3b. Scout dashboard — firecrawl's "Scout searching in
      progress" panel, ported from open-scouts
      (ScoutAgent/Results.tsx): a typed query with blinking
      cursor, rows that reveal one by one with a decrypt
      effect, an endless linear marquee, and count-up stats.
      Data comes from /admin/api/dashboard (latest commits,
      token usage, USD→IDR, agent/skill counts). Timers are
      page-scoped so nothing needs cleanup; reduced-motion
      renders the final state instantly. */

function scoutById(id) {
  return document.getElementById(id);
}

/** Firecrawl encryptText port: the tail of the string stays
    scrambled until progress reaches 1; spaces never scramble.
    @param {number} progress - 0 (fully scrambled) to 1 (plain) */
function scoutEncrypt(text, progress, randomizeChance = 0.7) {
  const encryptedCount = Math.floor(text.length * (1 - progress));
  let result = "";
  let charIndex = 1;
  for (const char of text) {
    if (char === " ") {
      result += char;
      charIndex += 1;
      continue;
    }
    if (text.length - charIndex < encryptedCount) {
      result +=
        Math.random() < randomizeChance
          ? char
          : SCOUT_ENCRYPT_CHARS[
              Math.floor(Math.random() * SCOUT_ENCRYPT_CHARS.length)
            ];
    } else {
      result += char;
    }
    charIndex += 1;
  }
  return result;
}

/** 1,009,743 → "1.0M", 9,091 → "9.1k", 812 → "812" */
function scoutCompact(value) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(Math.round(value));
}

/** 2834 → "2,834" — the count-up format for the left stats. */
function scoutThousands(value) {
  return Math.round(value).toLocaleString("en-US");
}

/** $0.16 / $673.23 — costs keep two decimals. */
function scoutUsd(cost) {
  return `$${cost.toFixed(2)}`;
}

/** USD→IDR, compact: "Rp 12.1M" over a million, "Rp 3,430" below. */
function scoutIdr(cost, rate) {
  const idr = cost * rate;
  if (idr >= 1_000_000) return `Rp ${(idr / 1_000_000).toFixed(1)}M`;
  return `Rp ${Math.round(idr).toLocaleString("en-US")}`;
}

/** One marquee row: subject, hash · date · tokens, cost at right. */
function buildScoutRow(commit, rate) {
  const row = document.createElement("div");
  row.className = "scout-row";

  const title = document.createElement("div");
  title.className = "scout-row-title";
  title.textContent = commit.subject;

  const desc = document.createElement("div");
  desc.className = "scout-row-desc";
  const when = new Date(commit.date_iso);
  const dateLabel = Number.isNaN(when.getTime())
    ? ""
    : when.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
  desc.textContent = `${commit.short} · ${dateLabel} · ${scoutCompact(
    commit.tokens,
  )} tokens`;

  const foot = document.createElement("div");
  foot.className = "scout-row-foot";
  const dot = document.createElement("span");
  dot.className = "scout-row-dot";
  dot.setAttribute("aria-hidden", "true");
  const url = document.createElement("span");
  url.className = "scout-row-url";
  url.textContent = "claudey";
  const cost = document.createElement("span");
  cost.className = "scout-row-cost";
  cost.textContent = `${scoutUsd(commit.cost_usd)} · ${scoutIdr(
    commit.cost_usd,
    rate,
  )}`;
  foot.append(dot, url, cost);

  row.append(title, desc, foot);
  return row;
}

/** Decrypt one field over ~0.5s (firecrawl's Field effect:
    progress steps 0.2 per 100ms, offset by row index). */
function revealScoutField(el, finalText, offsetTicks) {
  let i = offsetTicks * -0.5;
  const tick = () => {
    i += 0.2;
    if (i < 1) {
      el.textContent = scoutEncrypt(finalText, Math.max(i, 0), SCOUT_RANDOM_CHANCE);
      window.setTimeout(tick, SCOUT_ENCRYPT_MS);
    } else {
      el.textContent = finalText;
    }
  };
  tick();
}

/** Count up to finalValue in scoutThousands format ("2834 found"). */
function countUpScoutValue(el, finalValue) {
  let value = 0;
  const tick = () => {
    value += Math.floor(finalValue / (20 + Math.random() * 40));
    if (value >= finalValue) {
      el.textContent = `${scoutThousands(finalValue)} found`;
      return;
    }
    el.textContent = `${scoutThousands(value)} found`;
    window.setTimeout(tick, SCOUT_COUNTUP_MS);
  };
  tick();
}

/** Cycle "Scout searching in progress" + up to three dots. */
function cycleScoutDots(titleEl, baseText) {
  let dots = 0;
  const tick = () => {
    dots += 1;
    titleEl.textContent = `${baseText}${".".repeat(dots % 4)}`;
    window.setTimeout(tick, SCOUT_DOT_MS);
  };
  tick();
}

function initScoutDashboard() {
  const titleEl = scoutById("scoutTitle");
  const queryEl = scoutById("scoutQuery");
  const cursorEl = scoutById("scoutCursor");
  const statsEl = scoutById("scoutStats");
  const trackEl = scoutById("scoutTrack");
  if (!titleEl || !queryEl || !cursorEl || !statsEl || !trackEl) return;

  const run = (payload) => {
    const commits = Array.isArray(payload?.commits) ? payload.commits : [];
    const rate =
      typeof payload?.usd_to_idr === "number"
        ? payload.usd_to_idr
        : SCOUT_FALLBACK_RATE;
    // data-final is the source of truth for the count-up targets.
    const stats = payload?.stats ?? { agents: 0, skills: 0 };
    const statEls = Array.from(
      statsEl.querySelectorAll(".scout-stat-value"),
    );
    const statFinals = [stats.agents ?? 0, stats.skills ?? 0];
    statEls.forEach((el, index) => {
      el.dataset.final = String(statFinals[index]);
    });
    const rowCount = commits.length;

    // Two identical copies make the marquee loop seamlessly;
    // the second copy is hidden from the accessibility tree.
    const copyEls = [];
    if (rowCount > 0) {
      for (let copyIndex = 0; copyIndex < 2; copyIndex += 1) {
        const copy = document.createElement("div");
        copy.className = "scout-copy";
        if (copyIndex === 1) copy.setAttribute("aria-hidden", "true");
        commits.forEach((commit) => copy.appendChild(buildScoutRow(commit, rate)));
        trackEl.appendChild(copy);
        copyEls.push(copy);
      }
      trackEl.style.animationDuration = `${(rowCount * SCOUT_ROW_H) / SCOUT_SPEED}s`;
    } else {
      const empty = buildScoutRow(
        {
          short: "—",
          date_iso: "",
          subject: "No commits yet — start building",
          tokens: 0,
          cost_usd: 0,
        },
        rate,
      );
      empty.querySelector(".scout-row-cost").textContent = "";
      trackEl.appendChild(empty);
    }

    const allRows = Array.from(trackEl.querySelectorAll(".scout-row"));
    const revealed = new Set();
    const rowOf = (row) =>
      rowCount > 0 ? allRows.indexOf(row) % rowCount : 0;

    const reveal = (row) => {
      if (revealed.has(row)) return;
      revealed.add(row);
      row.classList.add("scout-row-visible");
      const offset = rowOf(row);
      [".scout-row-title", ".scout-row-desc", ".scout-row-cost"].forEach(
        (selector) => {
          const field = row.querySelector(selector);
          if (field) revealScoutField(field, field.textContent, offset);
        },
      );
    };

    let step = -1;
    let scrollStarted = false;
    let countStarted = false;

    const setStep = (next) => {
      step = next;
      // The cursor blinks only while the query is being typed.
      cursorEl.classList.toggle("scout-cursor-hidden", step !== 0);
      allRows.forEach((row) => {
        if (rowOf(row) < Math.max(step, 0)) reveal(row);
      });
      if (step >= 1) {
        if (!scrollStarted && rowCount > 0) {
          scrollStarted = true;
          trackEl.classList.add("scout-scrolling");
        }
        if (!countStarted) {
          countStarted = true;
          statFinals.forEach((finalValue, index) =>
            countUpScoutValue(statEls[index], finalValue),
          );
        }
        cursorEl.classList.add("scout-cursor-hidden");
      }
    };

    // Typing drives steps 0→4; late rows then arrive at SCOUT_ROW_MS.
    const advanceRows = () => {
      if (step >= rowCount) return;
      setStep(step + 1);
      window.setTimeout(advanceRows, SCOUT_ROW_MS);
    };
    const type = (typed) => {
      queryEl.textContent = SCOUT_QUERY.slice(0, typed);
      setStep(Math.floor(Math.min(typed / SCOUT_QUERY.length, 1) * 4));
      if (typed >= SCOUT_QUERY.length) {
        advanceRows();
        return;
      }
      window.setTimeout(
        () => type(typed + 1),
        SCOUT_CHAR_MIN + Math.random() * (SCOUT_CHAR_MAX - SCOUT_CHAR_MIN),
      );
    };

    if (REDUCED_MOTION) {
      // Final state instantly: rows, values, and full query text.
      // (reveal() would scramble the fields first — skip it.)
      allRows.forEach((row) => row.classList.add("scout-row-visible"));
      statEls.forEach((el, index) => {
        el.textContent = `${scoutThousands(statFinals[index])} found`;
      });
      queryEl.textContent = SCOUT_QUERY;
      return;
    }

    cycleScoutDots(titleEl, "Scout searching in progress");
    window.setTimeout(() => {
      queryEl.textContent = "";
      setStep(0);
      type(1);
    }, 500);
  };

  fetch("/admin/api/dashboard")
    .then((response) => (response.ok ? response.json() : null))
    .then(run)
    .catch(() => run(null));
}

initScoutDashboard();

/* 4. Media-query changes — keep tweens and pills consistent,
      and clear any active hover-peek so aria-expanded matches
      the persistent state again. */
function restoreSidebarAria() {
  if (!sidebarToggleEl) return;
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  sidebarToggleEl.setAttribute("aria-expanded", String(!collapsed));
}

function cancelSidebarTween() {
  if (sidebarTweenId !== null) {
    cancelAnimationFrame(sidebarTweenId);
    sidebarTweenId = null;
  }
  sidebarTweenTarget = null;
}

motionQuery.addEventListener("change", () => {
  cancelSidebarTween();
  if (DESKTOP.matches) {
    snapSidebar(document.body.classList.contains("sidebar-collapsed"));
    restoreSidebarAria();
  }
});

DESKTOP.addEventListener("change", () => {
  cancelSidebarTween();
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  snapSidebar(DESKTOP.matches && collapsed);
  restoreSidebarAria();
  syncPills();
});

/* 5. Init — align with the state admin.js restored, then build
      pills for whatever the nav already contains. */
if (DESKTOP.matches && document.body.classList.contains("sidebar-collapsed")) {
  snapSidebar(true);
}
syncPills();
