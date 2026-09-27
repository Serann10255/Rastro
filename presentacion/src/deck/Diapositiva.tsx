/* Una diapositiva sobre su lienzo de 1920 × 1080.
 *
 * Tres formas: la portada, la portadilla de cada bloque y la diapositiva de
 * contenido. Todas llevan el mismo pie —logotipo del proyecto, bloque en curso y
 * número— y una barra de avance fina en el borde inferior.
 */

import { useEffect, type ComponentType, type CSSProperties, type RefObject } from "react";

import { Bloques } from "./Bloques";
import { EnLinea, tituloLegible } from "./formato";
import { useDesborde } from "./medidas";
import type { Deck, Diapositiva as TipoDiapositiva, DiapositivaBloque, DiapositivaContenido } from "./tipos";

export interface PropiedadesLogotipo {
  tamano?: number;
  id?: string;
  className?: string;
}

export type Logotipo = ComponentType<PropiedadesLogotipo>;

interface Propiedades {
  deck: Deck;
  indice: number;
  Logotipo: Logotipo;
  /** Distingue los identificadores del logotipo entre el visor y el guion. */
  ambito: string;
  /** Escala del lienzo; sin ella, la hereda del contenedor. */
  escala?: number;
  alDesbordar?: (clave: string, desborda: boolean) => void;
}

export function Diapositiva({ deck, indice, Logotipo, ambito, escala, alDesbordar }: Propiedades) {
  const diapositiva = deck.diapositivas[indice]!;
  const [cuerpoRef, desborda] = useDesborde<HTMLDivElement>();

  useEffect(() => {
    alDesbordar?.(diapositiva.clave, desborda);
  }, [alDesbordar, diapositiva.clave, desborda]);

  const avance = ((indice + 1) / deck.diapositivas.length) * 100;
  const estilo = escala === undefined ? undefined : ({ "--zoom": escala } as CSSProperties);
  const idLogo = `logo-${ambito}-${diapositiva.clave}`;

  return (
    <div
      className={`lienzo lienzo--${forma(diapositiva)}`}
      style={estilo}
      data-desborda={desborda || undefined}
      aria-roledescription="diapositiva"
    >
      {diapositiva.tipo === "bloque" ? (
        <Portadilla diapositiva={diapositiva} cuerpoRef={cuerpoRef} />
      ) : diapositiva.portada ? (
        <Portada diapositiva={diapositiva} Logotipo={Logotipo} idLogo={idLogo} cuerpoRef={cuerpoRef} />
      ) : (
        <Contenido diapositiva={diapositiva} cuerpoRef={cuerpoRef} />
      )}

      <Pie deck={deck} diapositiva={diapositiva} Logotipo={Logotipo} idLogo={`${idLogo}-pie`} />
      <div className="lienzo__avance" aria-hidden="true">
        <span style={{ width: `${avance}%` }} />
      </div>
    </div>
  );
}

function forma(d: TipoDiapositiva): string {
  if (d.tipo === "bloque") return "bloque";
  return d.portada ? "portada" : "contenido";
}

type RefCuerpo = RefObject<HTMLDivElement>;

function Portada({
  diapositiva,
  Logotipo,
  idLogo,
  cuerpoRef,
}: {
  diapositiva: DiapositivaContenido;
  Logotipo: Logotipo;
  idLogo: string;
  cuerpoRef: RefCuerpo;
}) {
  return (
    <div className="portada" ref={cuerpoRef}>
      <div className="portada__logo">
        <Logotipo tamano={300} id={idLogo} />
      </div>
      <div className="portada__texto">
        <h1 className="solo-lectores">{diapositiva.titulo}</h1>
        <Bloques bloques={diapositiva.bloques} />
      </div>
    </div>
  );
}

function Portadilla({ diapositiva, cuerpoRef }: { diapositiva: DiapositivaBloque; cuerpoRef: RefCuerpo }) {
  return (
    <div className="portadilla" ref={cuerpoRef}>
      {diapositiva.numero !== null && <p className="portadilla__numero">Bloque {diapositiva.numero}</p>}
      <h2 className="portadilla__titulo">{tituloLegible(diapositiva.titulo)}</h2>
      {diapositiva.contenido.length > 0 && (
        <ol className="portadilla__sumario">
          {diapositiva.contenido.map((d) => (
            <li key={d.numero}>
              <span className="portadilla__cifra">{d.numero}</span>
              {d.titulo}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Contenido({ diapositiva, cuerpoRef }: { diapositiva: DiapositivaContenido; cuerpoRef: RefCuerpo }) {
  const figuras = diapositiva.bloques.filter((b) => b.tipo === "figura");
  const resto = diapositiva.bloques.filter((b) => b.tipo !== "figura");

  return (
    <div className="lamina">
      <h2 className="lamina__titulo">{diapositiva.titulo}</h2>
      {figuras.length > 0 ? (
        // Con figura, el texto a la izquierda y la figura a la derecha: una
        // figura bajo el texto quedaría demasiado pequeña para leerse.
        <div className="lamina__cuerpo lamina__cuerpo--con-figura" ref={cuerpoRef}>
          <div className="lamina__texto">
            <Bloques bloques={resto} />
          </div>
          <Bloques bloques={figuras} />
        </div>
      ) : (
        <div className="lamina__cuerpo" ref={cuerpoRef}>
          <Bloques bloques={resto} />
        </div>
      )}
    </div>
  );
}

function Pie({
  deck,
  diapositiva,
  Logotipo,
  idLogo,
}: {
  deck: Deck;
  diapositiva: TipoDiapositiva;
  Logotipo: Logotipo;
  idLogo: string;
}) {
  const ultima = [...deck.diapositivas].reverse().find((d) => d.tipo === "contenido");
  const total = ultima?.tipo === "contenido" ? ultima.numero : deck.resumen.contenido;
  const bloque = diapositiva.tipo === "bloque" ? null : diapositiva.bloque;
  const proyecto = String(deck.meta.proyecto ?? deck.titulo);

  return (
    <footer className="lienzo__pie">
      <Logotipo tamano={44} id={idLogo} className="lienzo__logo" />
      <span className="lienzo__proyecto">{proyecto}</span>
      {bloque && (
        <span className="lienzo__bloque">
          {bloque.numero !== null ? `Bloque ${bloque.numero} · ` : ""}
          {tituloLegible(bloque.titulo)}
        </span>
      )}
      <span className="lienzo__numero">
        {diapositiva.tipo === "contenido" ? (
          <>
            {diapositiva.numero}
            <span className="lienzo__total"> / {total}</span>
          </>
        ) : (
          <>Bloque {diapositiva.numero ?? ""}</>
        )}
      </span>
    </footer>
  );
}

/** El texto de las notas, para el visor y para el guion. */
/** Lo que acompaña a la diapositiva: primero lo que se dice, que es lo que se
 *  lee de reojo; después cómo decirlo y las respuestas preparadas, en menor
 *  jerarquía. */
export function Notas({ diapositiva }: { diapositiva: TipoDiapositiva }) {
  if (diapositiva.tipo === "bloque") {
    return <p className="notas__vacio">Portadilla: se pasa sin detenerse.</p>;
  }
  if (diapositiva.notas.length === 0) return <p className="notas__vacio">Sin guion.</p>;

  const guion = diapositiva.notas.filter((n) => n.tipo === "guion");
  const resto = diapositiva.notas.filter((n) => n.tipo !== "guion");
  return (
    <>
      {guion.map((nota, i) => (
        <p key={`g${i}`} className="notas__guion">
          {nota.presentador && <strong className="notas__presentador">{nota.presentador}: </strong>}
          <EnLinea nodos={nota.texto} />
        </p>
      ))}
      {resto.map((nota, i) => (
        <p key={`n${i}`} className={`notas__apoyo notas__apoyo--${nota.tipo}`}>
          <span className="notas__etiqueta">{nota.tipo === "pregunta" ? "Si preguntan" : "Indicación"}</span>{" "}
          <EnLinea nodos={nota.texto} />
        </p>
      ))}
    </>
  );
}

