import type { ConfigField } from "@/api/types";

/**
 * Shared config-form helpers. Mirrors the vanilla admin behavior exactly so the
 * wire payloads are byte-identical to what the server validated against.
 */

/** The server's mask for configured secrets (src/claudey/config/admin/values.py). */
export const MASKED_SECRET = "********";

export const REASONING_OPTION_ORDER: Record<string, number> = {
  inherit: 0,
  off: 1,
  client: 2,
  low: 3,
  medium: 4,
  high: 5,
  xhigh: 6,
  max: 7,
};

/** Present a config value as the value an editable input should show. */
export function inputValue(field: ConfigField): string {
  if (field.type === "secret") return "";
  if (field.type === "optional_model" && !field.value.trim()) return "None";
  return field.value || "";
}

/** Normalize an edited input value into the wire value for this field. */
export function wireValue(field: ConfigField, edited: string): string {
  if (field.type === "boolean") return String(edited).toLowerCase() === "true" ? "true" : "false";
  if (field.type === "optional_model") {
    const trimmed = edited.trim().toLowerCase();
    if (!trimmed || trimmed === "none") return "";
    return edited.trim();
  }
  if (field.type === "secret" && field.configured && !edited) return MASKED_SECRET;
  return edited;
}

/**
 * Whether editing this field counts as a change. A configured secret with no
 * new input reads back as the mask, so it is never "dirty".
 */
export function isFieldChanged(field: ConfigField, edited: string): boolean {
  const original = field.value || "";
  if (field.type === "boolean") {
    return (edited ? "true" : "false") !== String(Boolean(original && original !== "false"));
  }
  const current = wireValue(field, edited);
  return current !== original;
}

/** Human label for the config value source (writes to .env / process env). */
const SOURCE_LABELS: Record<string, string> = {
  template: "managed",
  managed: "managed",
  process: "process",
  repo: "repo",
  explicit: "explicit",
  default: "default",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}