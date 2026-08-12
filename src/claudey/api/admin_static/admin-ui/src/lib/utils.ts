import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind class merge — shadcn/magicui `cn` helper. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** @returns the last settled value after a width fade threshold. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Compact token formatter: 1,009,743 → "1.0M", 9,091 → "9.1k", 812 → "812". */
export function compactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(Math.round(value));
}

/** Thousands with commas: 2834 → "2,834". */
export function thousands(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}

/** USD with two decimals: 0.16 → "$0.16". */
export function formatUsd(cost: number): string {
  return `$${cost.toFixed(2)}`;
}

/** USD→IDR compact: "Rp 12.1M" over a million, "Rp 3,430" below. */
export function formatIdr(cost: number, rate: number): string {
  const idr = cost * rate;
  if (idr >= 1_000_000) return `Rp ${(idr / 1_000_000).toFixed(1)}M`;
  return `Rp ${Math.round(idr).toLocaleString("en-US")}`;
}