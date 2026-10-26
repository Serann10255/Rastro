/* El camino normal de un envío, contado para público general.
 *
 * Son los seis estados del flujo principal de libs/rastro_core/state_machine.py,
 * con su código y una frase en lugar de su descripción técnica. Las salidas de
 * excepción (incidencia, devuelto, cancelado) no se dibujan: la diapositiva las
 * nombra y el «Si preguntan» las enumera. «En reparto» va resaltado porque es el
 * paso que se ve en el mapa, y «Entregado» en verde porque es el cierre
 * correcto.
 */

import { useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

interface Paso {
  codigo: number;
  nombre: string;
  frase: string;
  variante?: "acento" | "exito";
}

const PASOS: Paso[] = [
  { codigo: 10, nombre: "Creado", frase: "La empresa registra la guía" },
  { codigo: 20, nombre: "Asignado", frase: "Ya tiene un mensajero responsable" },
  { codigo: 30, nombre: "Recolectado", frase: "El paquete está en sus manos" },
  { codigo: 40, nombre: "En tránsito", frase: "Va hacia la zona de entrega" },
  { codigo: 50, nombre: "En reparto", frase: "Va en camino: se ve en el mapa", variante: "acento" },
  { codigo: 60, nombre: "Entregado", frase: "Con foto, fecha y ubicación", variante: "exito" },
];

const ALTO_PASO = 120;
const CENTRO_X = 62;

export default function ViajeDelPaquete({ titulo }: PropiedadesFigura) {
  const tituloId = useIdSvg("titulo");
  const primero = ALTO_PASO / 2;
  const ultimo = (PASOS.length - 1) * ALTO_PASO + ALTO_PASO / 2;

  return (
    <svg viewBox={`0 0 820 ${PASOS.length * ALTO_PASO}`} role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>

      {/* El hilo que une los pasos: se traza al entrar, como las flechas. */}
      <path d={`M${CENTRO_X} ${primero} V${ultimo}`} pathLength={1} className="fig-linea" />

      {PASOS.map((paso, i) => {
        const y = i * ALTO_PASO;
        const variante = paso.variante ? ` fig-caja--${paso.variante}` : "";
        return (
          <g key={paso.codigo}>
            <circle cx={CENTRO_X} cy={y + ALTO_PASO / 2} r={40} className={`fig-caja${variante}`} />
            <text
              x={CENTRO_X}
              y={y + ALTO_PASO / 2 + 10}
              textAnchor="middle"
              fontSize={28}
              className="fig-texto fig-texto--fuerte"
            >
              {paso.codigo}
            </text>
            <rect x={130} y={y + 12} width={680} height={ALTO_PASO - 24} rx={14} className={`fig-caja${variante}`} />
            <text x={160} y={y + 54} fontSize={30} className="fig-texto fig-texto--fuerte">
              {paso.nombre}
            </text>
            <text x={160} y={y + 88} fontSize={26} className="fig-texto fig-texto--suave">
              {paso.frase}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
