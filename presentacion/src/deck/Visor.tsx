/* Modo presentación: una diapositiva a pantalla, escalada para caber.
 *
 * Teclas: flechas, Av Pág/Re Pág y barra espaciadora para avanzar y retroceder,
 * Inicio y Fin para los extremos, `n` para las notas y `f` para la pantalla
 * completa. Un clic en el borde izquierdo o derecho hace lo mismo que las
 * flechas. La dirección siempre dice dónde se está (`/rastro#7`), de modo que
 * recargar o compartir el enlace retoma en la misma diapositiva.
 *
 * Sin transiciones entre diapositivas: se cambia de una a otra en seco.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { Diapositiva, Notas, type Logotipo } from "./Diapositiva";
import { tituloLegible } from "./formato";
import { useEscala } from "./medidas";
import { SelectorTema } from "./SelectorTema";
import type { Deck, Diapositiva as TipoDiapositiva } from "./tipos";

/** Tiempo sin mover el ratón tras el que se ocultan los controles. */
const INACTIVIDAD_MS = 2500;

function rotulo(d: TipoDiapositiva): string {
  if (d.tipo === "contenido") return `${d.numero} · ${d.titulo}`;
  return `${d.numero !== null ? `Bloque ${d.numero} · ` : ""}${tituloLegible(d.titulo)}`;
}

function indiceDesdeDireccion(deck: Deck): number | null {
  const clave = decodeURIComponent(window.location.hash.slice(1));
  if (!clave) return null;
  const indice = deck.diapositivas.findIndex((d) => d.clave === clave);
  return indice >= 0 ? indice : null;
}

export function Visor({ deck, Logotipo }: { deck: Deck; Logotipo: Logotipo }) {
  const total = deck.diapositivas.length;
  const [indice, setIndice] = useState(() => indiceDesdeDireccion(deck) ?? 0);
  const [verNotas, setVerNotas] = useState(false);
  const [completa, setCompleta] = useState(false);
  const [activo, setActivo] = useState(true);
  const [desbordes, setDesbordes] = useState<Record<string, boolean>>({});

  const escenarioRef = useRef<HTMLElement>(null);
  const escala = useEscala(escenarioRef);

  const ir = useCallback((destino: number) => setIndice(Math.min(Math.max(destino, 0), total - 1)), [total]);
  const alternarPantallaCompleta = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.().catch(() => undefined);
  }, []);

  // -- Teclado ---------------------------------------------------------------
  useEffect(() => {
    const alPulsar = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const objetivo = e.target as HTMLElement | null;
      const enControl = objetivo?.closest("button, a, input, textarea, select, [contenteditable]");

      switch (e.key) {
        case "ArrowRight":
        case "ArrowDown":
        case "PageDown":
          ir(indice + 1);
          break;
        case "ArrowLeft":
        case "ArrowUp":
        case "PageUp":
          ir(indice - 1);
          break;
        case " ":
          // Sobre un botón, la barra lo pulsa; no debe además cambiar de página.
          if (enControl) return;
          ir(e.shiftKey ? indice - 1 : indice + 1);
          break;
        case "Home":
          ir(0);
          break;
        case "End":
          ir(total - 1);
          break;
        case "n":
        case "N":
          setVerNotas((v) => !v);
          break;
        case "f":
        case "F":
          alternarPantallaCompleta();
          break;
        default:
          return;
      }
      e.preventDefault();
    };
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, [indice, ir, total, alternarPantallaCompleta]);

  // -- Dirección: la diapositiva actual va en la almohadilla -----------------
  useEffect(() => {
    const clave = deck.diapositivas[indice]!.clave;
    if (decodeURIComponent(window.location.hash.slice(1)) !== clave) {
      // Sustituir y no apilar: «atrás» en el navegador sale del deck en lugar
      // de deshacer una a una las diapositivas vistas.
      window.history.replaceState(null, "", `#${clave}`);
    }
  }, [deck, indice]);

  useEffect(() => {
    const alCambiar = () => {
      const destino = indiceDesdeDireccion(deck);
      if (destino !== null) setIndice(destino);
    };
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, [deck]);

  // -- Pantalla completa -----------------------------------------------------
  useEffect(() => {
    const alCambiar = () => setCompleta(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", alCambiar);
    return () => document.removeEventListener("fullscreenchange", alCambiar);
  }, []);

  // -- Controles que se apartan cuando no se usan ----------------------------
  useEffect(() => {
    let temporizador = window.setTimeout(() => setActivo(false), INACTIVIDAD_MS);
    const alMover = () => {
      setActivo(true);
      window.clearTimeout(temporizador);
      temporizador = window.setTimeout(() => setActivo(false), INACTIVIDAD_MS);
    };
    window.addEventListener("pointermove", alMover);
    window.addEventListener("pointerdown", alMover);
    return () => {
      window.clearTimeout(temporizador);
      window.removeEventListener("pointermove", alMover);
      window.removeEventListener("pointerdown", alMover);
    };
  }, []);

  const alDesbordar = useCallback((clave: string, desborda: boolean) => {
    setDesbordes((previo) => (previo[clave] === desborda ? previo : { ...previo, [clave]: desborda }));
    if (desborda) console.warn(`La diapositiva «${clave}» no cabe en el lienzo.`);
  }, []);

  const actual = deck.diapositivas[indice]!;
  const siguiente = deck.diapositivas[indice + 1];
  const rotuloActual = rotulo(actual);

  return (
    <div className="visor" data-inactivo={!activo || undefined}>
      <main className="visor__escenario" ref={escenarioRef} aria-label={String(deck.meta.proyecto ?? deck.titulo)}>
        <Diapositiva
          key={actual.clave}
          deck={deck}
          indice={indice}
          Logotipo={Logotipo}
          ambito="visor"
          escala={escala}
          alDesbordar={alDesbordar}
        />

        <button
          type="button"
          className="visor__borde visor__borde--anterior"
          onClick={() => ir(indice - 1)}
          disabled={indice === 0}
          aria-label="Diapositiva anterior"
        >
          <span aria-hidden="true">‹</span>
        </button>
        <button
          type="button"
          className="visor__borde visor__borde--siguiente"
          onClick={() => ir(indice + 1)}
          disabled={indice === total - 1}
          aria-label="Diapositiva siguiente"
        >
          <span aria-hidden="true">›</span>
        </button>

        <nav className="visor__controles" aria-label="Controles de la presentación">
          <button
            type="button"
            className="boton boton--sutil"
            onClick={() => setVerNotas((v) => !v)}
            aria-pressed={verNotas}
          >
            Guion <kbd>N</kbd>
          </button>
          <button type="button" className="boton boton--sutil" onClick={alternarPantallaCompleta} aria-pressed={completa}>
            {completa ? "Salir de pantalla completa" : "Pantalla completa"} <kbd>F</kbd>
          </button>
          <a className="boton boton--sutil" href="?guion">
            Guion completo
          </a>
          <a className="boton boton--sutil" href="../">
            Inicio
          </a>
          <SelectorTema />
        </nav>
      </main>

      {verNotas && (
        <aside className="visor__notas" aria-label="Guion de la diapositiva">
          <div className="visor__notas-cabecera">
            <p className="visor__notas-titulo">{rotuloActual}</p>
            <p className="visor__notas-posicion">
              {indice + 1} de {total}
            </p>
          </div>
          {desbordes[actual.clave] && (
            <p className="aviso aviso--alerta">Esta diapositiva no cabe en el lienzo: revise el guion.</p>
          )}
          <Notas diapositiva={actual} />
          {siguiente && (
            <p className="visor__siguiente">
              Siguiente: {rotulo(siguiente)}
            </p>
          )}
        </aside>
      )}

      <p className="solo-lectores" aria-live="polite">
        {rotuloActual}
      </p>
    </div>
  );
}
