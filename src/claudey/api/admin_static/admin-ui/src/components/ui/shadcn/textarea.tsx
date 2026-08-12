import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Claudey Textarea — Apple multi-line form field, same grammar as Input.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-hairline placeholder:text-ink-muted-48 flex min-h-20 w-full resize-y rounded-sm border bg-canvas px-3 py-2 text-[14px] text-ink transition-[border-color,box-shadow] ease-default outline-none",
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

export { Textarea };