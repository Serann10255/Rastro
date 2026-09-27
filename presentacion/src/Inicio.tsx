/* Índice de las sustentaciones.
 *
 * Todo lo que muestra sale de los dos guiones: metadatos, recuento de
 * diapositivas y reparto de intervenciones, que se deduce del guion
 * («Guion: Sergio. …»). Sirve para ensayar: se ve de un vistazo quién presenta
 * qué, cuánto habla cada uno y si el reparto está equilibrado.
 */

import type { ComponentType } from "react";

import type { PropiedadesLogotipo } from "@/deck/Diapositiva";
import { duracion, PALABRAS_POR_MINUTO } from "@/deck/formato";
import { SelectorTema } from "@/deck/SelectorTema";
import type { Deck } from "@/deck/tipos";

interface EntradaDeck {
  deck: Deck;
  ruta: string;
  Logotipo: ComponentType<PropiedadesLogotipo>;
}

const TECLAS: [string, string][] = [
  ["→ ↓ Av Pág Espacio", "Siguiente diapositiva"],
  ["← ↑ Re Pág Mayús+Espacio", "Diapositiva anterior"],
  ["Clic en el borde derecho o izquierdo", "Siguiente o anterior"],
  ["Inicio · Fin", "Primera · última"],
  ["N", "Mostrar u ocultar el guion de la diapositiva: qué decir, cómo y qué responder"],
  ["F", "Entrar o salir de pantalla completa"],
  ["Ctrl+P", "Imprimir el guion: una diapositiva por página, con su texto hablado debajo"],
];

function rangos(numeros: number[]): string {
  const partes: string[] = [];
  let inicio = numeros[0];
  let previo = numeros[0];
  for (const n of [...numeros.slice(1), Number.NaN]) {
    if (inicio === undefined || previo === undefined) break;
    if (n === previo + 1) {
      previo = n;
      continue;
    }
    partes.push(inicio === previo ? String(inicio) : `${inicio}–${previo}`);
    inicio = n;
    previo = n;
  }
  return partes.join(", ");
}

function texto(valor: string | string[] | undefined): string {
  return Array.isArray(valor) ? valor.join(", ") : (valor ?? "");
}

export function Inicio({ decks }: { decks: EntradaDeck[] }) {
  const primero = decks[0]?.deck.meta ?? {};

  return (
    <div className="inicio">
      <header className="inicio__cabecera">
        <div>
          <p className="inicio__antetitulo">Grupo {texto(primero.grupo)}</p>
          <h1 className="inicio__titulo">Sustentaciones</h1>
          <p className="inicio__descripcion">
            Docente: {texto(primero.docente)}. Equipo: {texto(primero.equipo)}.
          </p>
        </div>
        <SelectorTema />
      </header>

      <main className="inicio__decks">
        {decks.map(({ deck, ruta, Logotipo }) => (
          <article className="tarjeta tarjeta-deck" key={ruta}>
            <div className="tarjeta__cuerpo tarjeta-deck__cuerpo">
              <div className="tarjeta-deck__marca">
                <Logotipo tamano={56} id={`logo-inicio-${ruta}`} />
                <div className="min-cero">
                  <h2 className="tarjeta-deck__nombre">{texto(deck.meta.proyecto)}</h2>
                  <p className="texto-suave">{texto(deck.meta.asignatura)}</p>
                </div>
              </div>
              <p>{texto(deck.meta.subtitulo)}</p>
              <p className="texto-suave texto-sm">
                {deck.resumen.total} diapositivas: {deck.resumen.contenido} de contenido y {deck.resumen.bloques}{" "}
                portadillas de bloque. Guion hablado: {duracion(deck.resumen.palabras)}.
              </p>
              <div className="acciones">
                <a className="boton" href={`${ruta}/`}>
                  Presentar
                </a>
                <a className="boton boton--secundario" href={`${ruta}/?guion`}>
                  Guion y revisión
                </a>
              </div>

              <div className="tabla-contenedor">
                <table className="tabla">
                  <caption className="tarjeta-deck__leyenda">Quién presenta qué</caption>
                  <thead>
                    <tr>
                      <th scope="col">Integrante</th>
                      <th scope="col">Diapositivas</th>
                      <th scope="col" className="tabla__numero">
                        Cuántas
                      </th>
                      <th scope="col" className="tabla__numero">
                        Tiempo
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {deck.resumen.intervenciones.map((i) => (
                      <tr key={i.presentador}>
                        <td>{i.presentador}</td>
                        <td className="envuelve">{rangos(i.numeros)}</td>
                        <td className="tabla__numero">{i.numeros.length}</td>
                        <td className="tabla__numero">{duracion(i.palabras)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="texto-tenue texto-xs">
                Tiempo estimado a {PALABRAS_POR_MINUTO} palabras por minuto. Cronométrense en voz alta.
              </p>
              <p className="texto-tenue texto-xs mono">{deck.archivo}</p>
            </div>
          </article>
        ))}
      </main>

      <section className="tarjeta inicio__teclas" aria-labelledby="titulo-teclas">
        <div className="tarjeta__cabecera">
          <h2 className="tarjeta__titulo" id="titulo-teclas">
            Durante la presentación
          </h2>
        </div>
        <div className="tabla-contenedor">
          <table className="tabla">
            <tbody>
              {TECLAS.map(([tecla, accion]) => (
                <tr key={tecla}>
                  <th scope="row">
                    <kbd>{tecla}</kbd>
                  </th>
                  <td className="envuelve">{accion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="pie">
        <span>
          Las diapositivas se generan al construir desde <code>documentacion/sustentacion/</code>. Para cambiarlas se
          edita el Markdown, no este sitio.
        </span>
      </footer>
    </div>
  );
}

