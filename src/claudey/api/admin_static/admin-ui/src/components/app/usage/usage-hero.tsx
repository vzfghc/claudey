import * as React from "react";
import { useEffect, useRef, useState } from "react";

import { cn, compactNumber, formatUsd, formatIdr, thousands } from "@/lib/utils";
import { useCountUp } from "@/hooks/use-count-up";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import type { BillingPayload, Period, UsagePayload } from "@/api/types";

/**
 * PRESERVED — the total-token hero.
 * Concentric ripple rings (8 circles, size 140+i*70, opacity
 * max(0.08, 0.4-i*0.045), delay i*0.06s, 3.2s cubic-bezier(0.4,0,0.2,1),
 * scale 1→0.78→1) + period tabs with sliding pill + count-up + cost row.
 * Acceptance test is the ring math and the period/toggle behavior, not restyling.
 */

const USAGE_PERIODS: Array<"Total" | Period> = ["Total", "24h", "7d", "30d"];
const COUNT_UP_MS = 500;
const IDR_FALLBACK_RATE = 18000;

function usageHeroValue(
  period: "Total" | Period,
  payload: UsagePayload,
  billing?: BillingPayload,
): number {
  if (period === "Total") {
    const native = payload.totals.total_tokens || 0;
    const deepseek = billing?.total_tokens || 0;
    return native + deepseek;
  }
  const windows = payload.windows || {};
  return windows[period] || 0;
}

interface UsageHeroProps {
  payload: UsagePayload;
  billing?: BillingPayload;
  usdToIdr: number;
}

export function UsageHero({ payload, billing, usdToIdr }: UsageHeroProps) {
  const reducedMotion = useReducedMotion();
  const [period, setPeriod] = useState<"Total" | Period>("Total");
  const [fullNumbers, setFullNumbers] = useState(false);

  const tabsRef = useRef<HTMLDivElement | null>(null);
  const indicatorRef = useRef<HTMLDivElement | null>(null);
  const activeTabRef = useRef<HTMLButtonElement | null>(null);

  const target = usageHeroValue(period, payload, billing);
  const counted = useCountUp(target, COUNT_UP_MS, reducedMotion);
  const displayValue = fullNumbers ? Math.round(counted) : counted;

  // Position the sliding pill indicator under the active tab after layout.
  useEffect(() => {
    const indicator = indicatorRef.current;
    const active = activeTabRef.current;
    if (!indicator || !active) return;
    indicator.style.left = `${active.offsetLeft}px`;
    indicator.style.width = `${active.offsetWidth}px`;
  }, [period]);

  const totalCostUsd = billing?.total_cost_usd;
  const idrRate = usdToIdr > 0 ? usdToIdr : IDR_FALLBACK_RATE;

  return (
    <article className="usage-hero animate-rise-in relative flex flex-col items-center overflow-hidden rounded-lg bg-parchment px-6 py-9 text-center">
      {/* Concentric ripple rings — preserved math */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        aria-hidden="true"
        style={{
          maskImage: "linear-gradient(to bottom, black 35%, transparent 92%)",
          WebkitMaskImage: "linear-gradient(to bottom, black 35%, transparent 92%)",
        }}
      >
        {Array.from({ length: 8 }, (_, i) => (
          <div
            key={i}
            className="usage-hero-ripple-circle absolute top-1/2 left-1/2 rounded-full"
            style={{
              width: 140 + i * 70,
              height: 140 + i * 70,
              opacity: Math.max(0.08, 0.4 - i * 0.045),
              animationDelay: `${i * 0.06}s`,
            }}
          />
        ))}
      </div>

      {/* Period segmented control */}
      <div
        ref={tabsRef}
        role="tablist"
        aria-label="Period"
        className="relative z-10 mx-auto mb-4 flex items-center justify-center gap-0 rounded-md bg-black/[0.04] p-1 shadow-[inset_0_1px_1px_rgba(0,0,0,0.04)]"
      >
        <div
          ref={indicatorRef}
          aria-hidden="true"
          className="pointer-events-none absolute top-1 bottom-1 z-0 rounded-sm bg-canvas shadow-float transition-[left,width] duration-300 ease-default"
        />
        {USAGE_PERIODS.map((label, index) => (
          <React.Fragment key={label}>
            {index > 0 && <div aria-hidden="true" className="z-10 mx-1 h-4 w-px bg-hairline" />}
            <button
              type="button"
              ref={label === period ? activeTabRef : undefined}
              role="tab"
              aria-selected={label === period}
              className={cn(
                "relative z-10 rounded-sm border-none bg-transparent px-3.5 py-1.5 text-[12px] leading-none font-semibold transition-[color,transform] duration-200",
                label === period ? "text-heat" : "text-ink-muted-48 hover:text-ink",
              )}
              onClick={() => {
                if (label === period) return;
                setPeriod(label);
              }}
            >
              {label}
            </button>
          </React.Fragment>
        ))}
      </div>

      {/* Hero number — click toggles compact ⇄ full */}
      <button
        type="button"
        title="Click to toggle between compact and full numbers"
        aria-pressed={fullNumbers}
        onClick={() => setFullNumbers((v) => !v)}
        className="usage-hero-number relative z-10 cursor-pointer border-none bg-transparent p-0 font-display text-[clamp(2.5rem,6vw,4rem)] leading-[1.1] font-semibold text-heat tabular-nums transition-[transform] duration-200 ease-default active:scale-[0.98]"
      >
        {fullNumbers ? thousands(displayValue) : compactNumber(displayValue)}
      </button>

      {/* Cost row */}
      <div className="relative z-10 mt-3 flex flex-wrap items-center gap-4 text-[13px] text-ink-muted-48">
        <span>
          <strong className="font-medium text-ink">Total cost:</strong>{" "}
          {totalCostUsd !== undefined ? formatUsd(totalCostUsd) : "—"}
        </span>
        <span aria-hidden="true" className="h-3 w-px bg-hairline" />
        <span>
          <strong className="font-medium text-ink">IDR:</strong>{" "}
          {totalCostUsd !== undefined ? formatIdr(totalCostUsd, idrRate) : "—"}
        </span>
      </div>
    </article>
  );
}