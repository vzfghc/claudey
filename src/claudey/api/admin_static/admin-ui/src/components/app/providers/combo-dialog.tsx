import { useState } from "react";
import { Loader2, Plus, Trash2, Check, Copy } from "lucide-react";
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
import { Checkbox } from "@/components/ui/shadcn/checkbox";
import { ModelCombobox } from "@/components/app/config/model-combobox";
import {
  createCombo,
  updateCombo,
  validateCombo,
} from "@/api/client";
import type { Combo, ComboNode, ComboPayload, ComboValidateResult } from "@/api/types";

interface ComboDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  combo?: Combo | null;
  onSaved: () => void;
}

let nodeKey = 0;
function nextNodeKey(): string {
  nodeKey += 1;
  return `node-${nodeKey}`;
}

/** A fallback row plus a stable client key (never sent to the API). */
type NodeRow = ComboNode & { _key: string };

function emptyNode(): NodeRow {
  return { _key: nextNodeKey(), provider_model_ref: "", enabled: true, priority: 0 };
}

function toNodeRow(node: ComboNode): NodeRow {
  return { _key: nextNodeKey(), ...node };
}

function stripNodeKey(row: NodeRow): ComboNode {
  const { _key, ...node } = row;
  void _key;
  return node;
}

export function ComboDialog({ open, onOpenChange, combo, onSaved }: ComboDialogProps) {
  const isEdit = Boolean(combo?.combo_id);
  const [name, setName] = useState(combo?.display_name ?? "");
  const [enabled, setEnabled] = useState(combo?.enabled ?? true);
  const [nodes, setNodes] = useState<NodeRow[]>(
    combo?.nodes?.length ? combo.nodes.map(toNodeRow) : [emptyNode()],
  );
  const [isValidating, setIsValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<ComboValidateResult | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const updateNode = (index: number, patch: Partial<ComboNode>) => {
    setNodes((prev) => prev.map((n, i) => (i === index ? { ...n, ...patch } : n)));
  };

  const addNode = () => {
    setNodes((prev) => [...prev, emptyNode()]);
  };

  const removeNode = (index: number) => {
    setNodes((prev) => prev.filter((_, i) => i !== index));
  };

  const handleValidate = async () => {
    const validNodes = nodes.filter((n) => n.provider_model_ref.trim()).map(stripNodeKey);
    if (!name.trim()) {
      toast.error("A combo name is required");
      return;
    }
    if (validNodes.length === 0) {
      toast.error("Add at least one model node");
      return;
    }
    setIsValidating(true);
    setValidateResult(null);
    try {
      const payload: ComboPayload = {
        display_name: name.trim(),
        nodes: validNodes,
        enabled: true,
      };
      const result = await validateCombo(payload);
      setValidateResult(result);
      if (result.valid) {
        toast.success("Valid — nodes are well-formed provider/model refs");
      } else {
        toast.error(result.error ?? "Invalid node reference");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async () => {
    const validNodes = nodes.filter((n) => n.provider_model_ref.trim()).map(stripNodeKey);
    if (!name.trim()) {
      toast.error("A combo name is required");
      return;
    }
    if (validNodes.length === 0) {
      toast.error("Add at least one model node");
      return;
    }
    setIsSaving(true);
    try {
      const payload: ComboPayload = {
        display_name: name.trim(),
        nodes: validNodes,
        enabled,
      };
      const result = isEdit
        ? await updateCombo(combo!.combo_id, payload)
        : await createCombo(payload);
      toast.success(result.message ?? `Combo ${name} saved`);
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save combo");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit" : "Add"} Fallback Combo</DialogTitle>
          <DialogDescription>
            A combo is a fallback chain of provider/model refs tried in order.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="comboName">Combo Name</Label>
            <Input
              id="comboName"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Flagship"
            />
          </div>

          {isEdit && combo && (
            <div className="flex items-center gap-2 rounded-sm bg-parchment px-3 py-2">
              <Copy className="size-3.5 text-ink-muted-48" />
              <code className="text-[13px] text-ink-muted-48">@combo:{combo.combo_id}</code>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Label>Fallback chain (tried in order)</Label>
            <div className="space-y-2">
              {nodes.map((node, index) => (
                <div key={node._key} className="flex items-center gap-2">
                  <div className="flex-1">
                    <ModelCombobox
                      value={node.provider_model_ref}
                      onChange={(v) => updateNode(index, { provider_model_ref: v })}
                      type="model"
                      placeholder="provider/model"
                    />
                  </div>
                  <label
                    htmlFor={`${node._key}-enabled`}
                    className="flex items-center gap-1.5 text-[13px] text-ink-muted-48"
                  >
                    <Checkbox
                      id={`${node._key}-enabled`}
                      checked={node.enabled}
                      onCheckedChange={(checked) => updateNode(index, { enabled: checked === true })}
                    />
                    enabled
                  </label>
                  <Input
                    type="number"
                    value={node.priority}
                    onChange={(e) => updateNode(index, { priority: Number(e.target.value) || 0 })}
                    className="w-20"
                    aria-label="Priority"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeNode(index)}
                    aria-label="Remove node"
                    className="h-9 w-9 p-0"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
            <Button variant="secondary" size="sm" onClick={addNode} className="w-fit">
              <Plus className="size-3.5" />
              Add node
            </Button>
          </div>

          <label htmlFor="combo-enabled" className="flex items-center gap-2 text-[14px] text-ink">
            <Checkbox
              id="combo-enabled"
              checked={enabled}
              onCheckedChange={(checked) => setEnabled(checked === true)}
            />
            Combo enabled
          </label>

          <div className="flex items-center gap-3">
            <Button variant="secondary" size="sm" onClick={handleValidate} disabled={isValidating}>
              {isValidating ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Validate nodes
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
                  ? "Valid — nodes are well-formed provider/model refs"
                  : `Invalid — ${validateResult.error ?? "bad node reference"}`}
              </span>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Loader2 className="size-3.5 animate-spin" /> : null}
            {isEdit ? "Save Changes" : "Add Combo"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
