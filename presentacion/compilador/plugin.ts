/* Complemento de Vite: importar un guion `.md` devuelve el deck ya compilado.
 *
 *   import deck from "@sustentacion/sustentacion-rastro.md";
 *
 * El Markdown se lee al construir, no se copia al código: si cambia el guion y
 * se vuelve a construir, cambia el deck. En desarrollo, guardar el Markdown
 * recarga la página, porque el archivo es una dependencia más del módulo.
 *
 * Los errores de lectura detienen la construcción con la línea del problema;
 * los avisos (numeración con saltos, diapositivas sin notas) se muestran y
 * dejan seguir, porque son decisiones del autor que conviene revisar.
 */

import { readdirSync } from "node:fs";
import { relative } from "node:path";

import type { Connect, Plugin } from "vite";

import { compilarSustentacion } from "./sustentacion.ts";

interface Opciones {
  /** Raíz del repositorio, para citar el archivo con su ruta relativa. */
  raizRepositorio: string;
  /** Carpeta de las figuras: una figura existe si existe su archivo. */
  carpetaFiguras: string;
}

export function sustentacion({ raizRepositorio, carpetaFiguras }: Opciones): Plugin {
  const figurasDisponibles = () =>
    new Set(
      readdirSync(carpetaFiguras)
        .filter((f) => f.endsWith(".tsx"))
        .map((f) => f.replace(/\.tsx$/, "")),
    );

  return {
    name: "rastro:sustentacion",
    enforce: "pre",
    transform(codigo, id) {
      const ruta = id.split("?")[0]!;
      if (!ruta.endsWith(".md")) return null;

      const archivo = relative(raizRepositorio, ruta).replaceAll("\\", "/");
      try {
        const { deck, avisos } = compilarSustentacion(codigo, {
          archivo,
          figuras: figurasDisponibles(),
        });
        for (const aviso of avisos) this.warn(aviso);
        const { total, contenido, bloques } = deck.resumen;
        console.log(
          `  sustentación · ${archivo}: ${total} diapositivas (${contenido} de contenido y ${bloques} portadillas de bloque)`,
        );
        return { code: `export default ${JSON.stringify(deck)};`, map: null };
      } catch (e) {
        this.error((e as Error).message);
      }
    },
  };
}

/**
 * `/rastro` → `/rastro/`, como hace cualquier alojamiento estático con una
 * carpeta. Sin esto, el servidor de desarrollo responde a `/rastro#7` con el
 * índice, porque cae a la página raíz. El navegador conserva la almohadilla al
 * seguir la redirección, de modo que `/rastro#7` abre la diapositiva 7.
 */
export function rutasDeDeck(decks: string[]): Plugin {
  const patron = new RegExp(`^/(${decks.join("|")})(\\?.*)?$`);
  const redirigir: Connect.NextHandleFunction = (peticion, respuesta, siguiente) => {
    const coincidencia = patron.exec(peticion.url ?? "");
    if (!coincidencia) return siguiente();
    respuesta.statusCode = 302;
    respuesta.setHeader("Location", `/${coincidencia[1]}/${coincidencia[2] ?? ""}`);
    respuesta.end();
  };
  return {
    name: "rastro:rutas-de-deck",
    configureServer(servidor) {
      servidor.middlewares.use(redirigir);
    },
    configurePreviewServer(servidor) {
      servidor.middlewares.use(redirigir);
    },
  };
}
