// Builds the provider-beam micro-frontend into a single self-contained
// IIFE bundle at admin_static/beam.bundle.js. The bundle inlines the
// stylesheet (loader ".css" = "text") and React + motion, so the admin
// serves one offline-safe file — no runtime CDN requests.
//
// Rebuild after editing anything under beam/src:
//   cd src/claudey/api/admin_static/beam && npm install && npm run build
import { build } from "esbuild";

await build({
  entryPoints: ["src/main.tsx"],
  bundle: true,
  minify: true,
  format: "iife",
  platform: "browser",
  target: ["es2020"],
  outfile: "../beam.bundle.js",
  sourcemap: false,
  loader: { ".css": "text" },
  define: {
    "process.env.NODE_ENV": '"production"',
  },
  logLevel: "info",
});
