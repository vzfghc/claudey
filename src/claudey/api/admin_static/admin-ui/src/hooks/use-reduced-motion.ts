import { useCallback, useState, useSyncExternalStore } from "react";

/**
 * Subscribes to `prefers-reduced-motion` (SSR-safe via getServerSnapshot).
 * All decorative loops in the admin UI must gate behind this — same rule
 * the vanilla admin-animations.js layer enforced.
 */
export function useReducedMotion(): boolean {
  const subscribe = useCallback((callback: () => void) => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    query.addEventListener("change", callback);
    return () => query.removeEventListener("change", callback);
  }, []);

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

/** Persistent boolean flag (localStorage-backed synced across the app). */
export function useStoredFlag(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : raw === "true";
    } catch {
      return initial;
    }
  });

  const set = useCallback(
    (next: boolean) => {
      setValue(next);
      try {
        localStorage.setItem(key, String(next));
      } catch {
        /* storage unavailable — state still works for the session */
      }
    },
    [key],
  );

  return [value, set];
}