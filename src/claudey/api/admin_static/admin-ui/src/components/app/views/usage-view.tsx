import { RefreshCw } from "lucide-react";

import { UsageHero } from "@/components/app/usage/usage-hero";
import { UsageHeatmap } from "@/components/app/usage/usage-heatmap";
import { UsageTrendChart } from "@/components/app/usage/usage-trend-chart";
import { UsageDailyTable } from "@/components/app/usage/usage-daily-table";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import { useJson } from "@/hooks/use-json";
import { cn, compactNumber, thousands } from "@/lib/utils";
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
            <ProviderBreakdown providers={providers} />
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

function ProviderBreakdown({
  providers,
}: {
  providers: ProviderRow[];
}) {
  if (!providers.length) return null;
  const total = providers.reduce((sum, p) => sum + (p.total_tokens || 0), 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <span className="tabular-nums text-[13px] text-ink-muted-48">
          {thousands(total)} tokens · {providers.length} active
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Stacked bar */}
        <div className="flex h-2 w-full overflow-hidden rounded-pill bg-black/[0.05]" role="img" aria-label="Token share by provider">
          {providers.map((p, i) => {
            if ((p.total_tokens || 0) <= 0 || total <= 0) return null;
            const share = (p.total_tokens / total) * 100;
            const colors = ["bg-heat", "bg-heat-soft", "bg-info", "bg-success", "bg-warn"];
            return (
              <div
                key={p.provider}
                className={cn("h-full", colors[i % colors.length])}
                style={{ width: `${share}%` }}
                title={`${p.provider} · ${compactNumber(p.total_tokens)} tokens`}
              />
            );
          })}
        </div>

        {/* Provider list */}
        <ul className="space-y-2">
          {providers
            .sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0))
            .map((provider) => {
              const share = total > 0 ? (provider.total_tokens / total) * 100 : 0;
              return (
                <li key={provider.provider}>
                  <div className="flex items-baseline justify-between gap-3 text-[13px]">
                    <span className="text-ink">{provider.provider}</span>
                    <span className="tabular-nums text-ink-muted-48">
                      {compactNumber(provider.total_tokens)} · {share.toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-pill bg-black/[0.05]">
                    <div
                      className="h-full rounded-pill bg-heat"
                      style={{ width: `${Math.max(share, 2)}%` }}
                    />
                  </div>
                </li>
              );
            })}
        </ul>
      </CardContent>
    </Card>
  );
}
