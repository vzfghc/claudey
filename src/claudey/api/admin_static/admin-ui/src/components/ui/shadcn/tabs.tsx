"use client";

import * as React from "react";

import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

/**
 * Claudey Tabs — Apple segment control. Parchment surface, rounded-sm tabs,
 * heat accent for active. No heavy borders.
 * Adapted from shadcn (components/ui/tabs) onto the claudey tokens.
 */
function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root data-slot="tabs" className={cn("flex flex-col gap-2", className)} {...props} />;
}

function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "bg-parchment inline-flex h-9 w-fit items-center justify-center gap-1 rounded-sm p-1 shadow-card",
        className,
      )}
      {...props}
    />
  );
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "data-[state=active]:bg-canvas data-[state=active]:text-heat data-[state=active]:shadow-card dark:data-[state=active]:text-heat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat-focus data-[state=active]:border-transparent text-ink-muted-48 inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-sm border border-transparent px-3 py-1 text-[13px] font-semibold whitespace-nowrap transition-[color,background-color,box-shadow] duration-200 ease-default disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content data-slot="tabs-content" className={cn("flex-1 outline-none", className)} {...props} />;
}

export { Tabs, TabsList, TabsTrigger, TabsContent };