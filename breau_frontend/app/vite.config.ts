// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@api": path.resolve(__dirname, "src/api"),
      "@hooks": path.resolve(__dirname, "src/hooks"),
      "@components": path.resolve(__dirname, "src/components"),
      "@context": path.resolve(__dirname, "src/context"),
      "@pages": path.resolve(__dirname, "src/pages"),
      "@styles": path.resolve(__dirname, "src/styles"),
      "@lib": path.resolve(__dirname, "src/lib"),
      "@data": path.resolve(__dirname, "src/data"),
      "@utils": path.resolve(__dirname, "src/utils"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE || "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: false,
        // IMPORTANT: do NOT strip /api — your backend expects it
        rewrite: (p) => p, // or simply remove the rewrite line
      },
    },
  },
});
