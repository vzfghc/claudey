import { Info, RotateCcw } from "lucide-react";

import { Input } from "@/components/ui/shadcn/input";
import { Textarea } from "@/components/ui/shadcn/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/shadcn/select";
import { Switch } from "@/components/ui/shadcn/switch";
import { Label } from "@/components/ui/shadcn/label";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/shadcn/tooltip";
import { Button } from "@/components/ui/shadcn/button";
import { ModelCombobox } from "@/components/app/config/model-combobox";
import { cn } from "@/lib/utils";
import type { ConfigField } from "@/api/types";
import { wireValue } from "@/lib/config";

interface ConfigFieldProps {
  field: ConfigField;
  value: string;
  onChange: (value: string) => void;
  onReset?: () => void;
  isDirty: boolean;
}

/**
 * Render a single config field with the correct input type.
 * Mirrors the vanilla admin's renderField so wire payloads stay
 * byte-identical. Design tokens apply the Apple grammar per design-system.md.
 */
export function ConfigFieldRow({ field, value, onChange, onReset, isDirty }: ConfigFieldProps) {
  const handleChange = (next: string) => onChange(wireValue(field, next));

  const renderControl = () => {
    if (field.type === "boolean") {
      return (
        <Switch
          checked={value === "true"}
          onCheckedChange={(checked) => handleChange(checked ? "true" : "false")}
          disabled={field.locked}
        />
      );
    }

    if (field.type === "select" && field.options?.length) {
      return (
        <Select value={value} onValueChange={handleChange} disabled={field.locked}>
          <SelectTrigger>
            <SelectValue placeholder="Select…" />
          </SelectTrigger>
          <SelectContent>
            {field.options.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }

    if (field.type === "model" || field.type === "optional_model") {
      return (
        <ModelCombobox
          value={value}
          onChange={handleChange}
          type={field.type}
          placeholder={
            field.type === "optional_model"
              ? "Uses provider default"
              : "Search or enter provider/model"
          }
          disabled={field.locked}
        />
      );
    }

    if (field.type === "textarea") {
      return (
        <Textarea
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          disabled={field.locked}
          rows={3}
        />
      );
    }

    if (field.type === "secret") {
      return (
        <Input
          type="password"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={
            field.configured
              ? "Configured — enter a new value to replace"
              : "Not configured"
          }
          disabled={field.locked}
          autoComplete="off"
        />
      );
    }

    if (field.type === "number") {
      return (
        <Input
          type="number"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          disabled={field.locked}
        />
      );
    }

    return (
      <Input
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        disabled={field.locked}
      />
    );
  };

  return (
    <div
      className={cn("flex flex-col gap-2", field.advanced && "hidden", isDirty && "ring-1 ring-heat/20 rounded-sm -mx-1 px-1 py-1")}
      data-key={field.key}
    >
      <div className="flex items-baseline justify-between gap-3">
        <Label htmlFor={`field-${field.key}`} className="flex-1">
          {field.label}
          {field.restart_required && (
            <span
              className="ml-2 inline-flex items-center gap-1 rounded-sm bg-heat/10 px-1.5 py-[2px] text-[10px] font-semibold text-heat"
              title="Requires server restart"
            >
              ↻ restart
            </span>
          )}
          {field.session_sensitive && (
            <span
              className="ml-2 inline-flex items-center gap-1 rounded-sm bg-info/12 px-1.5 py-[2px] text-[10px] font-semibold text-info"
              title="Requires new session"
            >
              ⎇ session
            </span>
          )}
        </Label>

        <div className="flex items-center gap-2">
          {field.description && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help text-ink-muted-48">
                  <Info className="size-3.5" aria-hidden="true" />
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" align="start">
                {field.description}
              </TooltipContent>
            </Tooltip>
          )}
          {onReset && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              aria-label={`Reset ${field.label}`}
              className="h-7 px-2 text-[12px]"
            >
              <RotateCcw className="size-3" />
              Reset
            </Button>
          )}
        </div>
      </div>

      <div className="w-full">{renderControl()}</div>

      {field.type === "optional_model" && (!value || value === "None") && (
        <p className="text-[12px] text-ink-muted-48">Uses provider default</p>
      )}

      {field.configured && field.type === "secret" && !value && (
        <p className="text-[12px] text-ink-muted-48">
          Currently configured (value hidden). Enter a new value to replace it.
        </p>
      )}
    </div>
  );
}
