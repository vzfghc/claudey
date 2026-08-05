/* ============================================
   admin-animations.js — firecrawl-style motion layer
   ES module loaded after admin.js. Owns only decorative
   motion: the JS-tweened sidebar collapse (hover-peek
   expansion plus click pin/unpin), the sliding nav pills,
   and toast swipe-to-dismiss. Persistent state, inert, and
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
const SWIPE_DISMISS_AT = 70; // px of horizontal drag that dismisses a toast
const SWIPE_FADE_OVER = 220; // px of drag that fully fades a toast
const SWIPE_CLICK_AT = 10; // px of drag that suppresses click-to-dismiss
const SWIPE_FLICK_PX = 30; // minimum drag for a velocity-based dismiss
const SWIPE_FLICK_VELOCITY = 1.2; // px per ms that counts as a flick

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

/** Jump straight to a collapsed/expanded state (no tween). */
function snapSidebar(collapsed) {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;
  if (collapsed) {
    sidebar.style.width = `${SIDEBAR_W.collapsed}px`;
    sidebar.style.paddingLeft = `${SIDEBAR_W.padCollapsed}px`;
    sidebar.style.paddingRight = `${SIDEBAR_W.padCollapsed}px`;
    document.documentElement.style.setProperty("--sidebar-w", `${SIDEBAR_W.collapsed}px`);
    setLabelOpacity("0");
    document.body.classList.add("sidebar-rail");
  } else {
    sidebar.style.width = "";
    sidebar.style.paddingLeft = "";
    sidebar.style.paddingRight = "";
    document.documentElement.style.removeProperty("--sidebar-w");
    setLabelOpacity("");
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
    if (progress < 1) {
      sidebarTweenId = requestAnimationFrame(frame);
    } else {
      sidebarTweenId = null;
      sidebarTweenTarget = null;
      if (targetCollapsed) {
        document.body.classList.add("sidebar-rail");
      } else {
        sidebar.style.width = "";
        sidebar.style.paddingLeft = "";
        sidebar.style.paddingRight = "";
        document.documentElement.style.removeProperty("--sidebar-w");
        setLabelOpacity("");
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
      pill, both absolute and sliding between items. */
let activePill = null;
let hoverPill = null;

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
    if (index >= 0) {
      hoverPill.style.transform = `translateY(${index * NAV_PITCH}px)`;
    }
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
