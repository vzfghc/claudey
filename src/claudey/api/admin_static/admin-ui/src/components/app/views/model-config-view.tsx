import * as React from "react";
import { useState } from "react";
import { RefreshCw, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { ConfigSection } from "@/components/shared/form/config-section";
import { ConfigActionBar } from "@/components/shared/form/config-action-bar";
import { ConfigFieldRow } from "@/components/shared/form/config-field";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/shadcn/card";
import { Button } from "@/components/ui/shadcn/button";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { useConfigForm } from "@/hooks/use-config-form";
import { refreshModels } from "@/api/client";

const ROLE_CARDS = [
  { id: "fallback", label: "Fallback", modelKey: "MODEL", reasoningKey: "REASONING_POLICY", description: "Default used by Claude Code's /model picker. Roles without an override inherit this.", modelLabel: "Model" },
  { id: "fable", label: "Fable", modelKey: "MODEL_FABLE", reasoningKey: "REASONING_FABLE", description: "Override for Fable-tier requests. Empty means use the fallback model.", modelLabel: "Model override" },
  { id: "opus", label: "Opus", modelKey: "MODEL_OPUS", reasoningKey: "REASONING_OPUS", description: "Override for Opus-tier requests. Empty means use the fallback model.", modelLabel: "Model override" },
  { id: "sonnet", label: "Sonnet", modelKey: "MODEL_SONNET", reasoningKey: "REASONING_SONNET", description: "Override for Sonnet-tier requests. Empty means use the fallback model.", modelLabel: "Model override" },
  { id: "haiku", label: "Haiku", modelKey: "MODEL_HAIKU", reasoningKey: "REASONING_HAIKU", description: "Override for Haiku-tier requests. Empty means use the fallback model.", modelLabel: "Model override" },
] as const;

export function ModelConfigView() {
  const form = useConfigForm();
  const [isValidating, setIsValidating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isRefreshingModels, setIsRefreshingModels] = useState(false);

  if (form.isLoading) {
    return (
      <PlaceholderView
        title="Model Config"
        eyebrow="Combo Routes · Fallbacks"
        status="loading"
        slots={[<Skeleton key="s1" className="h-48 w-full rounded-lg" />]}
      />
    );
  }

  if (form.error || !form.payload) {
    return (
      <PlaceholderView
        title="Model Config"
        eyebrow="Combo Routes · Fallbacks"
        status="error"
        action={<Button variant="pearl" onClick={() => window.location.reload()}>Retry</Button>}
      />
    );
  }

  const { sections, fields } = form.payload;
  const bySection = (id: string) => fields.filter((f) => f.section === id);
  const webToolsFields = bySection("web_tools");
  const fieldByKey = (key: string) => fields.find((f) => f.key === key);

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

  const handleRefreshModels = async () => {
    setIsRefreshingModels(true);
    try {
      const result = await refreshModels();
      const failed = result.failed_providers ?? [];
      if (failed.length > 0) {
        toast.warning(`${result.models.length} models available; could not refresh ${failed.join(", ")}`);
      } else {
        toast.success(`${result.models.length} models available`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not refresh models");
    } finally {
      setIsRefreshingModels(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    void handleApply();
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <form onSubmit={handleFormSubmit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-[920px] space-y-6">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
                Combo Routes · Fallbacks
              </p>
              <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
                Model Config
              </h1>
            </div>
            <Button variant="secondary" size="sm" onClick={handleRefreshModels} disabled={isRefreshingModels}>
              {isRefreshingModels ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              Refresh models
            </Button>
          </div>

          {/* Role cards — Fallback/Fable/Opus/Sonnet/Haiku */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {ROLE_CARDS.map((role) => {
              const modelField = fieldByKey(role.modelKey);
              const reasoningField = fieldByKey(role.reasoningKey);
              if (!modelField) return null;
              return (
                <Card key={role.id}>
                  <CardHeader>
                    <CardTitle>{role.label}</CardTitle>
                    <CardDescription>{role.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ConfigFieldRow
                      field={{ ...modelField, label: role.modelLabel }}
                      value={form.editedValues[modelField.key] ?? form.getInputValue(modelField)}
                      onChange={(v) => form.setEdited(modelField.key, v)}
                      onReset={() => form.setEdited(modelField.key, modelField.type === "optional_model" ? "None" : "")}
                      isDirty={modelField.key in form.editedValues}
                    />
                    {reasoningField && (
                      <ConfigFieldRow
                        field={{ ...reasoningField, label: "Reasoning policy" }}
                        value={form.editedValues[reasoningField.key] ?? form.getInputValue(reasoningField)}
                        onChange={(v) => form.setEdited(reasoningField.key, v)}
                        isDirty={reasoningField.key in form.editedValues}
                      />
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Web tools section */}
          {webToolsFields.length > 0 && (
            <ConfigSection
              section={sections.find((s) => s.id === "web_tools") ?? { id: "web_tools", label: "Web Tools", description: "", advanced: false }}
              fields={webToolsFields}
              editedValues={form.editedValues}
              onChange={form.setEdited}
              onReset={(key) => form.setEdited(key, "")}
            />
          )}
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
      </form>
    </div>
  );
}
