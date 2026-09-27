/* El ejecutor de Cotejo y sus tres fuentes de evidencia, para proyectar.
 *
 * Cada fuente es una familia de prueba del catálogo (Entrega 2, tabla 9 y
 * tabla 11): la configuración de la cuenta y el repositorio se inspeccionan
 * (cumplimiento), el sistema se usa con un usuario de cada rol (sustantivas) y
 * la bitácora se recalcula (integridad). Las flechas van hacia el ejecutor
 * porque lo que llega es evidencia; lo que sale hacia abajo es el papel de
 * trabajo con su huella, que es lo único que el ejecutor escribe.
 */

import { Caja, PuntaFlecha, useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

export default function EjecutorCotejo({ titulo }: PropiedadesFigura) {
  const flecha = useIdSvg("flecha");
  const tituloId = useIdSvg("titulo");

  return (
    <svg viewBox="0 0 820 720" role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>
      <defs>
        <PuntaFlecha id={flecha} />
      </defs>

      {/* Columna del programa: criterio, ejecución, evidencia. */}
      <Caja
        x={0}
        y={0}
        ancho={330}
        alto={150}
        lineas={[
          { texto: "Catálogo", estilo: "fuerte" },
          { texto: "criterio declarado", estilo: "suave" },
          { texto: "antes de ejecutar", estilo: "suave" },
        ]}
      />
      <path d="M165 150 V238" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={0}
        y={240}
        ancho={330}
        alto={180}
        variante="acento"
        lineas={[
          { texto: "Ejecutor", estilo: "fuerte" },
          { texto: "una invocación,", estilo: "suave" },
          { texto: "once resultados", estilo: "suave" },
        ]}
      />
      <path d="M165 420 V538" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={0}
        y={540}
        ancho={330}
        alto={180}
        lineas={[
          { texto: "Papeles de trabajo", estilo: "fuerte" },
          { texto: "salida literal", estilo: "suave" },
          { texto: "huella SHA-256", estilo: "suave" },
        ]}
      />

      {/* Las tres fuentes. La evidencia llega al ejecutor. */}
      <path d="M420 105 L336 292" className="fig-linea" markerEnd={`url(#${flecha})`} />
      <path d="M420 360 L336 330" className="fig-linea" markerEnd={`url(#${flecha})`} />
      <path d="M420 615 L336 368" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={420}
        y={0}
        ancho={400}
        alto={210}
        lineas={[
          { texto: "CUMPLIMIENTO", estilo: "rotulo" },
          { texto: "Configuración de AWS", estilo: "fuerte" },
          { texto: "y repositorio", estilo: "normal" },
          { texto: "C-01…C-04 · C-09a/b", estilo: "mono" },
        ]}
      />
      <Caja
        x={420}
        y={255}
        ancho={400}
        alto={210}
        lineas={[
          { texto: "SUSTANTIVAS", estilo: "rotulo" },
          { texto: "Rastro en uso", estilo: "fuerte" },
          { texto: "un usuario por rol", estilo: "normal" },
          { texto: "C-05…C-07 · C-09c", estilo: "mono" },
        ]}
      />
      <Caja
        x={420}
        y={510}
        ancho={400}
        alto={210}
        lineas={[
          { texto: "INTEGRIDAD", estilo: "rotulo" },
          { texto: "Bitácora encadenada", estilo: "fuerte" },
          { texto: "recálculo de la cadena", estilo: "normal" },
          { texto: "C-08", estilo: "mono" },
        ]}
      />
    </svg>
  );
}
