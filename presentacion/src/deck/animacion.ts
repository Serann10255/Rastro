/* Qué se mueve y dónde.
 *
 * Solo el visor anima: la transición entre diapositivas, la entrada escalonada
 * del contenido, las cifras que cuentan, las galerías que pasan solas. El
 * guion, la lectura en el teléfono y el papel se dibujan quietos, con cada
 * galería en su elemento de reposo. Este contexto es lo que se lo dice a cada
 * pieza, y también por dónde el visor ofrece ampliar una captura.
 */

import { createContext, useContext } from "react";

import type { Visual } from "./tipos";

export interface Animacion {
  /** Verdadero solo dentro del visor. */
  animado: boolean;
  /** Falso en la diapositiva que sale durante la transición: sus galerías se
   *  detienen y no registran nada. */
  activa: boolean;
  /** Amplía un visual a toda la pantalla. Sin ella, pulsar no hace nada. */
  ampliar?: (visual: Visual) => void;
  /** Anota el visual que se ampliaría al pulsar `z`: el de la galería en curso. */
  registrar?: (visual: Visual | null) => void;
}

export const AnimacionContext = createContext<Animacion>({ animado: false, activa: true });

export function useAnimacion(): Animacion {
  return useContext(AnimacionContext);
}

/** Quien pide menos movimiento lo tiene: ni transiciones ni contadores. */
export function prefiereMenosMovimiento(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
