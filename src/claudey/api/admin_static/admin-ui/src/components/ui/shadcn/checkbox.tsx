"use client";

import * as React from "react";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Claudey Checkbox — Apple 20px toggle. Heat checked state, hairline box.
 * Adapted from shadcn (components/ui/checkbox) onto the claudey tokens.
 */
function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer border-hairline data-[state=checked]:bg-heat data-[state=checked]:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat-focus size-5 shrink-0 cursor-pointer rounded-[5px] border bg-canvas transition-[background-color,color,border-color] duration-200 ease-default",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current"
      >
        <Check className="size-3" strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };