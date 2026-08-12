import { useState } from "react";

import { ConfigSection } from "@/components/shared/form/config-section";
import { ConfigActionBar } from "@/components/shared/form/config-action-bar";
import { Button } from "@/components/ui/shadcn/button";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { useConfigForm } from "@/hooks/use-config-form";

const MESSAGING_SECTIONS = ["messaging", "voice"] as const;

export function MessagingView() {
  const form = useConfigForm();
  const [isValidating, setIsValidating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  if (form.isLoading) {
    return (
      <PlaceholderView
        title="Messaging"
        eyebrow="Channels · Agents"
        status="loading"
        slots={[<Skeleton key="s1" className="h-48 w-full rounded-lg" />]}
      />
    );
  }

  if (form.error || !form.payload) {
    return (
      <PlaceholderView
        title="Messaging"
        eyebrow="Channels · Agents"
        status="error"
        action={<Button variant="pearl" onClick={() => window.location.reload()}>Retry</Button>}
      />
    );
  }

  const { sections, fields } = form.payload;
  const bySection = (id: string) => fields.filter((f) => f.section === id);

  const handleValidate = async () => {
    setIsValidating(true);
    const result = await form.validate();
    setIsValidating(false);
    return result;
  };

  const handleApply = async () => {
    setIsApplying(true);
    const result = await form.apply();
    setIsApplying(false);
    return result;
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-[820px] space-y-6">
          <div>
            <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
              Channels · Agents
            </p>
            <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Messaging
            </h1>
          </div>

          {MESSAGING_SECTIONS.map((sectionId) => {
            const section = sections.find((s) => s.id === sectionId);
            const sectionFields = bySection(sectionId);
            if (!section || sectionFields.length === 0) return null;

            const headerExtra =
              sectionId === "voice" ? (
                <span className="text-[14px] text-ink-muted-48">Voice notes</span>
              ) : undefined;

            return (
              <ConfigSection
                key={sectionId}
                section={sectionId === "voice" ? { ...section, label: "Voice notes" } : section}
                fields={sectionFields}
                editedValues={form.editedValues}
                onChange={form.setEdited}
                onReset={(key) => form.setEdited(key, "")}
                headerExtra={headerExtra}
              />
            );
          })}
        </div>
      </div>

      <ConfigActionBar
        dirtyCount={form.dirtyCount}
        isApplying={isApplying}
        isValidating={isValidating}
        onValidate={handleValidate}
        onApply={handleApply}
        onRestart={form.restart}
      />
    </div>
  );
}
