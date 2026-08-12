import { BarChart3 } from "lucide-react";
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
      className="sidebar-budget space-y-3 px-1"
      style={{
        opacity: "var(--sidebar-budget-opacity, 1)",
      }}
      hidden={limit <= 0}
    >
      <button
        type="button"
        onClick={onStatClick}
        className="group flex w-full items-center justify-between gap-3 text-left text-ink transition-colors duration-200 hover:text-heat"
        data-sidebar-budget-stat
      >
        <span className="text-[17px] leading-tight font-normal tracking-[-0.374px]">
          {formatUsd(remaining)} left
        </span>
        <BarChart3
          className="size-5 shrink-0 text-ink-muted-48 transition-colors duration-200 group-hover:text-heat"
          strokeWidth={1.8}
          aria-hidden="true"
        />
      </button>

      <div
        className="h-3 w-full overflow-hidden rounded-pill bg-hairline"
        role="progressbar"
        aria-label="Monthly budget used"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <div
          className="h-full rounded-pill bg-heat transition-[width] duration-500 ease-default"
          style={{ width: `${(ratio * 100).toFixed(1)}%` }}
        />
      </div>

      <div className="flex items-center justify-between gap-3 text-[14px] leading-tight">
        <span className="text-ink-muted-48" data-sidebar-budget-reset>
          Resets {resetLabel}
        </span>
        <span className="shrink-0 font-normal text-heat">Upgrade</span>
      </div>
    </div>
  );
}