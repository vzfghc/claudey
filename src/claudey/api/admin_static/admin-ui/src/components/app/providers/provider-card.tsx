import { useState } from "react";
import { Trash2, Zap } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/shadcn/card";
import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { testProvider, deleteCustomProvider } from "@/api/client";
import type { ProviderStatus, ConfigField } from "@/api/types";

interface ProviderCardProps {
  provider: ProviderStatus;
  primaryField?: ConfigField;
  onConfigure: (fieldKey: string) => void;
  onChanged: () => void;
}

function statusBadgeVariant(status: string): "success" | "warn" | "danger" | "secondary" {
  if (["configured", "reachable", "connected"].includes(status)) return "success";
  if (["offline", "error"].includes(status)) return "danger";
  if (["missing_key", "missing_config", "missing_url", "unknown", "connecting"].includes(status)) return "warn";
  return "secondary";
}

function statusLabel(status: string, label: string): string {
  if (["configured", "reachable"].includes(status)) return "Configured";
  if (status === "connected") return "Connected";
  if (status === "disconnected") return "Not connected";
  if (status === "missing_key") return "Missing key";
  if (status === "missing_config") return "Missing configuration";
  if (status === "missing_url") return "Missing URL";
  return label || "Not configured";
}

const FALLBACK_LOGO = "/admin/assets/logos/_fallback.svg";

function providerLogoSrc(providerId: string): string {
  if (providerId.startsWith("custom_")) return FALLBACK_LOGO;
  return `/admin/assets/logos/${providerId}.svg`;
}

export function ProviderCard({ provider, primaryField, onConfigure, onChanged }: ProviderCardProps) {
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const isConfigured = ["configured", "reachable"].includes(provider.status);
  const fieldKey = primaryField?.key ?? provider.configuration?.split(" + ")[0]?.trim();

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testProvider(provider.provider_id);
      if (result.ok) {
        setTestResult(`${result.models?.length ?? 0} models`);
        toast.success(`${provider.display_name}: ${result.models?.length ?? 0} models found`);
      } else {
        setTestResult(result.error_type ?? "Failed");
        toast.error(`${provider.display_name}: ${result.error_type ?? "test failed"}`);
      }
    } catch (err) {
      setTestResult("Error");
      toast.error(err instanceof Error ? err.message : "Test failed");
    } finally {
      setIsTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete custom provider "${provider.display_name}"?`)) return;
    try {
      await deleteCustomProvider(provider.provider_id);
      toast.success("Custom provider deleted");
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete provider");
    }
  };

  return (
    <Card className="gap-3 p-4">
      <CardHeader>
        <div className="flex items-center gap-3">
          <img
            src={providerLogoSrc(provider.provider_id)}
            alt=""
            width={32}
            height={32}
            loading="lazy"
            className="size-8 shrink-0 rounded-sm"
            onError={(e) => {
              const img = e.currentTarget;
              img.onerror = null;
              img.src = FALLBACK_LOGO;
            }}
          />
          <CardTitle className="text-[15px]">{provider.display_name}</CardTitle>
        </div>
        <CardAction>
          <Badge variant={statusBadgeVariant(provider.status)}>
            {statusLabel(provider.status, provider.label)}
          </Badge>
        </CardAction>
      </CardHeader>

      {provider.kind === "custom" && (
        <CardContent className="flex items-center justify-between gap-2">
          <Badge variant="accent">
            {provider.compatible === "anthropic" ? "Anthropic" : "OpenAI"}
          </Badge>
          <Button variant="secondary" size="sm" onClick={handleDelete}>
            <Trash2 className="size-3.5" />
            Delete
          </Button>
        </CardContent>
      )}

      {provider.kind === "remote" && (
        <CardContent className="flex items-center justify-end gap-2">
          {isConfigured ? (
            <>
              {testResult && (
                <span className="text-[12px] text-ink-muted-48">{testResult}</span>
              )}
              <Button variant="secondary" size="sm" onClick={handleTest} disabled={isTesting}>
                <Zap className="size-3.5" />
                {isTesting ? "Testing…" : "Test"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fieldKey && onConfigure(fieldKey)}
              >
                Switch key
              </Button>
            </>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fieldKey && onConfigure(fieldKey)}
            >
              Configure
            </Button>
          )}
        </CardContent>
      )}

      {provider.kind === "local" && (
        <CardContent>
          <p className="truncate text-[12px] text-ink-muted-48" title={provider.base_url}>
            {provider.base_url || "No URL configured"}
          </p>
        </CardContent>
      )}
    </Card>
  );
}
