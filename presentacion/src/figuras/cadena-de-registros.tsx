/* La bitácora encadenada, contada como una cadena de eslabones.
 *
 * Cada registro guarda la huella (SHA-256, libs/rastro_core/audit.py) del
 * anterior. Si alguien cambia el tercero, su huella cambia y la que guardó el
 * cuarto ya no coincide: la verificación lo detecta en ese eslabón. Para el
 * público general basta esa idea; los campos reales del registro están en la
 * captura de la bitácora que acompaña a la figura en la diapositiva.
 */

import { Caja, useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

const ALTO = 130;
const PASO = 190;

const REGISTROS = [
  { titulo: "Registro 1", huella: "primer eslabón" },
  { titulo: "Registro 2", huella: "huella del registro 1" },
  { titulo: "Registro 3 · cambiado", huella: "huella del registro 2", alterado: true },
  { titulo: "Registro 4", huella: "huella del registro 3" },
];

export default function CadenaDeRegistros({ titulo }: PropiedadesFigura) {
  const tituloId = useIdSvg("titulo");

  return (
    // Sesenta unidades de aire debajo: en la diapositiva va en una galería, y
    // los puntos de la galería se dibujan sobre el borde inferior.
    <svg viewBox="0 0 820 760" role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>

      {REGISTROS.map((registro, i) => (
        <Caja
          key={registro.titulo}
          x={40}
          y={i * PASO}
          ancho={740}
          alto={ALTO}
          variante={registro.alterado ? "peligro" : "normal"}
          lineas={[
            { texto: registro.titulo, estilo: "fuerte" },
            { texto: registro.alterado ? "alguien cambió lo que pasó" : "qué pasó · quién · cuándo", estilo: "suave" },
            { texto: registro.huella, estilo: "mono" },
          ]}
        />
      ))}

      {/* Los eslabones entre registros. El que sigue al registro cambiado se
          rompe: la huella que guarda el 4 ya no es la del 3. */}
      {REGISTROS.slice(0, -1).map((registro, i) => {
        const y = i * PASO + ALTO;
        const roto = registro.alterado;
        return (
          <g key={`eslabon-${i}`}>
            <rect
              x={393}
              y={y + 8}
              width={34}
              height={PASO - ALTO - 16}
              rx={17}
              className={roto ? "fig-eslabon fig-eslabon--roto" : "fig-eslabon"}
            />
            {roto && (
              <text x={450} y={y + 40} fontSize={26} className="fig-texto fig-texto--peligro">
                la huella ya no coincide
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
