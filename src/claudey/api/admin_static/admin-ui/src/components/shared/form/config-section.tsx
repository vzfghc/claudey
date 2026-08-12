import { useState } from "react";

import { ConfigFieldRow } from "@/components/shared/form/config-field";
import { Button } from "@/components/ui/shadcn/button";
import type { ConfigField, ConfigSection } from "@/api/types";

interface ConfigSectionProps {
  section: ConfigSection;
  fields: ConfigField[];
  editedValues: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onReset: (key: string) => void;
  headerExtra?: React.ReactNode;
}

/**
 * ConfigSection — renders a settings section with its fields.
 * Advanced fields are hidden behind a "Show advanced" toggle,
 * mirroring the vanilla admin's .show-advanced pattern.
 * Per design-system.md: section heading uses display-md (34/600/-0.374px),
 * description in caption (14/400) muted ink.
 */
export function ConfigSection({
  section,
  fields,
  editedValues,
  onChange,
  onReset,
  headerExtra,
}: ConfigSectionProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const visibleFields = showAdvanced
    ? fields
    : fields.filter((f) => !f.advanced);

  if (fields.length === 0) return null;

  return (
    <section className="animate-rise-in rounded-lg border border-hairline bg-pearl p-6">
      <header className="flex items-start justify-between gap-4 pb-4">
        <div>
          <h3 className="text-[17px] leading-tight font-semibold tracking-[-0.374px] text-ink">
            {section.label}
          </h3>
          <p className="mt-1 text-[14px] leading-relaxed text-ink-muted-48">
            {section.description}
          </p>
        </div>
        {headerExtra}
      </header>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {visibleFields.map((field) => {
          const value = field.key in editedValues
            ? editedValues[field.key]
            : field.value || (field.type === "optional_model" ? "None" : "");
          const isDirty = field.key in editedValues && value !== (field.value || "");
          return (
            <ConfigFieldRow
              key={field.key}
              field={field}
              value={value}
              onChange={(v) => onChange(field.key, v)}
              onReset={() => onReset(field.key)}
              isDirty={isDirty}
            />
          );
        })}
      </div>

      {fields.some((f) => f.advanced) && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowAdvanced((v) => !v)}
          className="mt-4"
        >
          {showAdvanced ? "Hide advanced" : "Show advanced"}
        </Button>
      )}
    </section>
  );
}
