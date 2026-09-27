/* El guion: todas las diapositivas seguidas, cada una con sus notas debajo.
 *
 * Tiene tres usos y un solo marcado:
 *
 * - **Impresión.** Cada diapositiva en una página horizontal con sus notas
 *   debajo, para llevar el guion en papel. Se imprime desde cualquier modo.
 * - **Revisión** (`?guion`). Lo mismo en pantalla, con un aviso en cada
 *   diapositiva que no cabe en el lienzo. Es la forma de comprobar el deck
 *   después de cambiar el Markdown.
 * - **Lectura** en un teléfono en vertical, donde un lienzo de 16:9 se vería a
 *   un quinto de su tamaño. Ahí las diapositivas se reflujan como tarjetas.
 */

import { useCallback, useRef, useState } from "react";

import { Diapositiva, Notas, type Logotipo } from "./Diapositiva";
import { tituloLegible } from "./formato";
import { useEscala } from "./medidas";
import { SelectorTema } from "./SelectorTema";
import type { Deck, Diapositiva as TipoDiapositiva } from "./tipos";

interface Propiedades {
  deck: Deck;
  Logotipo: Logotipo;
  /** `impresion`: oculto en pantalla. `revision`: lienzo escalado. `lectura`: fluido. */
  modo: "impresion" | "revision" | "lectura";
}

function rotulo(d: TipoDiapositiva): string {
  if (d.tipo === "bloque") {
    const titulo = tituloLegible(d.titulo);
    return d.numero !== null ? `Bloque ${d.numero} · ${titulo}` : titulo;
  }
  return `${d.numero} · ${d.titulo}`;
}

export function Guion({ deck, Logotipo, modo }: Propiedades) {
  const contenedorRef = useRef<HTMLElement>(null);
  const escala = useEscala(contenedorRef, true);
  const [desbordes, setDesbordes] = useState<Record<string, boolean>>({});
  // En lectura las notas empiezan ocultas, como en la presentación; en la
  // revisión se ven, porque revisarlas es parte del propósito.
  const [verNotas, setVerNotas] = useState(modo !== "lectura");

  const alDesbordar = useCallback((clave: string, desborda: boolean) => {
    setDesbordes((previo) => (previo[clave] === desborda ? previo : { ...previo, [clave]: desborda }));
  }, []);

  const desbordadas = deck.diapositivas.filter((d) => desbordes[d.clave]);
  const clases = ["guion", `guion--${modo}`, verNotas ? "" : "guion--sin-notas"].filter(Boolean).join(" ");

  return (
    <section className={clases} ref={contenedorRef} aria-label="Guion del presentador">
      {modo !== "impresion" && (
        <header className="guion__cabecera">
          <div className="guion__identidad">
            <Logotipo tamano={40} id={`logo-guion-${modo}`} />
            <div>
              <h1 className="guion__titulo">{String(deck.meta.proyecto ?? deck.titulo)} · guion</h1>
              <p className="guion__resumen">
                {deck.resumen.total} diapositivas: {deck.resumen.contenido} de contenido y {deck.resumen.bloques}{" "}
                portadillas de bloque.{" "}
                {modo === "revision" &&
                  (desbordadas.length === 0 ? (
                    <strong>Ninguna se desborda.</strong>
                  ) : (
                    <strong className="guion__alerta">
                      Se desbordan: {desbordadas.map((d) => d.clave).join(", ")}.
                    </strong>
                  ))}
              </p>
              <p className="guion__fuente">
                Fuente: <code className="d-codigo">{deck.archivo}</code>
              </p>
            </div>
          </div>
          <div className="guion__acciones">
            <a className="boton" href="./">
              Presentar
            </a>
            <button type="button" className="boton boton--secundario" onClick={() => window.print()}>
              Imprimir guion
            </button>
            <button
              type="button"
              className="boton boton--secundario"
              onClick={() => setVerNotas((v) => !v)}
              aria-pressed={verNotas}
            >
              {verNotas ? "Ocultar notas" : "Ver notas"}
            </button>
            <a className="boton boton--sutil" href="../">
              Inicio
            </a>
            <SelectorTema />
          </div>
        </header>
      )}

      {deck.diapositivas.map((d, indice) => (
        <article className="guion__pagina" key={d.clave} id={modo === "impresion" ? undefined : d.clave}>
          <div className="guion__marco">
            <Diapositiva
              deck={deck}
              indice={indice}
              Logotipo={Logotipo}
              ambito={`guion-${modo}`}
              escala={modo === "revision" ? escala : undefined}
              alDesbordar={alDesbordar}
            />
          </div>
          {desbordes[d.clave] && modo === "revision" && (
            <p className="aviso aviso--alerta guion__aviso">
              La diapositiva {d.clave} no cabe en el lienzo. Acorte el texto en el Markdown: la letra no se
              reduce por debajo del tamaño de cuerpo.
            </p>
          )}
          <div className="guion__notas">
            <p className="guion__rotulo">
              {rotulo(d)}
              {d.tipo === "contenido" && d.presentador && (
                <span className="guion__presenta"> · Presenta: {d.presentador}</span>
              )}
            </p>
            <Notas diapositiva={d} />
          </div>
        </article>
      ))}
    </section>
  );
}
