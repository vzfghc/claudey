"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type Bar<T> = T & {
  key?: string;
  href?: string;
  value: number;
  name: string;

  /** Optional class applied to this bar's fill element, overrides `barClassName`. */
  barClassName?: string;
};

interface BarListProps<T = unknown> extends React.ComponentProps<"div"> {
  data: Bar<T>[];
  valueFormatter?: (value: number) => string;
  showAnimation?: boolean;
  onValueChange?: (payload: Bar<T>) => void;
  sortOrder?: "ascending" | "descending" | "none";

  /** Class applied to every bar fill element. Per-item `barClassName` takes precedence. */
  barClassName?: string;

  /** Class applied to the label text inside each bar. */
  labelClassName?: string;

  /** Gap in pixels between bars. Default: 6 */
  barGap?: number;

  /** Height in pixels of each bar row. Default: 32 */
  barHeight?: number;
}

function BarListInner<T>(
  {
    data = [],
    valueFormatter = (value: number) => value.toString(),
    showAnimation = false,
    onValueChange,
    sortOrder = "descending",
    barClassName,
    labelClassName,
    barGap = 6,
    barHeight = 32,
    className,
    ...props
  }: BarListProps<T>,
  forwardedRef: React.ForwardedRef<HTMLDivElement>
) {
  const Component = onValueChange ? "button" : "div";

  const sortedData = React.useMemo(() => {
    if (sortOrder === "none") {
      return data;
    }

    return [...data].sort((a, b) => {
      return sortOrder === "ascending" ? a.value - b.value : b.value - a.value;
    });
  }, [data, sortOrder]);

  const widths = React.useMemo(() => {
    const maxValue = Math.max(...sortedData.map((item) => item.value), 0);

    return sortedData.map((item) =>
      item.value === 0
        ? 0
        : Math.max((item.value / maxValue) * 100, 2)
    );
  }, [sortedData]);

  return (
    <div
      ref={forwardedRef}
      data-slot="bar-list"
      className={cn("flex justify-between space-x-6", className)}
      aria-sort={sortOrder}
      {...props}
    >
      <div
        className="relative w-full"
        style={{ display: "flex", flexDirection: "column", gap: barGap }}
      >
        {sortedData.map((item, index) => (
          <Component
            key={item.key ?? item.name}
            onClick={() => {
              onValueChange?.(item);
            }}
            style={{ height: barHeight }}
            className={cn(
              "group relative w-full rounded-sm",
              "flex items-center",
              onValueChange
                ? ["cursor-pointer", "hover:bg-muted", "transition-colors"]
                : []
            )}
          >
            <div
              data-slot="bar-list-bar"
              className={cn(
                "rounded-sm transition-all",
                "absolute inset-y-0 left-0",
                "bg-primary/20",
                onValueChange ? "group-hover:bg-primary/30" : "",
                {
                  "duration-[800ms]": showAnimation,
                },
                barClassName,
                item.barClassName
              )}
              style={{ width: `${widths[index]}%` }}
            />
            <div data-slot="bar-list-label" className="relative z-10 flex min-w-0 px-2">
              {item.href ? (
                <a
                  href={item.href}
                  className={cn(
                    "truncate rounded-sm text-sm whitespace-nowrap",
                    "text-foreground",
                    "hover:underline hover:underline-offset-2",
                    labelClassName
                  )}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(event) => event.stopPropagation()}
                >
                  {item.name}
                </a>
              ) : (
                <p
                  className={cn(
                    "truncate text-sm whitespace-nowrap",
                    "text-foreground",
                    labelClassName
                  )}
                >
                  {item.name}
                </p>
              )}
            </div>
          </Component>
        ))}
      </div>
      <div
        style={{ display: "flex", flexDirection: "column", gap: barGap }}
      >
        {sortedData.map((item) => (
          <div
            key={item.key ?? item.name}
            data-slot="bar-list-value"
            style={{ height: barHeight }}
            className="flex items-center justify-end"
          >
            <p className={cn("truncate text-sm leading-none whitespace-nowrap", "text-foreground")}>
              {valueFormatter(item.value)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

BarListInner.displayName = "BarList";

const BarList = React.forwardRef(BarListInner) as <T>(
  p: BarListProps<T> & { ref?: React.ForwardedRef<HTMLDivElement> }
) => ReturnType<typeof BarListInner>;

export { BarList, type BarListProps };