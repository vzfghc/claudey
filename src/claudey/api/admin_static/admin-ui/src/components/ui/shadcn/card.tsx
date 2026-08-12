import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Claudey Card — Apple tool surface: pearl fill, lg radius, one soft shadow.
 * Adapted from shadcn (components/ui/card) onto the claudey tokens
 * (docs/design-system.md §component grammar: cards are quiet, border + pearl).
 */
function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex flex-col gap-6 rounded-lg border border-hairline bg-pearl p-6 shadow-card",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "flex flex-col gap-1.5 px-0 pt-0 pb-2 [&:has([data-slot=card-action])]:flex-row [&:has([data-slot=card-action])]:items-start [&:has([data-slot=card-action])]:justify-between",
        className,
      )}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn(
        "text-[17px] leading-tight font-semibold tracking-[-0.374px] text-ink",
        className,
      )}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-[13px] leading-relaxed text-ink-muted-48", className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn("shrink-0", className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("px-0", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center gap-2 px-0 pt-2", className)}
      {...props}
    />
  );
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent };
