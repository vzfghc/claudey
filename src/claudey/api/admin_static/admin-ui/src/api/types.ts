/**
 * Typed contract for the local admin API
 * (routes defined in src/claudey/api/admin_routes.py). Only the fields the
 * micro-frontend renders are declared — payloads stay loose on purpose.
 */

/** Token breakdown keyed by measurement name (input/output/…). */
export type TokenTotals = Record<string, number> & {
  total_tokens: number;
  conversations: number;
};

/** Window totals keyed by rolling period label. */
export type UsageWindows = Partial<Record<Period, number>>;

export type Period = "24h" | "7d" | "30d";

export interface UsageProviderRow {
  provider: string;
  total_tokens: number;
  conversations: number;
}

export interface UsagePayload {
  available: boolean;
  total_entries: number;
  last_updated: string | null;
  totals: TokenTotals;
  windows: UsageWindows;
  daily: Array<Record<string, unknown>>;
  models: Array<Record<string, unknown>>;
  providers: UsageProviderRow[];
  heatmap: Array<Record<string, unknown>>;
}

/** DeepSeek billing payload merged into /admin/api/usage by the server. */
export interface BillingPayload {
  total_tokens?: number;
  total_cost_usd?: number;
  available?: boolean;
  configured?: boolean;
  status?: string;
  days?: Array<{ date: string; cost_usd: number }>;
  [key: string]: unknown;
}

export interface UsageResponse {
  billing?: BillingPayload;
}

export interface DashboardPayload {
  commits: Array<Record<string, unknown>>;
  stats: { agents: number; skills: number };
  usd_to_idr: number;
  monthly_spend_usd: number;
  monthly_limit_usd: number;
}

export interface ApiErrorShape {
  detail?: string;
  message?: string;
}

/* ------------------------------------------------------------------ */
/* Config payload (src/claudey/config/admin/values.py)                 */
/* ------------------------------------------------------------------ */

export type ConfigFieldType =
  | "text"
  | "secret"
  | "number"
  | "boolean"
  | "model"
  | "optional_model"
  | "select"
  | "textarea";

export interface ConfigOption {
  value: string;
  label: string;
}

export interface ConfigField {
  key: string;
  label: string;
  section: string;
  type: ConfigFieldType;
  value: string;
  configured: boolean;
  source: string;
  locked: boolean;
  secret: boolean;
  advanced: boolean;
  restart_required: boolean;
  session_sensitive: boolean;
  options?: ConfigOption[];
  description?: string;
}

export interface ConfigSection {
  id: string;
  label: string;
  description: string;
  advanced: boolean;
}

export type ProviderKind = "remote" | "local" | "connected_account" | "custom";

export interface ProviderStatus {
  provider_id: string;
  display_name: string;
  kind: ProviderKind;
  status: string;
  label: string;
  configuration?: string;
  compatible?: "anthropic" | "openai";
  base_url?: string;
  created_at?: string;
}

export interface ConfigPaths {
  managed: string;
  repo: string;
  explicit: string;
}

export interface ConfigPayload {
  sections: ConfigSection[];
  fields: ConfigField[];
  paths: ConfigPaths;
  provider_status: ProviderStatus[];
}

/* ------------------------------------------------------------------ */
/* Providers: local-status, test, models                              */
/* ------------------------------------------------------------------ */

export interface ProviderTestResult {
  ok: boolean;
  models?: string[];
  error_type?: string;
}

export interface ModelsResponse {
  models: string[];
  failed_providers?: string[];
}

/* ------------------------------------------------------------------ */
/* Custom providers                                                    */
/* ------------------------------------------------------------------ */

export interface CustomProviderPayload {
  type: "openai" | "anthropic";
  name: string;
  base_url: string;
  api_key?: string;
  model_id?: string | null;
}

export interface CustomProviderValidateResult {
  valid: boolean;
  method?: "chat" | "models";
  error?: string;
}

/* ------------------------------------------------------------------ */
/* Fallback combos                                                     */
/* ------------------------------------------------------------------ */

export interface ComboNode {
  provider_model_ref: string;
  enabled: boolean;
  priority: number;
}

export interface Combo {
  combo_id: string;
  display_name: string;
  enabled: boolean;
  nodes: ComboNode[];
}

export interface ComboPayload {
  display_name: string;
  nodes: ComboNode[];
  enabled: boolean;
}

export interface ComboValidateResult {
  valid: boolean;
  error?: string;
}

/* ------------------------------------------------------------------ */
/* Config validate / apply                                             */
/* ------------------------------------------------------------------ */

export interface ValidateResponse {
  valid: boolean;
  errors?: string[];
}

export interface ApplyResponse {
  applied: boolean;
  errors?: string[];
  restart?: {
    required: boolean;
    automatic: boolean;
    admin_url?: string;
    fields?: string[];
  };
  pending_fields?: string[];
}
