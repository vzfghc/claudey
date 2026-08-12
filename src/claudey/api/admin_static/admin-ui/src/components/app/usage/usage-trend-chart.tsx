import { AreaChart } from "@tremor/react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import { compactNumber } from "@/lib/utils";

interface DailyRow {
  date: string;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
}

interface UsageTrendChartProps {
  daily: DailyRow[];
}

export function UsageTrendChart({ daily }: UsageTrendChartProps) {
  const rows = daily ?? [];
  if (!rows.length) return null;

  const total = rows.reduce((sum, row) => sum + (row.total_tokens || 0), 0);

  const chartData = rows.map((row) => ({
    date: row.date,
    "Total tokens": row.total_tokens || 0,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Last 30 days</CardTitle>
        <span className="tabular-nums text-[13px] text-ink-muted-48">
          {compactNumber(total)} total
        </span>
      </CardHeader>
      <CardContent>
        <AreaChart
          data={chartData}
          index="date"
          categories={["Total tokens"]}
          colors={["orange"]}
          showLegend={false}
          showGridLines={true}
          showXAxis={true}
          showYAxis={true}
          yAxisWidth={48}
          minValue={0}
          connectNulls={true}
          valueFormatter={(v: number) => compactNumber(v)}
          className="h-[180px]"
        />
      </CardContent>
    </Card>
  );
}
