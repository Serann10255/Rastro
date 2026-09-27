import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

import { rutasDeDeck, sustentacion } from "./compilador/plugin.ts";

const ruta = (relativa: string) => fileURLToPath(new URL(relativa, import.meta.url));

// Un sitio estático con tres páginas: el índice y un deck por proyecto. Son
// páginas y no rutas de una sola aplicación porque cada deck lleva la identidad
// de su proyecto —el azul de Rastro, el índigo de Cotejo— y esa identidad se
// declara sobre `:root`: dos identidades en la misma página se pisarían.
export default defineConfig({
  plugins: [
    sustentacion({ raizRepositorio: ruta(".."), carpetaFiguras: ruta("./src/figuras") }),
    rutasDeDeck(["rastro", "cotejo"]),
    react(),
  ],
  resolve: {
    alias: {
      "@": ruta("./src"),
      // El sistema de diseño es el mismo de las otras dos interfaces y no se
      // copia: véase documentacion/modulos/sistema-de-diseno.
      "@design": ruta("../design"),
      // Los guiones viven en la documentación, que es donde se escriben y se
      // revisan. El deck es una vista de ellos.
      "@sustentacion": ruta("../documentacion/sustentacion"),
      // La identidad de marca de cada proyecto se toma de su aplicación, no se
      // repite aquí: si cambia el color de Rastro, cambia también su deck.
      "@identidad-rastro": ruta("../web/src/estilos/identidad.css"),
      "@identidad-cotejo": ruta("../cotejo/web/src/estilos/identidad.css"),
    },
    // Los componentes de `design/` están fuera de esta carpeta y no tienen
    // `node_modules` al lado; sin esto, su `react/jsx-runtime` no se resuelve.
    dedupe: ["react", "react-dom"],
  },
  server: {
    port: 5177,
    host: true,
    fs: {
      allow: [
        ruta("."),
        ruta("../design"),
        ruta("../documentacion/sustentacion"),
        ruta("../web/src/estilos"),
        ruta("../web/public"),
        ruta("../cotejo/web/src/estilos"),
        ruta("../cotejo/web/public"),
      ],
    },
  },
  preview: { port: 5177 },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        inicio: ruta("./index.html"),
        rastro: ruta("./rastro/index.html"),
        cotejo: ruta("./cotejo/index.html"),
      },
    },
  },
});
