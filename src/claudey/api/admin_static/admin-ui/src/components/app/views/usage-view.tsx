import { RefreshCw } from "lucide-react";

import { UsageHero } from "@/components/app/usage/usage-hero";
import { UsageHeatmap } from "@/components/app/usage/usage-heatmap";
import { UsageTrendChart } from "@/components/app/usage/usage-trend-chart";
import { UsageDailyTable } from "@/components/app/usage/usage-daily-table";
import { ProviderBarList } from "@/components/app/usage/provider-bar-list";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { useJson } from "@/hooks/use-json";
import type { AdminUsagePayload } from "@/api/client";
import type { DashboardPayload, UsagePayload, BillingPayload } from "@/api/types";
import { useState, useCallback } from "react";

interface DailyRow {
  date: string;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached_input_tokens?: number;
  reasoning_output_tokens?: number;
  conversations?: number;
}

interface HeatWeek {
  start: string;
  days: number[];
}

interface ProviderRow {
  provider: string;
  total_tokens: number;
  model_count?: number;
}

/** Usage view — hero preserved; tremor chart, heatmap, table, provider breakdown rebuilt. */
export function UsageView() {
  const [reloadKey, setReloadKey] = useState(0);
  const usage = useJson<AdminUsagePayload>("/admin/api/usage");
  const dashboard = useJson<DashboardPayload>("/admin/api/dashboard");

  const payload = usage.data;
  const usdToIdr = dashboard.data?.usd_to_idr ?? 18000;

  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
    window.location.reload();
  }, []);

  if (usage.isLoading || dashboard.isLoading) {
    return (
      <PlaceholderView
        title="Usage"
        eyebrow="Tokens · Cost · Activity"
        status="loading"
      />
    );
  }

  if (usage.error || !payload) {
    return (
      <PlaceholderView
        title="Usage"
        eyebrow="Tokens · Cost · Activity"
        status="error"
        action={<Button variant="pearl" onClick={reload}>Retry</Button>}
      />
    );
  }

  if (!payload.available && payload.total_entries === 0) {
    return (
      <PlaceholderView
        title="Usage"
        eyebrow="Tokens · Cost · Activity"
        status="empty"
        message="No usage log yet"
      />
    );
  }

  const daily = (payload.daily ?? []) as unknown as DailyRow[];
  const heatmap = (payload.heatmap ?? []) as unknown as HeatWeek[];
  const providers = (payload.providers ?? []) as ProviderRow[];

  return (
    <div key={reloadKey} className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-[1080px] space-y-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
              Tokens · Cost · Activity
            </p>
            <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Usage
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={payload.available ? "success" : "warn"}>
              {payload.available ? "Tracking" : "Not found"}
            </Badge>
            <Button variant="secondary" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Preserved hero */}
        <UsageHero
          payload={payload as UsagePayload}
          billing={payload.billing as BillingPayload | undefined}
          usdToIdr={usdToIdr}
        />

        {/* Two-column layout: charts left, providers+table right */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <ProviderBarList providers={providers} />
            {heatmap.length > 0 && <UsageHeatmap weeks={heatmap} />}
            {daily.length > 0 && <UsageTrendChart daily={daily} />}
          </div>
          <div className="space-y-6">
            {daily.length > 0 && (
              <UsageDailyTable
                daily={daily}
                billingDays={(payload.billing as BillingPayload | undefined)?.days}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
