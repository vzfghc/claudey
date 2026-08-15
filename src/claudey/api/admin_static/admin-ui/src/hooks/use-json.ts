import { useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Minimal JSON fetch hook with AbortController cleanup.
 * (Container views only — the design-system empty/error states do the rest.)
 * @param refetchKey — bump to refetch the same path without remounting callers.
 */
export function useJson<T>(path: string, refetchKey: number = 0): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, isLoading: true, error: null });

    fetch(path, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          let detail = `Request failed (${response.status})`;
          try {
            const body = (await response.json()) as { detail?: string };
            if (body.detail) detail = body.detail;
          } catch {
            /* non-JSON error body — keep the status message */
          }
          throw new Error(detail);
        }
        return (await response.json()) as T;
      })
      .then((data) => setState({ data, isLoading: false, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Unexpected error";
        setState({ data: null, isLoading: false, error: message });
      });

    return () => controller.abort();
  }, [path, refetchKey]);

  return state;
}