import { Check, Loader2, RotateCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/shadcn/button";
import { Badge } from "@/components/ui/shadcn/badge";

interface ConfigActionBarProps {
  dirtyCount: number;
  isApplying: boolean;
  isValidating: boolean;
  onValidate: () => Promise<boolean>;
  onApply: () => Promise<boolean>;
  onRestart: () => Promise<void>;
}

/**
 * ConfigActionBar — sticky bottom bar with dirty count, validate, apply, restart.
 * Mirrors the vanilla admin's #actionBar / #dirtyState / #applyButton / #restartButton.
 * Per design-system.md: heat primary for apply, secondary-pill for validate,
 * dark-utility for restart; pill radius for actions.
 */
export function ConfigActionBar({
  dirtyCount,
  isApplying,
  isValidating,
  onValidate,
  onApply,
  onRestart,
}: ConfigActionBarProps) {
  const handleValidate = async () => {
    const valid = await onValidate();
    if (valid) {
      toast.success("Config shape is valid");
    } else {
      toast.error("Config validation failed — check field values");
    }
  };

  const handleApply = async () => {
    if (dirtyCount === 0) return;
    const applied = await onApply();
    if (applied) {
      toast.success("Applied");
    } else {
      toast.error("Apply failed — check validation errors");
    }
  };

  const handleRestart = async () => {
    toast.loading("Restarting server…");
    await onRestart();
    toast.success("Restart requested");
  };

  return (
    <div className="sticky bottom-0 left-0 z-30 flex items-center justify-between gap-4 border-t border-hairline bg-canvas/90 px-6 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        {dirtyCount === 0 ? (
          <Badge variant="secondary">No changes</Badge>
        ) : (
          <Badge variant="accent">
            {dirtyCount} unsaved change{dirtyCount === 1 ? "" : "s"}
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleValidate}
          disabled={isValidating || dirtyCount === 0}
        >
          {isValidating ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
          Validate
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={handleApply}
          disabled={isApplying || dirtyCount === 0}
        >
          {isApplying ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
          Apply
        </Button>
        <Button variant="utility" size="sm" onClick={handleRestart}>
          <RotateCw className="size-3.5" />
          Restart
        </Button>
      </div>
    </div>
  );
}
