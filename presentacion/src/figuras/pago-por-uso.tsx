/* Pago por uso, como el recibo de la luz.
 *
 * Es una ilustración, no una medición: un día de 24 horas, con las horas en que
 * algo cobra resaltadas. El servidor propio cobra todas; la nube, las horas en
 * que alguien usa el sistema (un horario de oficina cualquiera). La cifra real
 * —50 dólares para el semestre— va en el texto de la diapositiva. El único
 * cargo fijo del despliegue, la llave de cifrado, está en «Si preguntan».
 */

import { useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

const HORAS = 24;
const IZQUIERDA = 20;
const ANCHO = 780;
const CELDA = ANCHO / HORAS;
const ALTO_CELDA = 90;

/** Horas con uso en la fila de la nube. */
const CON_USO = new Set([7, 8, 9, 11, 12, 14, 16, 17, 18]);

function Fila({ y, llena }: { y: number; llena: (hora: number) => boolean }) {
  return (
    <g>
      {Array.from({ length: HORAS }, (_, hora) => (
        <rect
          key={hora}
          x={IZQUIERDA + hora * CELDA + 2.5}
          y={y}
          width={CELDA - 5}
          height={ALTO_CELDA}
          rx={5}
          className={llena(hora) ? "fig-celda fig-celda--llena" : "fig-celda"}
        />
      ))}
    </g>
  );
}

export default function PagoPorUso({ titulo }: PropiedadesFigura) {
  const tituloId = useIdSvg("titulo");

  return (
    <svg viewBox="0 0 820 580" role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>

      <text x={IZQUIERDA} y={40} fontSize={30} className="fig-texto fig-texto--fuerte">
        Servidor propio
      </text>
      <text x={IZQUIERDA} y={80} fontSize={26} className="fig-texto fig-texto--suave">
        cobra las 24 horas, lo usen o no
      </text>
      <Fila y={105} llena={() => true} />

      <text x={IZQUIERDA} y={270} fontSize={30} className="fig-texto fig-texto--fuerte">
        En la nube
      </text>
      <text x={IZQUIERDA} y={310} fontSize={26} className="fig-texto fig-texto--suave">
        cobra cuando alguien lo usa
      </text>
      <Fila y={335} llena={(hora) => CON_USO.has(hora)} />

      {[0, 6, 12, 18, 24].map((hora) => (
        <text
          key={hora}
          x={IZQUIERDA + hora * CELDA}
          y={465}
          fontSize={25}
          textAnchor={hora === 0 ? "start" : hora === HORAS ? "end" : "middle"}
          className="fig-texto fig-texto--mono"
        >
          {hora} h
        </text>
      ))}

      <rect x={IZQUIERDA} y={510} width={27} height={36} rx={5} className="fig-celda fig-celda--llena" />
      <text x={IZQUIERDA + 42} y={537} fontSize={26} className="fig-texto fig-texto--suave">
        hora que se paga
      </text>
    </svg>
  );
}
