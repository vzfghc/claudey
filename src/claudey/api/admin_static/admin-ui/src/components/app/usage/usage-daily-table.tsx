import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/shadcn/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import { cn, compactNumber, formatUsd } from "@/lib/utils";

interface DailyRow {
  date: string;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached_input_tokens?: number;
  reasoning_output_tokens?: number;
  conversations?: number;
}

interface BillingDay {
  date: string;
  cost_usd: number;
}

interface UsageDailyTableProps {
  daily: DailyRow[];
  billingDays?: BillingDay[];
}

const COLUMNS = ["Date", "Total", "Input", "Output", "Cached", "Reasoning", "Conversations", "Cost"] as const;

export function UsageDailyTable({ daily, billingDays }: UsageDailyTableProps) {
  const rows = daily ?? [];
  if (!rows.length) return null;

  const costByDate = new Map<string, number>();
  (billingDays ?? []).forEach((day) => costByDate.set(day.date, day.cost_usd));

  const totals = rows.reduce(
    (acc, row) => ({
      total_tokens: acc.total_tokens + (row.total_tokens || 0),
      input_tokens: acc.input_tokens + (row.input_tokens || 0),
      output_tokens: acc.output_tokens + (row.output_tokens || 0),
      cached_input_tokens: acc.cached_input_tokens + (row.cached_input_tokens || 0),
      reasoning_output_tokens: acc.reasoning_output_tokens + (row.reasoning_output_tokens || 0),
      conversations: acc.conversations + (row.conversations || 0),
      cost_usd: acc.cost_usd + (costByDate.get(row.date) || 0),
    }),
    {
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      cached_input_tokens: 0,
      reasoning_output_tokens: 0,
      conversations: 0,
      cost_usd: 0,
    },
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Daily breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-hairline">
                {COLUMNS.map((label) => (
                  <TableHead key={label}>{label}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="font-semibold border-hairline">
                <TableCell>Total</TableCell>
                <TableCell>{compactNumber(totals.total_tokens)}</TableCell>
                <TableCell>{compactNumber(totals.input_tokens)}</TableCell>
                <TableCell>{compactNumber(totals.output_tokens)}</TableCell>
                <TableCell>{compactNumber(totals.cached_input_tokens)}</TableCell>
                <TableCell>{compactNumber(totals.reasoning_output_tokens)}</TableCell>
                <TableCell>{totals.conversations}</TableCell>
                <TableCell>{formatUsd(totals.cost_usd)}</TableCell>
              </TableRow>
              {[...rows].reverse().map((row) => {
                const isZero = !(row.total_tokens || 0);
                const cost = costByDate.has(row.date) ? formatUsd(costByDate.get(row.date)!) : "—";
                return (
                  <TableRow
                    key={row.date}
                    className={cn("border-hairline", isZero && "opacity-40")}
                  >
                    <TableCell className="!tabular-nums">{row.date}</TableCell>
                    <TableCell>{compactNumber(row.total_tokens || 0)}</TableCell>
                    <TableCell>{compactNumber(row.input_tokens || 0)}</TableCell>
                    <TableCell>{compactNumber(row.output_tokens || 0)}</TableCell>
                    <TableCell>{compactNumber(row.cached_input_tokens || 0)}</TableCell>
                    <TableCell>{compactNumber(row.reasoning_output_tokens || 0)}</TableCell>
                    <TableCell>{row.conversations || 0}</TableCell>
                    <TableCell>{cost}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
