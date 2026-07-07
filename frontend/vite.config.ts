import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite の設定ファイル。
// ポイントは server.proxy:
//   フロント（http://localhost:5173）から "/ask" を呼ぶと、
//   Vite が裏で http://localhost:8770/ask に転送してくれる。
//   こうすると CORS の設定がいらず、バックエンドを一切変えずに済む。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 注意: localhost ではなく 127.0.0.1 を使う。
      // Node 18 は localhost を IPv6(::1) に解決することがあり、
      // IPv4 で待つ uvicorn に繋がらず 500 になるため。
      "/ask": "http://127.0.0.1:8770",
      "/ingest": "http://127.0.0.1:8770",
      "/ingest_sample": "http://127.0.0.1:8770",
      "/ingest_pdf": "http://127.0.0.1:8770",
      "/health": "http://127.0.0.1:8770",
    },
  },
});
