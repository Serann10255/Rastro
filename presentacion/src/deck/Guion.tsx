/* El guion: todas las diapositivas seguidas, cada una con sus notas debajo.
 *
 * Tiene tres usos y un solo marcado:
 *
 * - **Impresión.** Un documento de texto en vertical: por cada diapositiva,
 *   su número y título, quién la presenta y cuánto tarda, lo que se dice, la
 *   indicación y la respuesta preparada. Sin las láminas, que se descargan
 *   aparte con «PDF de diapositivas»: así el texto fluye y nunca se recorta.
 *   Se imprime desde cualquier modo.
 * - **Revisión** (`?guion`). Lo mismo en pantalla, con un aviso en cada
 *   diapositiva que no cabe en el lienzo. Es la forma de comprobar el deck
 *   después de cambiar el Markdown.
 * - **Lectura** en un teléfono en vertical, donde un lienzo de 16:9 se vería a
 *   un quinto de su tamaño. Ahí las diapositivas se reflujan como tarjetas.
 */

import { useCallback, useRef, useState } from "react";

import { Diapositiva, Notas, type Logotipo } from "./Diapositiva";
import { duracion, PALABRAS_POR_MINUTO, rangos, recuento, tituloLegible } from "./formato";
import { imprimir } from "./impresion";
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
                {recuento(deck.resumen)}. Guion hablado de {deck.resumen.palabras} palabras:{" "}
                {duracion(deck.resumen.palabras)} a {PALABRAS_POR_MINUTO} palabras por minuto.{" "}
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
            <button
              type="button"
              className="boton boton--secundario"
              onClick={() => imprimir("guion")}
              title="En el diálogo, destino «Guardar como PDF»: así se respetan la orientación apaisada y el tamaño"
            >
              Imprimir guion
            </button>
            <button
              type="button"
              className="boton boton--secundario"
              onClick={() => imprimir("diapositivas")}
              title="En el diálogo, destino «Guardar como PDF»: así se respetan la orientación apaisada y el tamaño"
            >
              PDF de diapositivas
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
          {/* El tamaño y la orientación los fija la hoja de estilos, pero el
           *  diálogo solo los respeta con «Guardar como PDF»; con una impresora
           *  del sistema manda el papel del controlador y sale vertical y
           *  partido. Se dice aquí, donde están los botones. */}
          <p className="guion__ayuda">
            <strong>Imprimir guion</strong> saca solo el texto, en vertical: por cada diapositiva, qué decir, cómo y qué
            responder. <strong>PDF de diapositivas</strong> saca las láminas a página completa; para esa, elija{" "}
            <strong>Guardar como PDF</strong> como destino y márgenes «Ninguno», o use{" "}
            <code className="d-codigo">npm run pdf</code> en <code className="d-codigo">presentacion/</code>.
          </p>
        </header>
      )}

      {/* Cabecera del guion impreso. En pantalla no se ve: la de arriba ya dice
       *  lo mismo y además tiene los botones. */}
      <header className="guion__documento">
        <p className="guion__documento-antetitulo">
          {String(deck.meta.asignatura ?? "")} · Grupo {String(deck.meta.grupo ?? "")}
        </p>
        <h1 className="guion__documento-titulo">{String(deck.meta.proyecto ?? deck.titulo)} · guion de sustentación</h1>
        <p>
          {recuento(deck.resumen)}. Guion hablado: {duracion(deck.resumen.palabras)} a {PALABRAS_POR_MINUTO} palabras por
          minuto. Las diapositivas van aparte, en el PDF de diapositivas.
        </p>
        <p className="guion__documento-reparto">
          {deck.resumen.intervenciones
            .map((i) => `${i.presentador}: ${rangos(i.numeros)} · ${duracion(i.palabras)}`)
            .join("  ·  ")}
        </p>
      </header>

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
            {d.tipo === "contenido" && d.bloque && (
              <p className="guion__bloque">
                {d.bloque.numero !== null ? `Bloque ${d.bloque.numero} · ` : ""}
                {tituloLegible(d.bloque.titulo)}
              </p>
            )}
            <p className="guion__rotulo">
              {d.tipo === "contenido" ? "Diapositiva " : ""}
              {rotulo(d)}
              {d.tipo === "contenido" && d.presentador && (
                <span className="guion__presenta">
                  {" "}
                  · {d.presentador} · {duracion(d.palabras)}
                </span>
              )}
            </p>
            <Notas diapositiva={d} />
          </div>
        </article>
      ))}
    </section>
  );
}
