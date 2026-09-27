/* Medidas del lienzo: escala para que quepa y comprobación de desborde. */

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

/** El lienzo se diseña a 1920 × 1080 y se escala entero. Así «24 px» significa
 *  lo mismo en el portátil del ensayo que en el proyector. */
export const ANCHO_LIENZO = 1920;
export const ALTO_LIENZO = 1080;

/** Escala que hace caber el lienzo en el elemento observado. Con `soloAncho`
 *  se ajusta al ancho y la altura queda libre, como en el guion. */
export function useEscala(ref: RefObject<HTMLElement>, soloAncho = false): number {
  const [escala, setEscala] = useState(1);

  useLayoutEffect(() => {
    const elemento = ref.current;
    if (!elemento) return;
    const medir = () => {
      const estilo = getComputedStyle(elemento);
      const ancho = elemento.clientWidth - parseFloat(estilo.paddingLeft) - parseFloat(estilo.paddingRight);
      const alto = elemento.clientHeight - parseFloat(estilo.paddingTop) - parseFloat(estilo.paddingBottom);
      const porAncho = ancho / ANCHO_LIENZO;
      const nueva = soloAncho ? porAncho : Math.min(porAncho, alto / ALTO_LIENZO);
      if (nueva > 0) setEscala(nueva);
    };
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => observador.disconnect();
  }, [ref, soloAncho]);

  return escala;
}

/**
 * Indica si el contenido no cabe en su caja. Se mide sin escalar, de modo que
 * el resultado es el mismo a cualquier tamaño de pantalla: una diapositiva que
 * se desborda en el proyector se desborda también en el ensayo.
 */
export function useDesborde<T extends HTMLElement>(): [RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [desborda, setDesborda] = useState(false);

  useEffect(() => {
    const elemento = ref.current;
    if (!elemento) return;
    const medir = () =>
      setDesborda(
        elemento.scrollHeight - elemento.clientHeight > 2 || elemento.scrollWidth - elemento.clientWidth > 2,
      );
    medir();
    // La tipografía del sistema puede llegar después del primer pintado y
    // cambiar lo que ocupa cada línea.
    void document.fonts?.ready.then(medir);
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    for (const hijo of Array.from(elemento.children)) observador.observe(hijo);
    return () => observador.disconnect();
  }, []);

  return [ref, desborda];
}

/** Coincidencia con una consulta de medios, viva. */
export function useConsulta(consulta: string): boolean {
  const [coincide, setCoincide] = useState(() => window.matchMedia(consulta).matches);
  useEffect(() => {
    const lista = window.matchMedia(consulta);
    const alCambiar = () => setCoincide(lista.matches);
    alCambiar();
    lista.addEventListener("change", alCambiar);
    return () => lista.removeEventListener("change", alCambiar);
  }, [consulta]);
  return coincide;
}
