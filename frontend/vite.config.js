// Vite = the tool that runs the website while we develop, and builds it for the server.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Any call to /api/... is forwarded to our FastAPI server.
    // So the website always uses "/api/..." — same on your Mac and on EC2 later.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
