/* Registro de figuras.
 *
 * Una figura existe si existe su archivo en esta carpeta: `arquitectura-rastro.tsx`
 * se cita en el guion como `![Título](figura:arquitectura-rastro)`. El
 * compilador comprueba la misma carpeta al construir, de modo que no hay una
 * lista aparte que pueda quedarse atrás.
 */

import type { ComponentType } from "react";

export interface PropiedadesFigura {
  /** El texto alternativo del guion: título accesible del SVG. */
  titulo: string;
}

const modulos = import.meta.glob<{ default: ComponentType<PropiedadesFigura> }>("./*.tsx", {
  eager: true,
});

export const FIGURAS: Record<string, ComponentType<PropiedadesFigura>> = Object.fromEntries(
  Object.entries(modulos).map(([ruta, modulo]) => [ruta.replace(/^\.\/|\.tsx$/g, ""), modulo.default]),
);
