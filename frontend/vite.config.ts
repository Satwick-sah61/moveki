import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, Vite serves the React app on :5173 and forwards /api to uvicorn on :8000,
// so the browser always talks to one origin. In Docker and on Vercel the FastAPI app
// serves the built files itself, so the same relative /api calls work there too.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
