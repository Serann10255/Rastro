/* Quién hace qué durante la demostración en vivo.
 *
 * Sirve al público para seguir lo que pasa entre tres pantallas a la vez, y al
 * equipo como guion si el GPS del salón no colabora: la diapositiva anterior
 * muestra lo mismo en capturas. Sin nombres de personas, para no tener que
 * cambiar la figura si cambia el reparto.
 */

import { Caja, PuntaFlecha, useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

const ALTO = 130;
const PASO = 180;

const PASOS = [
  { quien: "El mensajero", que: "sale a ruta desde su celular", variante: "actor" },
  { quien: "La empresa", que: "lo ve moverse en esta pantalla", variante: "acento" },
  { quien: "El cliente", que: "lo sigue desde otro celular, sin cuenta", variante: "actor" },
  { quien: "Entregado", que: "con foto: el paquete queda cerrado", variante: "exito" },
] as const;

export default function DemoEnVivo({ titulo }: PropiedadesFigura) {
  const flecha = useIdSvg("flecha");
  const tituloId = useIdSvg("titulo");

  return (
    <svg viewBox={`0 0 820 ${(PASOS.length - 1) * PASO + ALTO}`} role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>
      <defs>
        <PuntaFlecha id={flecha} />
      </defs>

      {PASOS.map((paso, i) => (
        <Caja
          key={paso.quien}
          x={40}
          y={i * PASO}
          ancho={740}
          alto={ALTO}
          variante={paso.variante}
          lineas={[
            { texto: paso.quien, estilo: "fuerte" },
            { texto: paso.que, estilo: "suave" },
          ]}
        />
      ))}

      {PASOS.slice(1).map((paso, i) => {
        const desde = i * PASO + ALTO;
        return (
          <path
            key={paso.quien}
            d={`M410 ${desde} V${desde + PASO - ALTO - 2}`}
            pathLength={1}
            className="fig-linea"
            markerEnd={`url(#${flecha})`}
          />
        );
      })}
    </svg>
  );
}
