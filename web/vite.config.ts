import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// La direccion de la API NO se hornea en el bundle. Se lee de
// public/configuracion.json en tiempo de ejecucion, porque el requisito REQ-09
// exige que trasladar el sistema a otra cuenta no obligue a tocar el codigo ni
// a recompilar. Con `import.meta.env.VITE_*` la URL quedaria dentro del
// paquete compilado y cada migracion exigiria un build nuevo.
export default defineConfig({
  plugins: [react()],
  resolve: {
    // El mismo alias que declara tsconfig.json. Sin esto, el compilador de tipos
    // resuelve las rutas pero el empaquetador no, y el fallo solo aparece al
    // construir para producción.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    host: true,
    // En desarrollo la interfaz llama a rutas relativas y Vite las reenvia a la
    // puerta de enlace, de modo que no hay diferencia de origen entre el
    // entorno de desarrollo y el sitio publicado.
    proxy: Object.fromEntries(
      ["/auth", "/envios", "/publico", "/bitacora"].map((ruta) => [
        ruta,
        { target: process.env.RASTRO_URL_API ?? "http://localhost:8080", changeOrigin: true },
      ]),
    ),
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        // Separar la biblioteca del codigo propio permite que un cambio en la
        // interfaz no invalide la cache del navegador para todo lo demas.
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          consultas: ["@tanstack/react-query"],
        },
      },
    },
  },
});
