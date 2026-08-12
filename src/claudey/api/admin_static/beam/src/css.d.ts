// The esbuild build inlines CSS as text (loader: { ".css": "text" }); this
// declaration lets tsc type-check the import without the loader present.
declare module "*.css" {
  const content: string;
  export default content;
}
