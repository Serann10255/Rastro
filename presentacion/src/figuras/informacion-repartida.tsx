/* El problema, para público general: lo que se sabe de un paquete está en
 * cuatro sitios y ninguno manda.
 *
 * Son los cuatro de la Entrega 1 (memoria del mensajero, chat, hoja de cálculo
 * y teléfono del despachador). Las líneas son discontinuas a propósito: ninguna
 * fuente está conectada con el paquete de forma fiable.
 */

import { Caja, useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

export default function InformacionRepartida({ titulo }: PropiedadesFigura) {
  const tituloId = useIdSvg("titulo");

  return (
    <svg viewBox="0 0 820 700" role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>

      <path d="M190 140 L300 285" className="fig-linea fig-linea--discontinua" />
      <path d="M630 140 L520 285" className="fig-linea fig-linea--discontinua" />
      <path d="M190 560 L300 415" className="fig-linea fig-linea--discontinua" />
      <path d="M630 560 L520 415" className="fig-linea fig-linea--discontinua" />

      <Caja
        x={20}
        y={20}
        ancho={340}
        alto={120}
        variante="actor"
        lineas={[{ texto: "Memoria", estilo: "fuerte" }, { texto: "del mensajero", estilo: "suave" }]}
      />
      <Caja
        x={460}
        y={20}
        ancho={340}
        alto={120}
        variante="actor"
        lineas={[{ texto: "Un chat", estilo: "fuerte" }, { texto: "mensajes sueltos", estilo: "suave" }]}
      />
      <Caja
        x={20}
        y={560}
        ancho={340}
        alto={120}
        variante="actor"
        lineas={[{ texto: "Hoja de cálculo", estilo: "fuerte" }, { texto: "otra copia", estilo: "suave" }]}
      />
      <Caja
        x={460}
        y={560}
        ancho={340}
        alto={120}
        variante="actor"
        lineas={[{ texto: "Teléfono", estilo: "fuerte" }, { texto: "del despachador", estilo: "suave" }]}
      />

      <Caja
        x={235}
        y={285}
        ancho={350}
        alto={130}
        variante="acento"
        lineas={[{ texto: "El paquete", estilo: "fuerte" }, { texto: "¿dónde está?", estilo: "normal" }]}
      />
    </svg>
  );
}
