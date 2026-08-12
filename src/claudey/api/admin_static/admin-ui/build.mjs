// Vite build → dist/, then copies dist/* into ../admin_ui_dist (committed,
// served offline by admin_routes.py at /admin/ui). Run via `npm run build`.
import { cpSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, "dist");
const outDir = resolve(here, "..", "admin_ui_dist");

rmSync(outDir, { recursive: true, force: true });
cpSync(distDir, outDir, { recursive: true });

process.stdout.write(`admin-ui build copied → ${outDir}\n`);
