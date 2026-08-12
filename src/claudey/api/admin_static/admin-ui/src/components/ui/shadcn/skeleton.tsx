import { cn } from "@/lib/utils";

/** Claudey Skeleton — quiet placeholder block (parchment shimmer). */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-sm bg-black/[0.05] dark:bg-white/10", className)}
      {...props}
    />
  );
}

export { Skeleton };