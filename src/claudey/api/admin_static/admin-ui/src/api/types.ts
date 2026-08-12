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