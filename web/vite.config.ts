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
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // El sistema de diseño vive fuera de la aplicación, en `design/`, y lo
      // comparten las dos interfaces. Es la única forma de que Rastro y Cotejo
      // no se separen visualmente: una copia por aplicación diverge en cuanto
      // alguien corrige un color en una sola.
      "@design": fileURLToPath(new URL("../design", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: true,
    // Vite solo sirve archivos dentro de la raíz del proyecto; el sistema de
    // diseño está un nivel más arriba y hay que permitirlo explícitamente.
    fs: { allow: [fileURLToPath(new URL(".", import.meta.url)), fileURLToPath(new URL("../design", import.meta.url))] },
    // En desarrollo la interfaz llama a rutas relativas y Vite las reenvia a la
    // puerta de enlace, de modo que no hay diferencia de origen entre el
    // entorno de desarrollo y el sitio publicado.
    // La lista es la misma que reparte la puerta de enlace. Si aqui falta un
    // prefijo, la ruta responde el index.html de Vite en lugar de la API y el
    // sintoma es un error de JSON invalido que no señala su causa.
    proxy: Object.fromEntries(
      [
        "/auth",
        "/usuarios",
        "/empresa",
        "/equipo",
        "/roles",
        "/envios",
        "/publico",
        "/bitacora",
        "/tablero",
        "/catalogos",
        "/tiendas",
        "/clientes",
        "/transportistas",
        "/salud",
      ].map((ruta) => [
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
