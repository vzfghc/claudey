import { useState } from "react";
import { Loader2, Check } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/shadcn/dialog";
import { Input } from "@/components/ui/shadcn/input";
import { Label } from "@/components/ui/shadcn/label";
import { Button } from "@/components/ui/shadcn/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/shadcn/select";
import { validateCustomProvider, createCustomProvider } from "@/api/client";
import type { CustomProviderPayload, CustomProviderValidateResult } from "@/api/types";

interface CustomProviderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CustomProviderDialog({ open, onOpenChange, onCreated }: CustomProviderDialogProps) {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelId, setModelId] = useState("");
  const [providerType, setProviderType] = useState<"openai" | "anthropic">("openai");
  const [isValidating, setIsValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<CustomProviderValidateResult | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const reset = () => {
    setName("");
    setBaseUrl("");
    setApiKey("");
    setModelId("");
    setProviderType("openai");
    setValidateResult(null);
  };

  const handleValidate = async () => {
    if (!baseUrl.trim()) {
      toast.error("Base URL is required");
      return;
    }
    setIsValidating(true);
    setValidateResult(null);
    try {
      const result = await validateCustomProvider({
        type: providerType,
        base_url: baseUrl.trim(),
        api_key: apiKey || undefined,
        model_id: modelId.trim() || null,
      });
      setValidateResult(result);
      if (result.valid) {
        toast.success(result.method === "chat" ? "Chat request OK" : "Models endpoint OK");
      } else {
        toast.error(result.error ?? "Could not connect");
      }
    } catch (err) {
      setValidateResult({ valid: false, error: err instanceof Error ? err.message : "Check failed" });
      toast.error(err instanceof Error ? err.message : "Check failed");
    } finally {
      setIsValidating(false);
    }
  };

  const handleCreate = async () => {
    if (!validateResult?.valid) {
      toast.error("Run Check first to verify the provider connection");
      return;
    }
    if (!name.trim()) {
      toast.error("Provider name is required");
      return;
    }
    setIsCreating(true);
    try {
      const payload: CustomProviderPayload = {
        type: providerType,
        name: name.trim(),
        base_url: baseUrl.trim(),
        api_key: apiKey || undefined,
      };
      const result = await createCustomProvider(payload);
      toast.success(result.message ?? `Provider ${name} added`);
      reset();
      onOpenChange(false);
      onCreated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create provider");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Add {providerType === "openai" ? "OpenAI-compatible" : "Anthropic-compatible"} Provider
          </DialogTitle>
          <DialogDescription>
            Connect a custom provider endpoint. Check the connection before adding.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-col gap-2">
            <Label>Compatibility</Label>
            <Select value={providerType} onValueChange={(v) => setProviderType(v as "openai" | "anthropic")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="openai">OpenAI-compatible</SelectItem>
                <SelectItem value="anthropic">Anthropic-compatible</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="providerName">Provider Name</Label>
            <Input
              id="providerName"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Custom Provider"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="baseUrl">Base URL</Label>
            <Input
              id="baseUrl"
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-xxxxx"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="modelId">Model ID (optional)</Label>
            <Input
              id="modelId"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              placeholder="e.g. gpt-4o-mini"
            />
            <p className="text-[12px] text-ink-muted-48">
              If the provider has no /models endpoint, add a model ID to validate via a chat request.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="secondary" size="sm" onClick={handleValidate} disabled={isValidating}>
              {isValidating ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Check
            </Button>
            {validateResult && (
              <span
                className={
                  validateResult.valid
                    ? "text-[13px] font-semibold text-success"
                    : "text-[13px] font-semibold text-danger"
                }
              >
                {validateResult.valid
                  ? `Valid — ${validateResult.method === "chat" ? "chat request OK" : "models endpoint OK"}`
                  : `Invalid — ${validateResult.error ?? "could not connect"}`}
              </span>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={() => { reset(); onOpenChange(false); }}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleCreate} disabled={isCreating}>
            {isCreating ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Add Provider
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
