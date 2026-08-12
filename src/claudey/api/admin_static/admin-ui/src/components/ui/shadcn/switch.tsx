"use client";

import * as React from "react";

import * as SwitchPrimitive from "@radix-ui/react-switch";

import { cn } from "@/lib/utils";

/**
 * Claudey Switch — Apple toggle. Heat thumb on the checked state, hairline
 * track when off. Used for boolean config fields (semantic status is separate).
 */
function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat-focus peer relative inline-flex h-[26px] w-[46px] shrink-0 cursor-pointer items-center rounded-full border border-transparent transition-colors ease-default",
        "data-[state=checked]:bg-heat data-[state=unchecked]:bg-black/[0.12]",
        "dark:data-[state=unchecked]:bg-white/20",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block size-[22px] rounded-full bg-canvas shadow-card transition-transform ease-default",
          "translate-x-0.5 data-[state=checked]:translate-x-[22px]",
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch };