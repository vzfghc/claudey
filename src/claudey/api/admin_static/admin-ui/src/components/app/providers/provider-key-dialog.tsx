import { useState } from "react";
import { Loader2, KeyRound } from "lucide-react";
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
import { applyConfig } from "@/api/client";
import { wireValue } from "@/lib/config";
import type { ConfigField } from "@/api/types";

interface ProviderKeyDialogProps {
  open: boolean;
  field: ConfigField | null;
  providerName: string;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

/**
 * Single-field dialog for entering/replacing a provider API key. The Providers
 * view surfaces this instead of a dead-end toast so every provider has a real
 * place to put its key. Saves through the same applyConfig wire path as the
 * config form so payloads stay byte-identical.
 */
export function ProviderKeyDialog({
  open,
  field,
  providerName,
  onOpenChange,
  onSaved,
}: ProviderKeyDialogProps) {
  const [value, setValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    if (!field) return;
    const key = field.key.trim();
    if (!key) return;
    const trimmed = value.trim();
    if (!trimmed) {
      toast.error("Enter an API key");
      return;
    }
    setIsSaving(true);
    try {
      const result = await applyConfig({ [key]: wireValue(field, trimmed) });
      if (result.applied) {
        toast.success(`${providerName} API key saved`);
        onSaved();
        onOpenChange(false);
      } else {
        toast.error(result.errors?.[0] ?? "Could not save the API key");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the API key");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="size-4 text-heat" aria-hidden="true" />
            {providerName} API key
          </DialogTitle>
          <DialogDescription>
            {field?.label ?? "Provider"} — keys are stored in the local .env and never shown
            again after saving.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2">
          <Label htmlFor="provider-key">API key</Label>
          <Input
            id="provider-key"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="sk-••••••••••••••••"
            autoComplete="off"
            autoFocus
          />
        </div>

        <DialogFooter>
          <Button variant="pearl" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !value.trim()}>
            {isSaving ? <Loader2 className="size-4 animate-spin" /> : null}
            Save key
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}