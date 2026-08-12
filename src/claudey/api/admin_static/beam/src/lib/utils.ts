// The magicui `cn` helper the AnimatedBeam component imports from
// "@/lib/utils". Kept verbatim so the vendored component needs no edits.
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
