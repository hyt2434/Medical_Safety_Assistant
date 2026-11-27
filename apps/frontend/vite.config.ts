import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "");
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: Number(process.env.FRONTEND_PORT || env.FRONTEND_PORT || 5173),
      strictPort: false,
      proxy: {
        "/api":
          process.env.API_PROXY_URL ||
          env.API_PROXY_URL ||
          "http://127.0.0.1:8000",
      },
    },
  };
});
