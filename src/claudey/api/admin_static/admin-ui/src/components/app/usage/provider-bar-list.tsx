import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import { BarList } from "@/components/ui/shadcn/bar-list";
import { compactNumber, thousands } from "@/lib/utils";

interface ProviderRow {
  provider: string;
  total_tokens: number;
  model_count?: number;
}

interface ProviderBarListProps {
  providers: ProviderRow[];
}

/** Top providers by token share — shadcn BarList with heat bars. */
export function ProviderBarList({ providers }: ProviderBarListProps) {
  if (!providers.length) return null;

  const total = providers.reduce((sum, p) => sum + (p.total_tokens || 0), 0);

  const data = providers.map((p) => ({
    name: p.provider,
    value: p.total_tokens || 0,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top providers</CardTitle>
        <span className="tabular-nums text-[13px] text-ink-muted-48">
          {thousands(total)} tokens · {providers.length} active
        </span>
      </CardHeader>
      <CardContent>
        <BarList
          data={data}
          valueFormatter={(value: number) => compactNumber(value)}
          barClassName="bg-heat"
          barGap={8}
          barHeight={28}
          sortOrder="descending"
        />
      </CardContent>
    </Card>
  );
}