import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Scaffold release states for views not rebuilt yet (Phase 3).
 * Per design-system: empty/loading/error states carry personality and lead
 * the user somewhere — never a bare "loading…" or "Something went wrong".
 */
type PlaceholderStatus = "loading" | "empty" | "error" | "coming";

interface PlaceholderViewProps {
  title: string;
  eyebrow?: string;
  status?: PlaceholderStatus;
  message?: string;
  action?: ReactNode;
  slots?: ReactNode[];
}

const STATUS_COPY: Record<PlaceholderStatus, { kicker: string; note: string }> = {
  loading: { kicker: "Syncing", note: "Pulling the latest state from the server." },
  empty: { kicker: "Quiet here", note: "Nothing to show yet — your data will land once you start a conversation." },
  error: { kicker: "Can't reach it", note: "The local API didn't answer. Retry when the server is back." },
  coming: { kicker: "Being rebuilt", note: "This view ships in the scaffold's week-2 pass (Phase 3)." },
};

export function PlaceholderView({
  title,
  eyebrow,
  status = "coming",
  message,
  action,
  slots = [],
}: PlaceholderViewProps) {
  const copy = STATUS_COPY[status];
  return (
    <section className="animate-rise-in mx-auto max-w-[880px] px-6 py-10">
      {eyebrow ? (
        <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
        {title}
      </h1>

      {/* Scaffold status card */}
      <div className="mt-6 flex flex-col gap-5 rounded-lg border border-hairline bg-pearl p-7">
        <div className="flex items-start gap-4">
          <span
            className={cn(
              "mt-1 grid size-9 shrink-0 place-items-center rounded-sm font-mono text-[12px] font-bold uppercase",
              status === "error"
                ? "bg-danger/10 text-danger"
                : status === "loading"
                  ? "bg-heat/10 text-heat"
                  : "bg-tile-1 text-white",
            )}
            aria-hidden="true"
          >
            {status === "loading" ? "…" : status}
          </span>
          <div>
            <h2 className="text-[20px] font-semibold tracking-[-0.374px] text-ink">
              {message ?? copy.kicker}
            </h2>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-muted-48">
              {copy.note}
            </p>
          </div>
        </div>
        {action ? <div className="self-start">{action}</div> : null}
        {slots.filter(Boolean).map((slot, index) => (
          <div key={index} className="mt-4">
            {slot}
          </div>
        ))}
      </div>
    </section>
  );
}