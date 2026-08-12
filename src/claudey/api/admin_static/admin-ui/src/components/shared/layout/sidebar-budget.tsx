import { useMemo } from "react";

import { formatUsd } from "@/lib/utils";

/**
 * Sidebar budget widget (preserved). The fade during collapse is driven by
 * the Sidebar's --sidebar-budget-opacity var; the widget itself is static.
 * "Stat" click → usage view via form + navigate callback.
 */

interface SidebarBudgetProps {
  monthlySpendUsd: number;
  monthlyLimitUsd: number;
  onStatClick: () => void;
}

function nextMonthResetLabel(nextReset: Date): string {
  return nextReset.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function SidebarBudget({
  monthlySpendUsd,
  monthlyLimitUsd,
  onStatClick,
}: SidebarBudgetProps) {
  const spend = Number(monthlySpendUsd) || 0;
  const limit = Number(monthlyLimitUsd) || 0;
  const remaining = Math.max(0, limit - spend);
  const ratio = limit > 0 ? Math.min(spend / limit, 1) : 0;

  const resetLabel = useMemo(() => {
    const now = new Date();
    const nextReset = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    return nextMonthResetLabel(nextReset);
  }, []);

  return (
    <div
      className="sidebar-budget"
      style={{
        opacity: "var(--sidebar-budget-opacity, 1)",
      }}
      hidden={limit <= 0}
    >
      <button
        type="button"
        onClick={onStatClick}
        className="flex w-full flex-col gap-1 rounded-lg bg-tile-1 p-2.5 text-left transition-colors duration-200 hover:bg-tile-2"
        data-sidebar-budget-stat
      >
        <div className="flex w-full items-start justify-between gap-2">
          <span className="text-[12px] font-medium text-white/90">
            ${spend.toFixed(2)} spent
          </span>
          <span className="text-[12px] font-medium text-ink-muted-48">
            {formatUsd(remaining)} left
          </span>
        </div>
        <span className="text-[11px] font-normal text-white/60" data-sidebar-budget-reset>
          Resets {resetLabel}
        </span>
      </button>

      <div
        className="mt-1.5 h-1 w-full overflow-hidden rounded-pill bg-tile-3"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <div
          className="h-full rounded-pill bg-heat transition-[width] duration-500 ease-default"
          style={{ width: `${(ratio * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  );
}