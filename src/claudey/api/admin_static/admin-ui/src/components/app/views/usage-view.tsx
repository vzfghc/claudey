import { useJson } from "@/hooks/use-json";
import { UsageHero } from "@/components/app/usage/usage-hero";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { Button } from "@/components/ui/shadcn/button";
import type { AdminUsagePayload } from "@/api/client";
import type { DashboardPayload } from "@/api/types";
import { cn, compactNumber, thousands } from "@/lib/utils";

/** Usage view — the hero is preserved; charts/heatmap/table ship in Phase 3. */
export function UsageView() {
  const usage = useJson<AdminUsagePayload>("/admin/api/usage");
  const dashboard = useJson<DashboardPayload>("/admin/api/dashboard");

  const payload = usage.data;
  const usdToIdr = dashboard.data?.usd_to_idr ?? 18000;

  if (usage.isLoading || dashboard.isLoading) {
    return (
      <PlaceholderView
        title="Usage"
        eyebrow="Tokens · Cost · Activity"
        status="loading"
        slots={[
          <div key="hero" className="animate-pulse h-64 rounded-lg bg-parchment" aria-hidden="true" />,
        ]}
      />
    );
  }

  if (usage.error || !payload) {
    return (
      <PlaceholderView
        title="Usage"
        eyebrow="Tokens · Cost · Activity"
        status="error"
        action={
          <Button variant="pearl" onClick={() => window.location.reload()}>
            Retry
          </Button>
        }
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

  return (
    <section className="animate-rise-in mx-auto max-w-[1080px] px-6 py-10">
      <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
        Tokens · Cost · Activity
      </p>
      <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
        Usage
      </h1>

      <div className="mt-6 space-y-6">
        <UsageHero
          payload={payload}
          billing={payload.billing}
          usdToIdr={usdToIdr}
        />

        {/* Provider breakdown strip (preserved card, tremor charts Phase 3) */}
        <ProviderStrip providers={payload.providers ?? []} />
      </div>
    </section>
  );
}

function ProviderStrip({
  providers,
}: {
  providers: Array<{ provider: string; total_tokens: number }>;
}) {
  const total = providers.reduce((sum, provider) => sum + (provider.total_tokens || 0), 0);
  if (!providers.length) return null;

  return (
    <article className="rounded-lg border border-hairline bg-pearl p-5">
      <h2 className="text-[17px] font-semibold tracking-[-0.374px] text-ink">Providers</h2>
      <ul className="mt-3 space-y-2">
        {providers.map((provider) => {
          const share = total > 0 ? (provider.total_tokens / total) * 100 : 0;
          return (
            <li key={provider.provider}>
              <div className="flex items-baseline justify-between gap-3 text-[14px]">
                <span className="text-ink">{provider.provider}</span>
                <span className="tabular-nums text-ink-muted-48">
                  {compactNumber(provider.total_tokens)} · {share.toFixed(1)}%
                </span>
              </div>
              <div
                className="mt-1 h-1 w-full overflow-hidden rounded-pill bg-black/[0.05]"
                role="presentation"
              >
                <div
                  className={cn("h-full rounded-pill bg-heat")}
                  style={{ width: `${Math.max(share, 2)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[12px] text-ink-muted-48">
        <span className="tabular-nums">{thousands(total)}</span> tokens across all providers · {providers.length} active
      </p>
    </article>
  );
}