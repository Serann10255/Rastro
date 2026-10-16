/* Una diapositiva sobre su lienzo de 1920 × 1080.
 *
 * Tres formas: la portada, la portadilla de cada bloque y la diapositiva de
 * contenido, que lleva su bloque sobre el título. Todas llevan el mismo pie
 * —logotipo del proyecto y número— y una barra de avance fina en el borde
 * inferior.
 *
 * Lo que se ve y no se lee —una figura, una captura de pantalla, una galería—
 * va a la columna derecha; el texto, a la izquierda. En la portada el visual
 * sustituye al logotipo grande: la aplicación es la mejor carta de presentación.
 */

import { useContext, useEffect, useMemo, type ComponentType, type CSSProperties, type RefObject } from "react";

import { AnimacionContext } from "./animacion";
import { Bloques } from "./Bloques";
import { EnLinea, tituloLegible } from "./formato";
import { useDesborde } from "./medidas";
import {
  esVisual,
  type Deck,
  type Diapositiva as TipoDiapositiva,
  type DiapositivaBloque,
  type DiapositivaContenido,
} from "./tipos";

export interface PropiedadesLogotipo {
  tamano?: number;
  id?: string;
  className?: string;
}

export type Logotipo = ComponentType<PropiedadesLogotipo>;

/** Cómo está la diapositiva respecto a la transición del visor. */
export type EstadoTransicion = "entra" | "sale";

interface Propiedades {
  deck: Deck;
  indice: number;
  Logotipo: Logotipo;
  /** Distingue los identificadores del logotipo entre el visor y el guion. */
  ambito: string;
  /** Escala del lienzo; sin ella, la hereda del contenedor. */
  escala?: number;
  alDesbordar?: (clave: string, desborda: boolean) => void;
  /** Solo en el visor: anima la entrada o la salida. */
  estado?: EstadoTransicion;
  /** 1 hacia delante, -1 hacia atrás: de qué lado entra y por cuál sale. */
  direccion?: 1 | -1;
  /** Desde dónde crece la barra de avance: el avance de la diapositiva anterior. */
  avanceDesde?: number;
}

export function Diapositiva({
  deck,
  indice,
  Logotipo,
  ambito,
  escala,
  alDesbordar,
  estado,
  direccion,
  avanceDesde,
}: Propiedades) {
  const diapositiva = deck.diapositivas[indice]!;
  const [cuerpoRef, desborda] = useDesborde<HTMLDivElement>();
  const padre = useContext(AnimacionContext);
  // La diapositiva que sale deja de ser la activa: sus galerías se paran y no
  // anotan nada para ampliar.
  const animacion = useMemo(
    () => ({ ...padre, activa: padre.activa && estado !== "sale" }),
    [padre, estado],
  );

  useEffect(() => {
    alDesbordar?.(diapositiva.clave, desborda);
  }, [alDesbordar, diapositiva.clave, desborda]);

  const avance = ((indice + 1) / deck.diapositivas.length) * 100;
  const estilo = {
    ...(escala !== undefined && { "--zoom": escala }),
    ...(direccion !== undefined && { "--direccion": direccion }),
  } as CSSProperties;
  const idLogo = `logo-${ambito}-${diapositiva.clave}`;
  const clases = ["lienzo", `lienzo--${forma(diapositiva)}`, estado ? `lienzo--${estado}` : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <AnimacionContext.Provider value={animacion}>
      <div
        className={clases}
        style={estilo}
        data-desborda={desborda || undefined}
        aria-roledescription="diapositiva"
        aria-hidden={estado === "sale" || undefined}
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
          <span style={{ width: `${avance}%`, "--desde": `${avanceDesde ?? avance}%` } as CSSProperties} />
        </div>
      </div>
    </AnimacionContext.Provider>
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
  const visuales = diapositiva.bloques.filter(esVisual);
  const texto = diapositiva.bloques.filter((b) => !esVisual(b));
  const conVisual = visuales.length > 0;

  return (
    <div className={conVisual ? "portada portada--con-visual" : "portada"} ref={cuerpoRef}>
      {!conVisual && (
        <div className="portada__logo">
          <Logotipo tamano={300} id={idLogo} />
        </div>
      )}
      <div className="portada__texto">
        {conVisual && (
          <div className="portada__marca">
            <Logotipo tamano={132} id={idLogo} />
          </div>
        )}
        <h1 className="solo-lectores">{diapositiva.titulo}</h1>
        <Bloques bloques={texto} />
      </div>
      {conVisual && (
        <div className="portada__visual">
          <Bloques bloques={visuales} galeriaEnBucle />
        </div>
      )}
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
  const visuales = diapositiva.bloques.filter(esVisual);
  const resto = diapositiva.bloques.filter((b) => !esVisual(b));

  const bloque = diapositiva.bloque;

  return (
    <div className="lamina">
      {/* El bloque va sobre el título y no en el pie: sin portadillas, es lo
       *  único que le dice al jurado cuál de los siete bloques se está viendo. */}
      <header className="lamina__encabezado">
        {bloque && (
          <p className="lamina__bloque">
            {bloque.numero !== null ? `Bloque ${bloque.numero} · ` : ""}
            {tituloLegible(bloque.titulo)}
          </p>
        )}
        <h2 className="lamina__titulo">{diapositiva.titulo}</h2>
      </header>
      {visuales.length > 0 ? (
        // Con visual, el texto a la izquierda y el visual a la derecha: debajo
        // del texto quedaría demasiado pequeño para leerse.
        <div className="lamina__cuerpo lamina__cuerpo--con-visual" ref={cuerpoRef}>
          <div className="lamina__texto">
            <Bloques bloques={resto} />
          </div>
          <div className="lamina__visual">
            <Bloques bloques={visuales} />
          </div>
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
  const proyecto = String(deck.meta.proyecto ?? deck.titulo);

  return (
    <footer className="lienzo__pie">
      <Logotipo tamano={44} id={idLogo} className="lienzo__logo" />
      <span className="lienzo__proyecto">{proyecto}</span>
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
