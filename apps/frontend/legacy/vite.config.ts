import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  build: { rollupOptions: { input: { main: "index.html", pa1: "pa1.html" } } },
  server: { watch: { ignored: ["**/artifacts/**", "**/test-results/**"] } },
});
