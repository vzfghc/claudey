import * as React from "react";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Claudey Badge — small status chip. Apple 13px weight-600 label, pill radius.
 * Status colors are semantic-only (never interactive chrome) per the design
 * system: success/warn/danger/info map to their tokens.
 */
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-pill border px-2.5 py-[3px] text-[12px] font-semibold whitespace-nowrap transition-[color,background-color,border-color] duration-200 ease-default [&>svg]:pointer-events-none [&>svg]:size-3",
  {
    variants: {
      variant: {
        // quiet neutral — ink-muted on parchment
        secondary: "border-transparent bg-parchment text-ink-muted-48",
        // outline — hairline + ink (default)
        outline: "border-hairline bg-transparent text-ink",
        // heat accent — for brand-adjacent status
        accent: "border-transparent bg-heat/10 text-heat",
        // semantic (non-interactive)
        success: "border-transparent bg-success/12 text-success",
        warn: "border-transparent bg-warn/15 text-warn",
        danger: "border-transparent bg-danger/12 text-danger",
        info: "border-transparent bg-info/12 text-info",
        // dark tile badge (used inside the beam / on tile surfaces)
        tile: "border-white/15 bg-white/10 text-white",
      },
    },
    defaultVariants: {
      variant: "outline",
    },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";

  return <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
