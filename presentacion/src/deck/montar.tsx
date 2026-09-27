/* Punto de montaje común de los dos decks.
 *
 * Elige el modo: el guion si la dirección lleva `?guion`, la lectura reflujada
 * en un teléfono en vertical y, en cualquier otro caso, la presentación. El
 * guion para imprimir se monta siempre, oculto en pantalla, para que imprimir
 * desde la presentación saque el guion completo y no la diapositiva visible.
 * Con `?diapositivas`, lo que se imprime son solo las diapositivas, a página
 * completa (véase impresion.ts).
 */

import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";

import { Guion } from "./Guion";
import type { Logotipo } from "./Diapositiva";
import { aplicarFormatoDeLaDireccion } from "./impresion";
import { useConsulta } from "./medidas";
import { temaAlImprimir } from "./SelectorTema";
import type { Deck } from "./tipos";
import { Visor } from "./Visor";

/** Por debajo de `md` y en vertical, el lienzo de 16:9 no se lee. */
const CONSULTA_LECTURA = "(max-width: 767px) and (orientation: portrait)";

function Presentacion({ deck, Logotipo }: { deck: Deck; Logotipo: Logotipo }) {
  const revision = new URLSearchParams(window.location.search).has("guion");
  const lectura = useConsulta(CONSULTA_LECTURA);

  useEffect(() => temaAlImprimir(), []);

  if (revision || lectura) {
    return <Guion deck={deck} Logotipo={Logotipo} modo={lectura ? "lectura" : "revision"} />;
  }
  return (
    <>
      <Visor deck={deck} Logotipo={Logotipo} />
      <Guion deck={deck} Logotipo={Logotipo} modo="impresion" />
    </>
  );
}

export function montar(deck: Deck, Logotipo: Logotipo) {
  const raiz = document.getElementById("raiz");
  if (!raiz) throw new Error("No se encontró el nodo raíz.");
  aplicarFormatoDeLaDireccion();
  createRoot(raiz).render(
    <StrictMode>
      <Presentacion deck={deck} Logotipo={Logotipo} />
    </StrictMode>,
  );
}
