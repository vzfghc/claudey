import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Claudey Button — the five Apple grammars with heat substituted for blue.
 * Preserved Apple rules: `transform: scale(0.95)` press, 2px heat-focus ring,
 * pill radius for action signals, no decorative shadows on buttons.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-pill font-body font-normal select-none transition-[background-color,color,border-color,box-shadow,transform] duration-200 ease-default focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat-focus disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 active:scale-[0.98]",
  {
    variants: {
      variant: {
        // button-primary — the signature heat action. 17px body, full pill.
        primary: "bg-heat text-white hover:bg-heat-focus shadow-card",
        // button-secondary-pill — ghost pill with the single accent.
        secondary:
          "bg-transparent text-heat border border-heat/60 hover:border-heat hover:text-heat-focus",
        // button-store-hero — larger primary, weight 300 (apple button-large).
        hero: "bg-heat text-white hover:bg-heat-focus text-[18px] font-light shadow-card",
        // button-dark-utility — ink fill, sm radius.
        utility: "bg-ink text-white hover:bg-heat rounded-sm text-[14px]",
        // button-pearl-capsule — near-white fill, md radius, soft ring not line.
        pearl:
          "bg-pearl text-ink-muted-48 rounded-md ring-3 ring-divider-soft hover:text-ink",
        // text-link — no chrome, just the accent.
        ghost: "text-heat hover:text-heat-focus",
      },
      size: {
        default: "h-11 px-[22px] py-[11px] text-[17px]",
        sm: "h-9 px-[15px] py-2 text-[14px]",
        lg: "h-13 px-[28px] py-3.5 text-[18px]",
        icon: "size-11 p-2 rounded-full",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export { buttonVariants };