import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/shadcn/chart";
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

const chartConfig = {
  tokens: {
    label: "Total tokens",
    color: "var(--heat)",
  },
} satisfies ChartConfig;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** "2026-08-12" → "Aug 12"; any other format passes through unchanged. */
function formatDate(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return value;
  const [, , month, day] = m;
  const monthIndex = Number(month) - 1;
  if (monthIndex < 0 || monthIndex > 11) return value;
  return `${MONTHS[monthIndex]} ${Number(day)}`;
}

export function UsageTrendChart({ daily }: UsageTrendChartProps) {
  const rows = daily ?? [];
  if (!rows.length) return null;

  const total = rows.reduce((sum, row) => sum + (row.total_tokens || 0), 0);

  const chartData = rows.map((row) => ({
    date: row.date,
    tokens: row.total_tokens || 0,
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
        <ChartContainer config={chartConfig} className="h-[180px] w-full">
          <AreaChart
            data={chartData}
            margin={{ left: 0, right: 12, top: 12, bottom: 0 }}
          >
            <defs>
              <linearGradient id="fillTokens" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--heat)" stopOpacity={0.6} />
                <stop offset="95%" stopColor="var(--heat)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--hairline)" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={(v: string) => formatDate(v)}
              tick={{ fontSize: 12, fill: "var(--ink-muted-48)" }}
            />
            <YAxis
              dataKey="tokens"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              width={48}
              tickFormatter={(v: number) => compactNumber(v)}
              tick={{ fontSize: 12, fill: "var(--ink-muted-48)" }}
            />
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent hideLabel />}
            />
            <Area
              dataKey="tokens"
              type="linear"
              fill="url(#fillTokens)"
              stroke="var(--heat)"
              strokeWidth={2}
              baseValue={0}
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}