import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Any request to /api goes to our Python backend.
    // (COOKMATE_API lets a test copy point at a different backend.)
    proxy: { "/api": process.env.COOKMATE_API ?? "http://127.0.0.1:8000" },
  },
});
