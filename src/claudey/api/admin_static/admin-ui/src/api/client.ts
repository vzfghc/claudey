import type {
  ApiErrorShape,
  ApplyResponse,
  AuthStatus,
  Combo,
  ComboPayload,
  ComboValidateResult,
  ConfigPayload,
  CustomProviderPayload,
  CustomProviderValidateResult,
  DashboardPayload,
  LocalStatusResponse,
  ModelsResponse,
  ProviderTestResult,
  UsagePayload,
  UsageResponse,
  ValidateResponse,
} from "./types";

/** UsagePayload + billing merged by the server under /admin/api/usage. */
export type AdminUsagePayload = UsagePayload & UsageResponse;

/**
 * Tiny typed fetch wrapper. Handles the shared Admin API conventions:
 * JSON only, `detail` on errors, `no-store` so refresh leaves no cache.
 */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    let shape: ApiErrorShape = {};
    try {
      shape = (await response.json()) as ApiErrorShape;
    } catch {
      shape = { detail: `Request failed (${response.status})` };
    }
    throw new Error(
      typeof shape.detail === "string" && shape.detail
        ? shape.detail
        : shape.message || `Request failed (${response.status})`,
    );
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/* GETs */
export function fetchDashboard(signal?: AbortSignal): Promise<DashboardPayload> {
  return request<DashboardPayload>("/admin/api/dashboard", { signal });
}

export function fetchUsage(signal?: AbortSignal): Promise<AdminUsagePayload> {
  return request<AdminUsagePayload>("/admin/api/usage", { signal });
}

export function fetchConfig(signal?: AbortSignal): Promise<ConfigPayload> {
  return request<ConfigPayload>("/admin/api/config", { signal });
}

export function fetchModels(signal?: AbortSignal): Promise<ModelsResponse> {
  return request<ModelsResponse>("/admin/api/models", { signal });
}

export function fetchCombos(signal?: AbortSignal): Promise<{ combos: Combo[] }> {
  return request<{ combos: Combo[] }>("/admin/api/combos", { signal });
}

export function fetchCustomProviders(signal?: AbortSignal): Promise<ConfigPayload["provider_status"]> {
  return request<ConfigPayload["provider_status"]>("/admin/api/providers/custom", { signal });
}

export function fetchProviderAuth(
  providerId: string,
  signal?: AbortSignal,
): Promise<AuthStatus> {
  return request<AuthStatus>(`/admin/api/providers/${providerId}/auth`, { signal });
}

/* POSTs */
export function validateConfig(values: Record<string, string>): Promise<ValidateResponse> {
  return post<ValidateResponse>("/admin/api/config/validate", { values });
}

export function applyConfig(values: Record<string, string>): Promise<ApplyResponse> {
  return post<ApplyResponse>("/admin/api/config/apply", { values });
}

export function refreshModels(): Promise<ModelsResponse> {
  return post<ModelsResponse>("/admin/api/models/refresh");
}

export function restartServer(): Promise<{ restarting: boolean; admin_url: string }> {
  return post("/admin/api/restart");
}

export function testProvider(providerId: string): Promise<ProviderTestResult> {
  return post<ProviderTestResult>(`/admin/api/providers/${providerId}/test`, {});
}

export function refreshLocalStatus(): Promise<LocalStatusResponse> {
  return post<LocalStatusResponse>("/admin/api/providers/local-status");
}

export function startAuthLogin(
  providerId: string,
  mode: "browser" | "device",
): Promise<AuthStatus> {
  return post<AuthStatus>(`/admin/api/providers/${providerId}/auth/login`, { mode });
}

export function cancelAuthLogin(providerId: string): Promise<AuthStatus> {
  return post<AuthStatus>(`/admin/api/providers/${providerId}/auth/cancel`);
}

export function disconnectProvider(providerId: string): Promise<AuthStatus> {
  return request<AuthStatus>(`/admin/api/providers/${providerId}/auth`, { method: "DELETE" });
}

export function validateCustomProvider(
  payload: Omit<CustomProviderPayload, "name">,
): Promise<CustomProviderValidateResult> {
  return post<CustomProviderValidateResult>("/admin/api/providers/custom/validate", payload);
}

export function createCustomProvider(payload: CustomProviderPayload): Promise<{ message: string }> {
  return post<{ message: string }>("/admin/api/providers/custom", payload);
}

export function createCombo(payload: ComboPayload): Promise<{ message: string }> {
  return post<{ message: string }>("/admin/api/combos", payload);
}

export function updateCombo(comboId: string, payload: ComboPayload): Promise<{ message: string }> {
  return request<{ message: string }>(`/admin/api/combos/${comboId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function validateCombo(payload: ComboPayload): Promise<ComboValidateResult> {
  return post<ComboValidateResult>("/admin/api/combos/validate", payload);
}

/* DELETEs */
export function deleteCustomProvider(providerId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/admin/api/providers/custom/${providerId}`, {
    method: "DELETE",
  });
}

export function deleteCombo(comboId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/admin/api/combos/${comboId}`, { method: "DELETE" });
}