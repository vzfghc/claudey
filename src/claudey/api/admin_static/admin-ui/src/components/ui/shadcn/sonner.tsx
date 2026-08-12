"use client";

import { Toaster as SonnerToaster, type ToasterProps } from "sonner";

import { cn } from "@/lib/utils";

/**
 * Claudey Toaster — sonner mounted with the design tokens.
 * Success/error/warn map to the semantic palette; the heat accent stays for
 * the loading → done transition. Rendered once at the app root.
 */
function Toaster(props: ToasterProps) {
  return (
    <SonnerToaster
      theme="system"
      position="top-right"
      gap={8}
      offset={64}
      toastOptions={{
        classNames: {
          toast: cn(
            "!rounded-lg !border-hairline !bg-canvas !text-ink !shadow-float !font-body !text-[13px] !tracking-[-0.01em]",
          ),
          description: "!text-ink-muted-48",
          loading: "!text-ink",
          success: "!text-ink",
          error: "!text-danger",
          closeButton: "!text-ink-muted-48 hover:!text-ink",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };