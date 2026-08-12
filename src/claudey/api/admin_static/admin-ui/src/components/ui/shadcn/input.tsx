import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Claudey Input — Apple form field. 40px control, sm radius, hairline border,
 * 2px heat-focus outline on focus. Never the default browser ring.
 * Adapted from shadcn (components/ui/input) onto the claudey tokens.
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "border-hairline placeholder:text-ink-muted-48 h-10 w-full min-w-0 rounded-sm border bg-canvas px-3 text-[14px] text-ink transition-[border-color,box-shadow] ease-default outline-none",
        "focus-visible:border-heat focus-visible:ring-2 focus-visible:ring-heat/30",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger aria-invalid:ring-danger/20",
        "[&::placeholder]:text-[13px]",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
