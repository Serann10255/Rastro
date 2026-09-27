/* Piezas comunes de las figuras.
 *
 * Las figuras se dibujan para verse a distancia: pocas cajas, grandes, y texto
 * que no baja de 25 unidades en un lienzo de 820 de ancho, que es lo que mide
 * una columna de la diapositiva. Todo el color sale de las fichas de diseño por
 * clase CSS (`fig-*` en presentacion.css), de modo que la figura cambia con el
 * tema y con la identidad del proyecto sin tocarla.
 */

import { useId } from "react";

export type EstiloLinea = "fuerte" | "normal" | "suave" | "mono" | "rotulo";

export interface LineaCaja {
  texto: string;
  estilo?: EstiloLinea;
}

const TAMANO: Record<EstiloLinea, number> = {
  fuerte: 30,
  normal: 28,
  suave: 26,
  mono: 25,
  rotulo: 25,
};

const INTERLINEA = 1.3;

interface PropiedadesCaja {
  x: number;
  y: number;
  ancho: number;
  alto: number;
  lineas: LineaCaja[];
  variante?: "normal" | "acento" | "actor" | "discontinua";
}

/** Caja con su texto centrado en vertical y en horizontal. */
export function Caja({ x, y, ancho, alto, lineas, variante = "normal" }: PropiedadesCaja) {
  const alturas = lineas.map((l) => TAMANO[l.estilo ?? "normal"] * INTERLINEA);
  const total = alturas.reduce((a, b) => a + b, 0);
  let base = y + (alto - total) / 2;

  return (
    <g>
      <rect x={x} y={y} width={ancho} height={alto} rx={14} className={`fig-caja fig-caja--${variante}`} />
      {lineas.map((linea, i) => {
        const tamano = TAMANO[linea.estilo ?? "normal"];
        // La línea base queda a unas tres cuartas partes de su interlineado.
        const posicion = base + alturas[i]! * 0.72;
        base += alturas[i]!;
        return (
          <text
            key={i}
            x={x + ancho / 2}
            y={posicion}
            textAnchor="middle"
            fontSize={tamano}
            className={`fig-texto fig-texto--${linea.estilo ?? "normal"}`}
          >
            {linea.texto}
          </text>
        );
      })}
    </g>
  );
}

/** Identificadores únicos para marcadores: la misma figura se dibuja en el
 *  visor y en el guion, y dos marcadores con el mismo id se confunden. */
export function useIdSvg(prefijo: string): string {
  return `${prefijo}-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

export function PuntaFlecha({ id }: { id: string }) {
  return (
    <marker
      id={id}
      viewBox="0 0 10 10"
      refX="9"
      refY="5"
      markerWidth="7"
      markerHeight="7"
      orient="auto-start-reverse"
    >
      <path d="M0,0 L10,5 L0,10 z" className="fig-punta" />
    </marker>
  );
}
