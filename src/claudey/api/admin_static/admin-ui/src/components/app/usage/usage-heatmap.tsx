import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/shadcn/card";
import { cn } from "@/lib/utils";

interface HeatWeek {
  start: string;
  days: number[];
}

interface UsageHeatmapProps {
  weeks: HeatWeek[];
}

const USAGE_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function usageHeatLevels(weeks: HeatWeek[]): number[] {
  const all = weeks.flatMap((w) => w.days);
  const sorted = [...all].sort((a, b) => a - b);
  if (sorted.length === 0) return [0, 1, 2, 3, 4];
  const max = sorted[sorted.length - 1] || 1;
  return [0, max * 0.1, max * 0.3, max * 0.6, max * 0.9].map((v) => Math.ceil(v));
}

function levelFor(value: number, thresholds: number[]): number {
  for (let i = thresholds.length - 1; i >= 0; i--) {
    if (value >= thresholds[i]) return i;
  }
  return 0;
}

const HEAT_COLORS = [
  "bg-black/[0.04]",
  "bg-heat/15",
  "bg-heat/30",
  "bg-heat/55",
  "bg-heat/80",
];

export function UsageHeatmap({ weeks }: UsageHeatmapProps) {
  const [tooltip, setTooltip] = useState<{ date: string; value: number; x: number; y: number } | null>(null);

  if (!weeks.length) return null;

  const thresholds = usageHeatLevels(weeks);
  const monthLabels: Array<{ col: number; label: string }> = [];
  let prevMonth = -1;
  weeks.forEach((week, i) => {
    const date = new Date(`${week.start}T00:00:00Z`);
    const month = date.getUTCMonth();
    if (month !== prevMonth) {
      monthLabels.push({ col: i + 1, label: USAGE_MONTHS[month] });
      prevMonth = month;
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Activity — last 52 weeks</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative overflow-x-auto">
          {/* Month labels */}
          <div className="mb-1 grid gap-[3px] pl-7" style={{ gridTemplateColumns: `repeat(${weeks.length}, 12px)` }}>
            {monthLabels.map((m) => (
              <span
                key={m.col}
                className="text-[10px] text-ink-muted-48"
                style={{ gridColumn: `${m.col} / span 2` }}
              >
                {m.label}
              </span>
            ))}
          </div>

          <div className="flex gap-[3px]">
            {/* Day labels */}
            <div className="flex flex-col gap-[3px] pr-1">
              {["Mon", "Wed", "Fri"].map((d) => (
                <span key={d} className="h-[12px] text-[10px] leading-[12px] text-ink-muted-48">
                  {d}
                </span>
              ))}
            </div>

            {/* Grid */}
            <div
              className="relative grid gap-[3px]"
              style={{ gridTemplateColumns: `repeat(${weeks.length}, 12px)` }}
              role="img"
              aria-label="Token usage heatmap over the last 52 weeks"
              onMouseLeave={() => setTooltip(null)}
            >
              {weeks.map((week, weekIdx) => (
                <div key={weekIdx} className="flex flex-col gap-[3px]">
                  {week.days.map((value, dayIdx) => {
                    const date = new Date(`${week.start}T00:00:00Z`);
                    date.setUTCDate(date.getUTCDate() + dayIdx);
                    const level = levelFor(value, thresholds);
                    return (
                      <div
                        key={dayIdx}
                        className={cn("size-[12px] rounded-[2px] transition-colors duration-150", HEAT_COLORS[level])}
                        data-date={date.toISOString().slice(0, 10)}
                        data-value={value}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          const container = e.currentTarget.closest("[role=img]")?.getBoundingClientRect();
                          setTooltip({
                            date: date.toISOString().slice(0, 10),
                            value,
                            x: rect.left - (container?.left ?? 0) + 6,
                            y: rect.top - (container?.top ?? 0) - 4,
                          });
                        }}
                      />
                    );
                  })}
                </div>
              ))}

              {tooltip && (
                <div
                  className="pointer-events-none absolute z-20 rounded-sm bg-ink px-2 py-1 text-[11px] whitespace-nowrap text-white shadow-float"
                  style={{ left: tooltip.x, top: tooltip.y - 28 }}
                >
                  {tooltip.value > 0 ? tooltip.value.toLocaleString() : "No"} tokens · {tooltip.date}
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
