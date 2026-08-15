import { useState } from "react";
import { Trash2, Zap } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";
import { testProvider, deleteCustomProvider } from "@/api/client";
import type { ProviderStatus, ConfigField } from "@/api/types";

interface ProviderRowProps {
  provider: ProviderStatus;
  primaryField?: ConfigField;
  /** Config-key dialog opener — omit for rows that cannot be configured (custom). */
  onConfigure?: (fieldKey: string) => void;
  onChanged: () => void;
}

type StatusTone = "success" | "warn" | "danger" | "secondary";

function statusDotClass(tone: StatusTone): string {
  if (tone === "success") return "bg-success";
  if (tone === "danger") return "bg-danger";
  if (tone === "warn") return "bg-warn";
  return "bg-ink-muted-48/40";
}

function statusTone(status: string): StatusTone {
  if (["configured", "reachable", "connected"].includes(status)) return "success";
  if (["offline", "error"].includes(status)) return "danger";
  if (["missing_key", "missing_config", "missing_url", "unknown", "connecting"].includes(status))
    return "warn";
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

/**
 * ProviderRow — Apple-style settings line. A hairline-divided row (logo · name ·
 * secondary meta · status · actions) instead of a boxed card. Rendered inside a
 * ProviderList that owns the dividers and the single rounded container.
 */
export function ProviderCard({ provider, primaryField, onConfigure, onChanged }: ProviderRowProps) {
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const tone = statusTone(provider.status);
  const isConfigured = ["configured", "reachable"].includes(provider.status);
  const fieldKey = primaryField?.key;

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

  // Secondary line: kind-specific metadata. Remote rows show the configuration
  // summary — the live status already lives in the dot+label on the right, so
  // rendering statusLabel() here duplicated it on every remote row.
  const secondary =
    provider.kind === "local"
      ? provider.base_url || "No URL configured"
      : provider.kind === "custom"
        ? provider.compatible === "anthropic"
          ? "Anthropic-compatible"
          : "OpenAI-compatible"
        : provider.configuration || provider.label;

  return (
    <div className="group flex items-center gap-4 px-4 py-3 transition-colors duration-200 hover:bg-parchment/60">
      <img
        src={providerLogoSrc(provider.provider_id)}
        alt=""
        width={28}
        height={28}
        loading="lazy"
        className="size-7 shrink-0 rounded-md"
        onError={(e) => {
          const img = e.currentTarget;
          img.onerror = null;
          img.src = FALLBACK_LOGO;
        }}
      />

      <div className="min-w-0 flex-1">
        <p className="truncate text-[15px] leading-tight font-semibold tracking-[-0.2px] text-ink">
          {provider.display_name}
        </p>
        <p className="truncate text-[12px] leading-snug text-ink-muted-48" title={secondary}>
          {secondary}
        </p>
      </div>

      <span className="hidden shrink-0 items-center gap-1.5 sm:flex">
        <span className={`size-1.5 rounded-full ${statusDotClass(tone)}`} aria-hidden="true" />
        <span className="text-[12px] text-ink-muted-48">
          {statusLabel(provider.status, provider.label)}
        </span>
      </span>

      <div className="flex shrink-0 items-center gap-1.5">
        {provider.kind === "custom" && (
          <Button variant="ghost" size="sm" onClick={handleDelete} aria-label="Delete provider">
            <Trash2 className="size-3.5" />
          </Button>
        )}

        {provider.kind === "remote" &&
          (isConfigured ? (
            <>
              {testResult && (
                <span className="hidden text-[12px] text-ink-muted-48 md:inline">{testResult}</span>
              )}
              <Button variant="ghost" size="sm" onClick={handleTest} disabled={isTesting}>
                <Zap className="size-3.5" />
                {isTesting ? "Testing…" : "Test"}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => fieldKey && onConfigure?.(fieldKey)}
              >
                Switch key
              </Button>
            </>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fieldKey && onConfigure?.(fieldKey)}
            >
              Configure
            </Button>
          ))}

        {provider.kind === "custom" && (
          <Badge variant="accent">
            {provider.compatible === "anthropic" ? "Anthropic" : "OpenAI"}
          </Badge>
        )}
      </div>
    </div>
  );
}
