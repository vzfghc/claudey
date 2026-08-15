import { useCallback, useState } from "react";
import { Plus, Copy, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ProviderCard } from "@/components/app/providers/provider-card";
import { CustomProviderDialog } from "@/components/app/providers/custom-provider-dialog";
import { ComboDialog } from "@/components/app/providers/combo-dialog";
import { ProviderKeyDialog } from "@/components/app/providers/provider-key-dialog";
import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { useJson } from "@/hooks/use-json";
import { deleteCombo } from "@/api/client";
import type { Combo, ConfigField, ConfigPayload } from "@/api/types";

/** Apple grouped-list shell: one rounded hairline container, rows divided by
 *  1px lines. Replaces the boxed-card grid (docs/design-system.md §5, §10). */
function LineGroup({ children }: { children: React.ReactNode }) {
  return (
    <div className="divide-y divide-hairline overflow-hidden rounded-lg border border-hairline bg-canvas">
      {children}
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-[21px] leading-tight font-semibold tracking-[-0.374px] text-ink">
      {children}
    </h2>
  );
}

interface ComboRowProps {
  combo: Combo;
  onEdit: () => void;
  onDelete: () => void;
}

/** ComboRow — same Apple settings line grammar as ProviderRow: name · enabled
 *  badge · node-chain summary · Copy/Edit/Delete actions. */
function ComboRow({ combo, onEdit, onDelete }: ComboRowProps) {
  const chain = combo.nodes
    .filter((node) => node.enabled)
    .sort((a, b) => a.priority - b.priority)
    .map((node) => node.provider_model_ref)
    .join(" → ");
  const summary = chain
    ? `${combo.nodes.length} node${combo.nodes.length === 1 ? "" : "s"} · ${chain}`
    : `${combo.nodes.length} node${combo.nodes.length === 1 ? "" : "s"}`;
  const token = `@combo:${combo.combo_id}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(token);
      toast.success(`Copied ${token}`);
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete combo "${combo.display_name}"?`)) return;
    try {
      await deleteCombo(combo.combo_id);
      toast.success("Combo deleted");
      onDelete();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete combo");
    }
  };

  return (
    <div className="group flex items-center gap-4 px-4 py-3 transition-colors duration-200 hover:bg-parchment/60">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-[15px] leading-tight font-semibold tracking-[-0.2px] text-ink">
            {combo.display_name}
          </p>
          <Badge variant={combo.enabled ? "success" : "secondary"}>
            {combo.enabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
        <p className="truncate text-[12px] leading-snug text-ink-muted-48" title={summary}>
          {summary}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <Button variant="ghost" size="sm" onClick={handleCopy} aria-label="Copy combo token">
          <Copy className="size-3.5" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onEdit} aria-label="Edit combo">
          <Pencil className="size-3.5" />
        </Button>
        <Button variant="ghost" size="sm" onClick={handleDelete} aria-label="Delete combo">
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

export function ProvidersView() {
  // Bumped by every mutation (save/delete/configure) — passed into useJson as a
  // refetch dependency so the view refetches without remounting (keeps row
  // state like in-flight test results, and scroll position).
  const [reloadKey, setReloadKey] = useState(0);
  const config = useJson<ConfigPayload>("/admin/api/config", reloadKey);
  const combosRes = useJson<{ combos: Combo[] }>("/admin/api/combos", reloadKey);
  const [showCustomDialog, setShowCustomDialog] = useState(false);
  const [comboDialogOpen, setComboDialogOpen] = useState(false);
  const [editingCombo, setEditingCombo] = useState<Combo | null>(null);
  const [keyDialogField, setKeyDialogField] = useState<ConfigField | null>(null);
  const [keyDialogProvider, setKeyDialogProvider] = useState("");

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  if (config.isLoading) {
    return (
      <PlaceholderView
        title="Providers"
        eyebrow="Connections · Keys · Status"
        status="loading"
        slots={[
          <div key="list" className="overflow-hidden rounded-lg border border-hairline">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-[58px] rounded-none" />
            ))}
          </div>,
        ]}
      />
    );
  }

  if (config.error || !config.data) {
    return (
      <PlaceholderView
        title="Providers"
        eyebrow="Connections · Keys · Status"
        status="error"
        action={<Button variant="pearl" onClick={() => window.location.reload()}>Retry</Button>}
      />
    );
  }

  const providers = config.data.provider_status ?? [];
  const combos = combosRes.data?.combos ?? [];
  const fields = config.data.fields ?? [];
  const fieldByKey = (key: string) => fields.find((f) => f.key === key);

  const openKeyDialog = (fieldKey: string, providerName: string) => {
    const field = fieldByKey(fieldKey);
    if (!field) {
      toast.error(`No config field found for ${fieldKey}`);
      return;
    }
    setKeyDialogField(field);
    setKeyDialogProvider(providerName);
  };

  const remoteAndLocal = providers.filter(
    (p) => p.kind !== "connected_account" && p.kind !== "custom",
  );
  const custom = providers.filter((p) => p.kind === "custom");

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-[880px] space-y-10">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
              Connections · Keys · Status
            </p>
            <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Providers
            </h1>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setShowCustomDialog(true)}>
            <Plus className="size-3.5" />
            Custom Provider
          </Button>
        </div>

        {/* Providers — Apple grouped-list */}
        <section>
          <SectionHead>
            {remoteAndLocal.length} provider{remoteAndLocal.length === 1 ? "" : "s"}
          </SectionHead>
          <LineGroup>
            {remoteAndLocal.map((provider) => {
              const primaryKey = provider.configuration?.split(" + ")[0]?.trim();
              const primaryField = primaryKey ? fieldByKey(primaryKey) : undefined;
              return (
                <ProviderCard
                  key={provider.provider_id}
                  provider={provider}
                  primaryField={primaryField}
                  onConfigure={(key) => openKeyDialog(key, provider.display_name)}
                  onChanged={reload}
                />
              );
            })}
          </LineGroup>
        </section>

        {custom.length > 0 && (
          <section>
            <SectionHead>Custom Providers</SectionHead>
            <LineGroup>
              {custom.map((provider) => (
                <ProviderCard
                  key={provider.provider_id}
                  provider={provider}
                  onChanged={reload}
                />
              ))}
            </LineGroup>
          </section>
        )}

        {/* Combos */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <SectionHead>Fallback Combos</SectionHead>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setEditingCombo(null);
                setComboDialogOpen(true);
              }}
            >
              <Plus className="size-3.5" />
              Add Combo
            </Button>
          </div>

          {combosRes.error ? (
            <LineGroup>
              <div className="flex items-center justify-between gap-4 px-4 py-4">
                <p className="text-[14px] text-danger">
                  Failed to load combos — {combosRes.error}
                </p>
                <Button variant="ghost" size="sm" onClick={reload}>
                  Retry
                </Button>
              </div>
            </LineGroup>
          ) : combos.length === 0 ? (
            <LineGroup>
              <p className="px-4 py-4 text-[14px] text-ink-muted-48">
                No fallback combos yet. Add one above, then reference it from the
                Fallback tier in Model Config with its @combo:&lt;id&gt; token.
              </p>
            </LineGroup>
          ) : (
            <LineGroup>
              {combos.map((combo) => (
                <ComboRow
                  key={combo.combo_id}
                  combo={combo}
                  onEdit={() => {
                    setEditingCombo(combo);
                    setComboDialogOpen(true);
                  }}
                  onDelete={reload}
                />
              ))}
            </LineGroup>
          )}
        </section>
      </div>

      <CustomProviderDialog
        open={showCustomDialog}
        onOpenChange={setShowCustomDialog}
        onCreated={reload}
      />
      <ComboDialog
        open={comboDialogOpen}
        onOpenChange={setComboDialogOpen}
        combo={editingCombo}
        onSaved={reload}
      />
      <ProviderKeyDialog
        open={keyDialogField !== null}
        field={keyDialogField}
        providerName={keyDialogProvider}
        onOpenChange={(open) => {
          if (!open) setKeyDialogField(null);
        }}
        onSaved={reload}
      />
    </div>
  );
}
