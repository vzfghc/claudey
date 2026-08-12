import type {
  ApiErrorShape,
  DashboardPayload,
  UsagePayload,
  UsageResponse,
} from "./types";

/** Tiny typed fetch wrapper. Abortable, JSON-only, validates HTTP status. */
async function getJson<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    let shape: ApiErrorShape = {};
    try {
      shape = (await response.json()) as ApiErrorShape;
    } catch {
      shape = { detail: `Request failed (${response.status})` };
    }
    throw new Error(shape.detail || shape.message || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

/** UsagePayload + billing merged by the server under /admin/api/usage. */
export type AdminUsagePayload = UsagePayload & UsageResponse;

export function fetchDashboard(signal?: AbortSignal): Promise<DashboardPayload> {
  return getJson<DashboardPayload>("/admin/api/dashboard", signal);
}

export function fetchUsage(signal?: AbortSignal): Promise<AdminUsagePayload> {
  return getJson<AdminUsagePayload>("/admin/api/usage", signal);
}