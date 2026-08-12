import { useCallback, useState } from "react";
import { Plus, Copy, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ProviderCard } from "@/components/app/providers/provider-card";
import { CustomProviderDialog } from "@/components/app/providers/custom-provider-dialog";
import { ComboDialog } from "@/components/app/providers/combo-dialog";
import { ProviderBeam, type BeamProvider } from "@/components/app/providers/provider-beam";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/shadcn/card";
import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { PlaceholderView } from "@/components/app/views/placeholder-view";
import { useJson } from "@/hooks/use-json";
import { deleteCombo } from "@/api/client";
import type { Combo, ConfigPayload } from "@/api/types";

export function ProvidersView() {
  const config = useJson<ConfigPayload>("/admin/api/config");
  const combosRes = useJson<{ combos: Combo[] }>("/admin/api/combos");
  const [showCustomDialog, setShowCustomDialog] = useState(false);
  const [comboDialogOpen, setComboDialogOpen] = useState(false);
  const [editingCombo, setEditingCombo] = useState<Combo | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  if (config.isLoading) {
    return (
      <PlaceholderView
        title="Providers"
        eyebrow="Connections · Keys · Status"
        status="loading"
        slots={[
          <div key="grid" className="grid grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-lg" />
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

  const remoteAndLocal = providers.filter(
    (p) => p.kind !== "connected_account" && p.kind !== "custom",
  );
  const custom = providers.filter((p) => p.kind === "custom");

  // All non-connected providers become beam nodes (keeps the diagram lively
  // even before keys are set; custom providers share the fallback logo).
  const beamProviders: BeamProvider[] = [...remoteAndLocal, ...custom].map((p) => ({
    id: p.provider_id,
    name: p.display_name,
    logo: p.provider_id.startsWith("custom_")
      ? "/admin/assets/logos/_fallback.svg"
      : `/admin/assets/logos/${p.provider_id}.svg`,
  }));

  return (
    <div key={reloadKey} className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-[1080px] space-y-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
              Connections · Keys · Status
            </p>
            <h1 className="mt-1 text-[34px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Providers
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowCustomDialog(true)}>
              <Plus className="size-3.5" />
              Custom Provider
            </Button>
          </div>
        </div>

        {/* Routing diagram — re-homed provider beam */}
        <section>
          <h2 className="mb-4 text-[21px] leading-tight font-semibold tracking-[-0.374px] text-ink">
            Routing
          </h2>
          <Card>
            <CardContent className="p-0">
              <ProviderBeam providers={beamProviders} />
            </CardContent>
          </Card>
        </section>

        {/* Provider grid */}
        <section>
          <h2 className="mb-4 text-[21px] leading-tight font-semibold tracking-[-0.374px] text-ink">
            {remoteAndLocal.length} provider{remoteAndLocal.length === 1 ? "" : "s"}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {remoteAndLocal.map((provider) => {
              const primaryKey = provider.configuration?.split(" + ")[0]?.trim();
              const primaryField = primaryKey ? fieldByKey(primaryKey) : undefined;
              return (
                <ProviderCard
                  key={provider.provider_id}
                  provider={provider}
                  primaryField={primaryField}
                  onConfigure={(key) => {
                    toast.info(`Configure ${key} in the Model Config view`);
                  }}
                  onChanged={reload}
                />
              );
            })}
          </div>
        </section>

        {/* Custom providers */}
        {custom.length > 0 && (
          <section>
            <h2 className="mb-4 text-[21px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Custom Providers
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {custom.map((provider) => (
                <ProviderCard
                  key={provider.provider_id}
                  provider={provider}
                  onConfigure={() => {}}
                  onChanged={reload}
                />
              ))}
            </div>
          </section>
        )}

        {/* Combos */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[21px] leading-tight font-semibold tracking-[-0.374px] text-ink">
              Fallback Combos
            </h2>
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

          {combos.length === 0 ? (
            <Card>
              <CardContent>
                <p className="text-[14px] text-ink-muted-48">
                  No fallback combos yet. Add one above, then reference it from the
                  Fallback tier in Model Config with its @combo:&lt;id&gt; token.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {combos.map((combo) => (
                <ComboCard
                  key={combo.combo_id}
                  combo={combo}
                  onEdit={() => {
                    setEditingCombo(combo);
                    setComboDialogOpen(true);
                  }}
                  onDelete={reload}
                />
              ))}
            </div>
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
    </div>
  );
}

function ComboCard({
  combo,
  onEdit,
  onDelete,
}: {
  combo: Combo;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(`@combo:${combo.combo_id}`);
      toast.success(`Copied @combo:${combo.combo_id}`);
    } catch {
      toast.error(`Copy failed — note @combo:${combo.combo_id}`);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete fallback combo "${combo.display_name}"?`)) return;
    try {
      await deleteCombo(combo.combo_id);
      toast.success("Combo deleted");
      onDelete();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete combo");
    }
  };

  return (
    <Card className="gap-3 p-4">
      <CardHeader>
        <CardTitle className="text-[15px]">{combo.display_name}</CardTitle>
        <CardAction>
          <Badge variant={combo.enabled ? "success" : "secondary"}>
            {combo.enabled ? "Enabled" : "Disabled"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-[13px] text-ink-muted-48" title={combo.nodes.map((n) => n.provider_model_ref).join(" → ")}>
          {combo.nodes.length} node{combo.nodes.length === 1 ? "" : "s"} ·{" "}
          {combo.nodes.map((n) => n.provider_model_ref).join(" → ")}
        </p>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleCopy} className="font-mono text-[12px]">
            <Copy className="size-3" />
            @combo:{combo.combo_id}
          </Button>
          <div className="flex-1" />
          <Button variant="secondary" size="sm" onClick={onEdit}>
            <Pencil className="size-3.5" />
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDelete} aria-label="Delete combo">
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
