/* Qué sale al imprimir.
 *
 * Dos formatos con el mismo marcado:
 *
 * - `guion` (por omisión): una diapositiva por página horizontal con sus notas
 *   debajo, para llevar en papel.
 * - `diapositivas`: solo las diapositivas, cada una a página completa de 16:9
 *   (13,33 × 7,5 pulgadas, el formato panorámico de un deck), para guardar como
 *   PDF y entregar o proyectar desde otro equipo.
 *
 * El formato se marca en `data-impresion` sobre la raíz y la hoja de estilos
 * decide con él (véase presentacion.css). `?diapositivas` en la dirección lo fija
 * para toda la visita, que es lo que permite generar el PDF sin diálogos.
 */

export type FormatoImpresion = "guion" | "diapositivas";

export function formatoDesdeDireccion(): FormatoImpresion {
  return new URLSearchParams(window.location.search).has("diapositivas") ? "diapositivas" : "guion";
}

function aplicar(formato: FormatoImpresion) {
  if (formato === "diapositivas") document.documentElement.dataset.impresion = "diapositivas";
  else delete document.documentElement.dataset.impresion;
}

/** Aplica el formato de la dirección al cargar la página. */
export function aplicarFormatoDeLaDireccion() {
  aplicar(formatoDesdeDireccion());
}

/** Imprime en el formato pedido y, al cerrar el diálogo, vuelve al de la dirección. */
export function imprimir(formato: FormatoImpresion) {
  const restaurar = () => {
    aplicar(formatoDesdeDireccion());
    window.removeEventListener("afterprint", restaurar);
  };
  window.addEventListener("afterprint", restaurar);
  aplicar(formato);
  window.print();
}
