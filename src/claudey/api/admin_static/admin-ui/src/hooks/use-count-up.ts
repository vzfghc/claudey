import { useEffect, useRef, useState } from "react";

/**
 * Count-up animation toward a target number. Mirrors the vanilla
 * admin count-up tick. Gated behind prefers-reduced-motion (final value
 * rendered instantly).
 */
export function useCountUp(target: number, durationMs = 1500, disabled = false): number {
  const [value, setValue] = useState(disabled ? target : 0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (disabled) {
      setValue(target);
      return;
    }
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    if (target === 0) {
      setValue(0);
      return;
    }
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      // easeOutQuart — same settle the nav pill uses.
      const eased = 1 - Math.pow(1 - progress, 4);
      setValue(from + (target - from) * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, durationMs, disabled]);

  return value;
}