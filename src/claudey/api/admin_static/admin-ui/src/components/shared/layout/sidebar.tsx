import * as React from "react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import {
  BarChart3,
  Boxes,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  SlidersHorizontal,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useReducedMotion, useStoredFlag } from "@/hooks/use-reduced-motion";

/* ============================================================================
   PRESERVED CHOREOGRAPHY — do not redesign.
   Ported from admin-animations.js + admin.css (v5.26.0). The exact curves,
   thresholds, and glide model are the acceptance test:
   - collapse 350ms / expand 220ms, easeOutQuint, per-frame rAF inline writes
   - label/budget fade ends at 120px / 170px of sidebar width
   - nav pill glide: easeOutQuart 160ms, sine scale dip ANCHORED TO TRAVEL
     progress (PILL_DIP 0.07), retarget-safe (never restarts from 0)
   - snap mode under prefers-reduced-motion and max-width: 900px
   - aria-expanded on toggle, aria-hidden on pills
   - localStorage key claudey.sidebar.collapsed
   ============================================================================ */

const SIDEBAR_W = {
  expanded: 256,
  collapsed: 64,
  padExpanded: 20,
  padCollapsed: 12,
  collapseMs: 350,
  expandMs: 220,
};
const LABEL_FADE_END = 120;
const BUDGET_FADE_END = 170;
const NAV_ITEM_HEIGHT = 40;
const NAV_PITCH = NAV_ITEM_HEIGHT + 6;
const PILL_GLIDE_MS = 160;
const PILL_DIP = 0.07;

function easeOutQuint(t: number) {
  return 1 - Math.pow(1 - t, 5);
}
function easeOutQuart(t: number) {
  return 1 - Math.pow(1 - t, 4);
}
function labelOpacityFor(width: number) {
  return Math.min(1, Math.max(0, (width - LABEL_FADE_END) / (SIDEBAR_W.expanded - LABEL_FADE_END)));
}
function budgetOpacityFor(width: number) {
  return Math.min(1, Math.max(0, (width - BUDGET_FADE_END) / (SIDEBAR_W.expanded - BUDGET_FADE_END)));
}

export interface SidebarItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const DEFAULT_ITEMS: SidebarItem[] = [
  { id: "usage", label: "Usage", icon: <BarChart3 size={18} strokeWidth={2} /> },
  { id: "providers", label: "Providers", icon: <Boxes size={18} strokeWidth={2} /> },
  { id: "model_config", label: "Model Config", icon: <SlidersHorizontal size={18} strokeWidth={2} /> },
  { id: "messaging", label: "Messaging", icon: <MessageSquareText size={18} strokeWidth={2} /> },
];

const BRAND_MARK_PATH =
  "M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-7.258 0h3.767L16.906 20h-3.674l-1.343-3.461H5.017l-1.344 3.46H0L6.57 3.522zm4.132 9.959L8.453 7.687 6.205 13.48H10.7z";

interface SidebarProps {
  items?: SidebarItem[];
  activeId?: string;
  onNavigate: (id: string) => void;
  /** optional footer widget — e.g. the sidebar budget (kept as a slot) */
  footer?: React.ReactNode;
}

export function Sidebar({ items = DEFAULT_ITEMS, activeId, onNavigate, footer }: SidebarProps) {
  const reducedMotion = useReducedMotion();
  const [collapsed, setCollapsed] = useStoredFlag("claudey.sidebar.collapsed", false);
  const sidebarRef = useRef<HTMLElement | null>(null);
  const tweenId = useRef<number | null>(null);
  const tweenTarget = useRef<boolean | null>(null);

  // Pills: active (heat) + hover (grey), both absolutely positioned and
  // sliding between items. Pill state mirrors the vanilla module.
  const navRef = useRef<HTMLElement | null>(null);
  const activePillRef = useRef<HTMLDivElement | null>(null);
  const hoverPillRef = useRef<HTMLDivElement | null>(null);
  const pillTweenId = useRef<number | null>(null);
  const pillFromY = useRef(0);
  const pillFromScale = useRef(1);
  const pillTargetIndex = useRef(-1);
  const pillY = useRef(0);
  const pillScale = useRef(1);

  const isDesktop = () => window.matchMedia("(min-width: 901px)").matches;

  const labelEls = useCallback(() => {
    const root = sidebarRef.current;
    if (!root) return [];
    return Array.from(root.querySelectorAll<HTMLElement>("[data-sidebar-label]"));
  }, []);

  const setLabelOpacity = useCallback(
    (opacity: string) => {
      labelEls().forEach((el) => {
        el.style.opacity = opacity;
      });
    },
    [labelEls],
  );

  const clearLayoutInline = useCallback(() => {
    const root = sidebarRef.current;
    if (!root) return;
    root.querySelectorAll<HTMLElement>("[data-nav-link]").forEach((link) => {
      link.style.gap = "";
      link.style.paddingLeft = "";
    });
    root.querySelectorAll<HTMLElement>("[data-sidebar-label]").forEach((el) => {
      el.style.width = "";
    });
  }, []);

  const cancelTween = useCallback(() => {
    if (tweenId.current !== null) {
      cancelAnimationFrame(tweenId.current);
      tweenId.current = null;
    }
    tweenTarget.current = null;
  }, []);

  /** Jump straight to a collapsed/expanded state (no tween). */
  const snap = useCallback(
    (next: boolean) => {
      const sidebar = sidebarRef.current;
      if (!sidebar) return;
      clearLayoutInline();
      const width = next ? SIDEBAR_W.collapsed : SIDEBAR_W.expanded;
      const pad = next ? SIDEBAR_W.padCollapsed : SIDEBAR_W.padExpanded;
      sidebar.style.width = `${width}px`;
      sidebar.style.paddingLeft = `${pad}px`;
      sidebar.style.paddingRight = `${pad}px`;
      document.documentElement.style.setProperty("--sidebar-w", `${width}px`);
      setLabelOpacity(next ? "0" : "1");
      if (footer) document.documentElement.style.setProperty("--sidebar-budget-opacity", next ? "0" : "1");
    },
    [clearLayoutInline, footer, setLabelOpacity],
  );

  /** Per-frame width tween (easeOutQuint). */
  const tween = useCallback(
    (targetCollapsed: boolean) => {
      if (tweenTarget.current === targetCollapsed && tweenId.current !== null) return;
      cancelTween();
      tweenTarget.current = targetCollapsed;
      const sidebar = sidebarRef.current;
      if (!sidebar) return;
      const duration = targetCollapsed ? SIDEBAR_W.collapseMs : SIDEBAR_W.expandMs;
      const startW = parseFloat(sidebar.style.width) || SIDEBAR_W.expanded;
      const startPad = parseFloat(sidebar.style.paddingLeft) || SIDEBAR_W.padExpanded;
      const endW = targetCollapsed ? SIDEBAR_W.collapsed : SIDEBAR_W.expanded;
      const endPad = targetCollapsed ? SIDEBAR_W.padCollapsed : SIDEBAR_W.padExpanded;
      const startedAt = performance.now();

      const frame = (now: number) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = easeOutQuint(progress);
        const width = startW + (endW - startW) * eased;
        const pad = startPad + (endPad - startPad) * eased;
        sidebar.style.width = `${width}px`;
        sidebar.style.paddingLeft = `${pad}px`;
        sidebar.style.paddingRight = `${pad}px`;
        document.documentElement.style.setProperty("--sidebar-w", `${width}px`);
        setLabelOpacity(String(labelOpacityFor(width)));
        if (footer) {
          document.documentElement.style.setProperty(
            "--sidebar-budget-opacity",
            String(budgetOpacityFor(width)),
          );
        }
        if (progress < 1) {
          tweenId.current = requestAnimationFrame(frame);
        } else {
          tweenId.current = null;
          tweenTarget.current = null;
          clearLayoutInline();
          sidebar.style.width = `${endW}px`;
          sidebar.style.paddingLeft = `${endPad}px`;
          sidebar.style.paddingRight = `${endPad}px`;
        }
      };
      tweenId.current = requestAnimationFrame(frame);
    },
    [cancelTween, clearLayoutInline, footer, setLabelOpacity],
  );

  const toggle = useCallback(() => {
    const next = !collapsed;
    setCollapsed(next);
    if (reducedMotion || !isDesktop()) {
      if (isDesktop()) snap(next);
      return;
    }
    tween(next);
  }, [collapsed, reducedMotion, setCollapsed, snap, tween]);

  // Mirror the persisted state into the DOM on mount / desktop breakpoint change.
  useEffect(() => {
    document.body.classList.toggle("sidebar-collapsed", collapsed);
    if (reducedMotion || !isDesktop()) snap(collapsed);
    else if (collapsed) snap(collapsed);
  }, [collapsed, reducedMotion, snap]);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    const onChange = () => {
      cancelTween();
      snap(collapsed);
    };
    desktop.addEventListener("change", onChange);
    return () => desktop.removeEventListener("change", onChange);
  }, [cancelTween, collapsed, snap]);

  // ---- Nav pill glide (travel-anchored sine dip) ----
  // Both the active (heat) and hover (grey) pills share one glide; each keeps
  // its own tween state so they never interrupt each other.
  interface PillGlideState {
    tweenId: React.MutableRefObject<number | null>;
    fromY: React.MutableRefObject<number>;
    fromScale: React.MutableRefObject<number>;
    targetIndex: React.MutableRefObject<number>;
    y: React.MutableRefObject<number>;
    scale: React.MutableRefObject<number>;
  }

  const hoverPillState: PillGlideState = useMemo(
    () => ({
      tweenId: pillTweenId,
      fromY: pillFromY,
      fromScale: pillFromScale,
      targetIndex: pillTargetIndex,
      y: pillY,
      scale: pillScale,
    }),
    [pillTweenId, pillFromY, pillFromScale, pillTargetIndex, pillY, pillScale],
  );

  const activePillTweenId = useRef<number | null>(null);
  const activePillFromY = useRef(0);
  const activePillFromScale = useRef(1);
  const activePillTargetIndex = useRef(-1);
  const activePillY = useRef(0);
  const activePillScale = useRef(1);
  const activePillInitialized = useRef(false);
  const activePillState: PillGlideState = useMemo(
    () => ({
      tweenId: activePillTweenId,
      fromY: activePillFromY,
      fromScale: activePillFromScale,
      targetIndex: activePillTargetIndex,
      y: activePillY,
      scale: activePillScale,
    }),
    [
      activePillTweenId,
      activePillFromY,
      activePillFromScale,
      activePillTargetIndex,
      activePillY,
      activePillScale,
    ],
  );

  const glideTo = useCallback(
    (el: HTMLDivElement | null, s: PillGlideState, index: number) => {
      if (!el || index === s.targetIndex.current) return;
      if (s.tweenId.current !== null) {
        cancelAnimationFrame(s.tweenId.current);
        s.tweenId.current = null;
      }
      if (reducedMotion) {
        s.targetIndex.current = index;
        s.y.current = s.fromY.current = index * NAV_PITCH;
        s.scale.current = s.fromScale.current = 1;
        el.style.transform = `translateY(${s.y.current}px)`;
        return;
      }
      s.fromY.current = s.y.current;
      s.fromScale.current = Math.min(s.scale.current, 1);
      s.targetIndex.current = index;
      const start = performance.now();

      const tick = (now: number) => {
        const progress = Math.max(0, Math.min(1, (now - start) / PILL_GLIDE_MS));
        const eased = easeOutQuart(progress);
        s.y.current = s.fromY.current + (index * NAV_PITCH - s.fromY.current) * eased;
        const span = index * NAV_PITCH - s.fromY.current;
        const travel = span === 0 ? 0 : (s.y.current - s.fromY.current) / span;
        s.scale.current =
          s.fromScale.current +
          (1 - s.fromScale.current) * eased -
          PILL_DIP * Math.sin(travel * Math.PI);
        el.style.transform = `translateY(${s.y.current}px) scale(${s.scale.current.toFixed(4)})`;
        if (progress < 1) {
          s.tweenId.current = requestAnimationFrame(tick);
        } else {
          s.tweenId.current = null;
          s.fromY.current = s.y.current;
          s.fromScale.current = 1;
        }
      };
      s.tweenId.current = requestAnimationFrame(tick);
    },
    [reducedMotion],
  );

  /** Park the hover pill at an index (no tween) — used when the active view changes. */
  const resetPillTween = useCallback((index: number) => {
    if (pillTweenId.current !== null) {
      cancelAnimationFrame(pillTweenId.current);
      pillTweenId.current = null;
    }
    pillTargetIndex.current = index;
    pillFromY.current = pillY.current = index * NAV_PITCH;
    pillFromScale.current = pillScale.current = 1;
    if (hoverPillRef.current) {
      hoverPillRef.current.style.transform = `translateY(${pillY.current}px)`;
    }
  }, []);

  const hoverGlide = useCallback(
    (index: number) => {
      glideTo(hoverPillRef.current, hoverPillState, index);
    },
    [glideTo, hoverPillState],
  );

  useLayoutEffect(() => {
    const activeIndex = Math.max(0, items.findIndex((item) => item.id === activeId));
    if (!activePillInitialized.current) {
      // First mount: snap the active pill into place before paint (no flash).
      activePillInitialized.current = true;
      activePillY.current = activeIndex * NAV_PITCH;
      activePillTargetIndex.current = activeIndex;
      if (activePillRef.current) {
        activePillRef.current.style.transform = `translateY(${activePillY.current}px)`;
      }
    } else {
      // Active view changed: glide the heat pill to its new slot.
      glideTo(activePillRef.current, activePillState, activeIndex);
    }
    // Keep the hover pill parked at the active slot (hidden) so it glides from
    // the right place the next time the pointer moves.
    resetPillTween(activeIndex);
    if (hoverPillRef.current) hoverPillRef.current.style.opacity = "0";
  }, [activeId, items, glideTo, resetPillTween, activePillState]);

  const activeIndex = Math.max(0, items.findIndex((item) => item.id === activeId));

  return (
    <aside
      ref={sidebarRef}
      className={cn(
        "relative z-20 flex h-full flex-col border-r border-hairline bg-parchment transition-none",
        collapsed && "sidebar-rail",
      )}
      style={{ width: SIDEBAR_W.expanded, paddingLeft: SIDEBAR_W.padExpanded, paddingRight: SIDEBAR_W.padExpanded }}
    >
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center gap-3" data-brand>
        <div
          className="brand-mark grid size-9 shrink-0 place-items-center rounded-lg bg-heat text-white shadow-card transition-transform duration-500 hover:rotate-[-4deg] hover:scale-105"
          aria-hidden="true"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22">
            <path d={BRAND_MARK_PATH} />
          </svg>
        </div>
        <div className="flex flex-col" data-sidebar-label>
          <h1 className="text-[17px] font-semibold leading-tight tracking-[-0.374px] text-ink">
            Claudey
          </h1>
          <p className="text-[12px] leading-none text-ink-muted-48">Server Control</p>
        </div>
      </div>

      {/* Nav */}
      <nav
        ref={navRef}
        className="relative mt-2 flex-1 overflow-hidden"
        aria-label="Admin views"
        onPointerMove={(event) => {
          const hoverPill = hoverPillRef.current;
          if (!hoverPill) return;
          const link = (event.target as HTMLElement).closest<HTMLElement>("[data-nav-link]");
          if (!link) return;
          const index = Number(link.dataset.index ?? -1);
          if (index < 0) return;
          if (index === activeIndex) {
            hoverPill.style.opacity = "0";
            return;
          }
          hoverPill.style.opacity = "1";
          hoverGlide(index);
        }}
        onPointerLeave={() => {
          if (hoverPillRef.current) hoverPillRef.current.style.opacity = "0";
        }}
      >
        {/* Active + hover pills */}
        <div
          ref={activePillRef}
          aria-hidden="true"
          className="nav-pill pointer-events-none absolute left-0 top-0 z-0 h-10 w-full rounded-sm bg-heat/12 transition-none"
        />
        <div
          ref={hoverPillRef}
          aria-hidden="true"
          className="nav-pill pointer-events-none absolute left-0 top-0 z-0 h-10 w-full rounded-sm bg-black/[0.045] opacity-0 transition-none"
        />
        <ul className="relative z-10 m-0 list-none p-0">
          {items.map((item, index) => {
            const isActive = item.id === activeId;
            return (
              <li key={item.id} className="mb-1.5">
                <a
                  href={`#${item.id}`}
                  data-nav-link
                  data-index={index}
                  onClick={(event) => {
                    event.preventDefault();
                    onNavigate(item.id);
                  }}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex h-10 items-center gap-2.5 rounded-sm px-3 text-[14px] leading-none transition-colors duration-200",
                    isActive ? "text-heat" : "text-ink-muted-48 hover:text-ink",
                  )}
                  style={{ paddingLeft: 14 }}
                >
                  <span className="flex size-4 shrink-0 items-center justify-center">{item.icon}</span>
                  <span className="whitespace-nowrap" data-sidebar-label>
                    {item.label}
                  </span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer: collapse toggle + optional budget slot */}
      <div className="shrink-0 pb-3">
        {footer ? (
          // Budget fade is driven by the sidebar tween via --sidebar-budget-opacity.
          <div className="mb-3" data-sidebar-budget>
            {footer}
          </div>
        ) : null}
        <button
          type="button"
          className="flex h-9 w-full items-center gap-2.5 rounded-lg px-3 text-[13px] text-ink-muted-48 transition-colors hover:bg-black/[0.045] hover:text-ink"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="sectionNav"
        >
          {collapsed ? (
            <PanelLeftOpen size={16} strokeWidth={2} />
          ) : (
            <PanelLeftClose size={16} strokeWidth={2} />
          )}
          <span className="whitespace-nowrap" data-sidebar-label>
            {collapsed ? "Expand" : "Collapse"}
          </span>
        </button>
      </div>
    </aside>
  );
}