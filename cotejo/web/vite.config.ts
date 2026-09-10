import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Igual que en Rastro: la direccion de la API se lee en tiempo de ejecucion de
// public/configuracion.json y nunca se hornea en el bundle. Cotejo se ejecuta
// contra cuentas distintas segun se audite el entorno local o el desplegado, y
// recompilar para cambiar de objetivo seria un obstaculo, no una garantia.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5175,
    host: true,
    proxy: {
      // El programa de auditoria; el prefijo evita chocar con las rutas de Rastro.
      "/cotejo": {
        target: process.env.COTEJO_URL_API ?? "http://localhost:8007",
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/cotejo/, ""),
      },
      // La autenticacion la resuelve el proveedor de identidad de Rastro: el
      // auditor es un usuario de la organizacion, no una cuenta aparte.
      "/auth": { target: process.env.RASTRO_URL_API ?? "http://localhost:8080", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
