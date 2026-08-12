import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// Admin micro-frontend for claudey. Tailwind v4 via the Vite plugin (CSS-first
// config lives in src/styles/globals.css). Built into admin_static/admin_ui_dist
// by build.mjs and served offline from the Python admin server.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    target: "es2020",
  },
  // Served under /admin/ui by admin_routes.py — all emitted asset URLs are
  // absolute against this base so the entry works with or without a trailing
  // slash.
  base: "/admin/ui/",
});