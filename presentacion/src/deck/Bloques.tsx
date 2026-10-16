/* Dibujo de los bloques de una diapositiva.
 *
 * Las tablas se leen a distancia: letra de cuerpo, celdas holgadas y sin la
 * retícula de una tabla de documento. Algunos valores llevan tono propio, y
 * siempre por su texto, nunca solo por el color: la marca «✓», el «—» de lo
 * vedado, los niveles de probabilidad, impacto o prioridad, y las tres
 * conclusiones de Cotejo con los mismos colores que usa su interfaz.
 *
 * Cada bloque lleva su posición en `--i` y cada fila o elemento la suya en
 * `--j`: con eso la hoja de estilos escalona la entrada en el visor. Fuera del
 * visor esas variables no hacen nada.
 */

import { useEffect, useState, type ComponentType, type CSSProperties, type ReactNode } from "react";

import { CAPTURAS } from "@/capturas";
import { FIGURAS, type PropiedadesFigura } from "@/figuras";

import { prefiereMenosMovimiento, useAnimacion } from "./animacion";
import { EnLinea, Lineas, textoPlano } from "./formato";
import type { Alineacion, Bloque, Cifra, Linea, Visual } from "./tipos";

interface PropiedadesBloques {
  bloques: Bloque[];
  /** En la portada la galería da vueltas; en el resto pasa una vez y se queda
   *  en el último elemento, que es el que se imprime. */
  galeriaEnBucle?: boolean;
}

export function Bloques({ bloques, galeriaEnBucle = false }: PropiedadesBloques) {
  return (
    <>
      {bloques.map((bloque, i) => (
        <BloqueUnico key={i} bloque={bloque} indice={i} galeriaEnBucle={galeriaEnBucle} />
      ))}
    </>
  );
}

function orden(i: number): CSSProperties {
  return { "--i": i } as CSSProperties;
}

function BloqueUnico({
  bloque,
  indice,
  galeriaEnBucle,
}: {
  bloque: Bloque;
  indice: number;
  galeriaEnBucle: boolean;
}) {
  const estilo = orden(indice);
  switch (bloque.tipo) {
    case "parrafo": {
      // Un párrafo que es solo un dato en código (una cuenta, un repositorio) se
      // presenta como dato, no como frase.
      const soloCodigo = bloque.lineas.every((l) => l.length === 1 && l[0]!.t === "codigo");
      return (
        <p className={soloCodigo ? "d-parrafo d-parrafo--dato d-animable" : "d-parrafo d-animable"} style={estilo}>
          <Lineas lineas={bloque.lineas} />
        </p>
      );
    }
    case "subtitulo":
      return (
        <h3 className="d-subtitulo d-animable" style={estilo}>
          <EnLinea nodos={bloque.linea} />
        </h3>
      );
    case "lista": {
      const elementos = bloque.elementos.map((linea, j) => (
        <li key={j} style={{ "--j": j } as CSSProperties}>
          <EnLinea nodos={linea} />
        </li>
      ));
      return bloque.ordenada ? (
        <ol className="d-lista d-lista--ordenada" start={bloque.inicio} style={estilo}>
          {elementos}
        </ol>
      ) : (
        <ul className="d-lista" style={estilo}>
          {elementos}
        </ul>
      );
    }
    case "tabla":
      return (
        <Tabla encabezado={bloque.encabezado} filas={bloque.filas} alineacion={bloque.alineacion} estilo={estilo} />
      );
    case "cita":
      return (
        <blockquote className="d-cita d-animable" style={estilo}>
          <EnLinea nodos={bloque.linea} />
        </blockquote>
      );
    case "resultado":
      return <Resultado cifras={bloque.cifras} estilo={estilo} />;
    case "codigo":
      return (
        <pre className="d-bloque-codigo d-animable" style={estilo}>
          <code>{bloque.texto}</code>
        </pre>
      );
    case "figura":
      return <Figura visual={bloque} estilo={estilo} />;
    case "captura":
      return <Captura visual={bloque} estilo={estilo} />;
    case "galeria":
      return <Galeria elementos={bloque.elementos} bucle={galeriaEnBucle} estilo={estilo} />;
  }
}

/* ------------------------------------------------------------------------ */
/* Tablas                                                                   */
/* ------------------------------------------------------------------------ */

const COLUMNAS_DE_NIVEL = /^(prob\.?|probabilidad|impacto|prioridad|severidad)$/i;

const NIVELES: Record<string, string> = {
  "muy alto": "muy-alto",
  "muy alta": "muy-alto",
  alto: "alto",
  alta: "alto",
  medio: "medio",
  media: "medio",
  bajo: "bajo",
  baja: "bajo",
};

const VEREDICTOS: Record<string, string> = {
  BIEN: "bien",
  MAL: "mal",
  "SIN REVISAR": "sin-revisar",
};

function claseAlineacion(alineacion: Alineacion): string | undefined {
  if (alineacion === "centro") return "d-alinear--centro";
  if (alineacion === "derecha") return "d-alinear--derecha";
  return undefined;
}

function Celda({
  linea,
  columnaDeNivel,
  columnaDeMarcas,
}: {
  linea: Linea;
  columnaDeNivel: boolean;
  /** Columna centrada de una matriz: ✓, — o un permiso con condiciones. */
  columnaDeMarcas: boolean;
}) {
  const texto = textoPlano(linea).trim();

  if (texto === "✓") return <span className="d-marca d-marca--si" aria-label="Sí">✓</span>;
  if (texto === "—") return <span className="d-marca d-marca--no" aria-label="No">—</span>;
  // «Solo suyos» es un permiso con condiciones solo dentro de una matriz; en
  // una columna de texto, «Solo el rol auditor…» es una frase cualquiera.
  if (columnaDeMarcas && /^solo\s/i.test(texto)) {
    return (
      <span className="d-marca d-marca--parcial">
        <EnLinea nodos={linea} />
      </span>
    );
  }

  const nivel = columnaDeNivel ? NIVELES[texto.toLocaleLowerCase("es")] : undefined;
  if (nivel) {
    return (
      <span className={`d-nivel d-nivel--${nivel}`}>
        <EnLinea nodos={linea} />
      </span>
    );
  }

  return <EnLinea nodos={linea} />;
}

function Tabla({
  encabezado,
  filas,
  alineacion,
  estilo,
}: {
  encabezado: Linea[] | null;
  filas: Linea[][];
  alineacion: Alineacion[];
  estilo: CSSProperties;
}) {
  const columnasDeNivel = (encabezado ?? []).map((c) => COLUMNAS_DE_NIVEL.test(textoPlano(c).trim()));
  // Sin encabezado, la primera columna nombra la fila: «Condición», «Criterio»…
  const encabezaFilas = encabezado === null;
  const fila = (j: number): CSSProperties => ({ "--j": j } as CSSProperties);

  return (
    <div className="d-tabla-contenedor" style={estilo}>
      <table className={encabezaFilas ? "d-tabla d-tabla--por-filas" : "d-tabla"}>
        {encabezado && (
          <thead>
            <tr style={fila(0)}>
              {encabezado.map((celda, c) => (
                <th key={c} scope="col" className={claseAlineacion(alineacion[c] ?? null)}>
                  <EnLinea nodos={celda} />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {filas.map((celdas, f) => {
            const veredicto = encabezaFilas ? VEREDICTOS[textoPlano(celdas[0] ?? []).trim()] : undefined;
            return (
              <tr
                key={f}
                className={veredicto ? `d-veredicto d-veredicto--${veredicto}` : undefined}
                style={fila(f + (encabezado ? 1 : 0))}
              >
                {celdas.map((celda, c) => {
                  const contenido = (
                    <Celda
                      linea={celda}
                      columnaDeNivel={columnasDeNivel[c] ?? false}
                      columnaDeMarcas={alineacion[c] === "centro"}
                    />
                  );
                  const clase = claseAlineacion(alineacion[c] ?? null);
                  return encabezaFilas && c === 0 ? (
                    <th key={c} scope="row" className={clase}>
                      {contenido}
                    </th>
                  ) : (
                    <td key={c} className={clase}>
                      {contenido}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* Cifras de resultado                                                      */
/* ------------------------------------------------------------------------ */

/** Tono de una cifra por lo que cuenta: lo superado en verde, un fallo o una
 *  desviación en rojo solo si hay alguno. Cero fallos no es una alarma. */
function tono(cifra: Cifra): "exito" | "peligro" | "neutro" {
  const etiqueta = cifra.etiqueta.toLocaleLowerCase("es");
  const valor = Number(cifra.valor.replace(/[.,]/g, ""));
  if (/superad|conforme/.test(etiqueta)) return "exito";
  if (/fallo|desviad/.test(etiqueta)) return valor > 0 ? "peligro" : "neutro";
  return "neutro";
}

const CONTADOR_RETARDO_MS = 350;
const CONTADOR_DURACION_MS = 1100;

/** En el visor, la cifra cuenta desde cero hasta su valor; en el resto se
 *  muestra tal cual. Solo los enteros cuentan: «3.400» se queda quieto. */
function Contador({ valor }: { valor: string }) {
  const { animado } = useAnimacion();
  const numero = /^\d+$/.test(valor) ? Number(valor) : null;
  const cuenta = animado && numero !== null && !prefiereMenosMovimiento();
  const [actual, setActual] = useState(cuenta ? "0" : valor);

  useEffect(() => {
    if (!cuenta || numero === null) {
      setActual(valor);
      return;
    }
    const inicio = performance.now();
    let cuadro = 0;
    const paso = (ahora: number) => {
      const avance = Math.min(1, Math.max(0, (ahora - inicio - CONTADOR_RETARDO_MS) / CONTADOR_DURACION_MS));
      const suave = 1 - Math.pow(1 - avance, 3);
      setActual(String(Math.round(numero * suave)));
      if (avance < 1) cuadro = requestAnimationFrame(paso);
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [cuenta, numero, valor]);

  return <>{actual}</>;
}

function Resultado({ cifras, estilo }: { cifras: Cifra[]; estilo: CSSProperties }) {
  return (
    <dl className="d-resultado" style={estilo}>
      {cifras.map((cifra, j) => (
        <div key={j} className={`d-cifra d-cifra--${tono(cifra)}`} style={{ "--j": j } as CSSProperties}>
          <dt className="d-cifra__etiqueta">{cifra.etiqueta}</dt>
          <dd className="d-cifra__valor">
            <Contador valor={cifra.valor} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------------ */
/* Figuras, capturas y galerías                                             */
/* ------------------------------------------------------------------------ */

/** Anota en el visor cuál es el visual que se ampliaría con `z`. */
function useRegistro(visual: Visual, activo = true) {
  const { activa, registrar } = useAnimacion();
  useEffect(() => {
    if (!activa || !activo || !registrar) return;
    registrar(visual);
    return () => registrar(null);
  }, [activa, activo, registrar, visual]);
}

export function Figura({ visual, estilo }: { visual: Visual; estilo?: CSSProperties }) {
  useRegistro(visual);
  return (
    <figure className="d-figura" style={estilo}>
      <DibujoFigura id={visual.id} titulo={visual.titulo} />
      {/* El título ya lo dice la diapositiva: en pantalla sobraría y le quitaría
          altura a la figura. Se conserva para lectores de pantalla. */}
      <figcaption className="solo-lectores">{visual.titulo}</figcaption>
    </figure>
  );
}

export function DibujoFigura({ id, titulo }: { id: string; titulo: string }) {
  // El compilador ya comprobó que existe; si faltara, se dice en lugar de dejar
  // un hueco que parezca una diapositiva rota.
  const Componente: ComponentType<PropiedadesFigura> | undefined = FIGURAS[id];
  return Componente ? <Componente titulo={titulo} /> : <p className="d-parrafo">Falta la figura «{id}».</p>;
}

/** Una captura de pantalla dentro de una ventana de navegador: la barra con el
 *  título dice qué pantalla es sin gastar un pie de figura. */
export function Ventana({
  titulo,
  children,
  onAmpliar,
}: {
  titulo: string;
  children: ReactNode;
  onAmpliar?: () => void;
}) {
  return (
    <div className="d-ventana">
      <div className="d-ventana__barra" aria-hidden="true">
        <span className="d-ventana__puntos">
          <i />
          <i />
          <i />
        </span>
        <span className="d-ventana__titulo">{titulo}</span>
      </div>
      {onAmpliar ? (
        <button type="button" className="d-ventana__cuerpo d-ventana__cuerpo--pulsable" onClick={onAmpliar}>
          {children}
          <span className="solo-lectores">Ampliar la captura «{titulo}»</span>
        </button>
      ) : (
        <div className="d-ventana__cuerpo">{children}</div>
      )}
    </div>
  );
}

export function ImagenDeCaptura({ visual, grande = false }: { visual: Visual; grande?: boolean }) {
  const src = CAPTURAS[visual.id];
  if (!src) return <p className="d-parrafo">Falta la captura «{visual.id}».</p>;
  return (
    <img
      className={grande ? "d-captura__imagen d-captura__imagen--grande" : "d-ventana__imagen"}
      src={src}
      alt={visual.titulo}
      decoding="async"
    />
  );
}

function Captura({ visual, estilo }: { visual: Visual; estilo?: CSSProperties }) {
  const { ampliar } = useAnimacion();
  useRegistro(visual);
  return (
    <figure className="d-captura" style={estilo}>
      <Ventana titulo={visual.titulo} onAmpliar={ampliar ? () => ampliar(visual) : undefined}>
        <ImagenDeCaptura visual={visual} />
      </Ventana>
      <figcaption className="solo-lectores">{visual.titulo}</figcaption>
    </figure>
  );
}

/** Un elemento de galería: figura o captura, sin su `figure` propio. */
function ElementoVisual({ visual }: { visual: Visual }) {
  const { ampliar } = useAnimacion();
  if (visual.tipo === "figura") return <DibujoFigura id={visual.id} titulo={visual.titulo} />;
  return (
    <Ventana titulo={visual.titulo} onAmpliar={ampliar ? () => ampliar(visual) : undefined}>
      <ImagenDeCaptura visual={visual} />
    </Ventana>
  );
}

/** Cuánto se queda cada elemento de una galería antes de pasar al siguiente. */
export const GALERIA_INTERVALO_MS = 5000;

/**
 * Varios visuales en el sitio de uno. En el visor pasan solos cada cinco
 * segundos; pulsar un punto salta a ese elemento y reinicia la espera. Fuera
 * del visor se ve el elemento de reposo: el primero si da vueltas, el último
 * si pasa una sola vez, porque ahí termina y es lo que se imprime.
 */
function Galeria({ elementos, bucle, estilo }: { elementos: Visual[]; bucle: boolean; estilo?: CSSProperties }) {
  const { animado, activa, registrar } = useAnimacion();
  const ultimo = elementos.length - 1;
  const reposo = bucle ? 0 : ultimo;
  const [activo, setActivo] = useState(animado ? 0 : reposo);
  // Cambia con cada salto manual para que la espera vuelva a empezar.
  const [ronda, setRonda] = useState(0);

  useEffect(() => {
    if (!animado || !activa) return;
    if (!bucle && activo === ultimo) return;
    const id = window.setTimeout(() => setActivo((a) => (a + 1) % elementos.length), GALERIA_INTERVALO_MS);
    return () => window.clearTimeout(id);
  }, [animado, activa, bucle, activo, ultimo, elementos.length, ronda]);

  useEffect(() => {
    if (!activa || !registrar) return;
    registrar(elementos[activo]!);
    return () => registrar(null);
  }, [activa, activo, elementos, registrar]);

  const saltar = (destino: number) => {
    setActivo(destino);
    setRonda((r) => r + 1);
  };

  return (
    <figure className="d-galeria" style={estilo} data-bucle={bucle || undefined}>
      {elementos.map((visual, i) => (
        <div
          key={i}
          className={`d-galeria__elemento d-galeria__elemento--${visual.tipo}`}
          data-activo={i === activo || undefined}
          aria-hidden={i !== activo}
          // Las figuras SVG no tienen barra con el título: se dice aparte.
          aria-label={visual.tipo === "figura" ? visual.titulo : undefined}
        >
          <ElementoVisual visual={visual} />
        </div>
      ))}
      <ol className="d-galeria__puntos" aria-label={`Galería de ${elementos.length} pantallas`}>
        {elementos.map((visual, i) => (
          <li key={i} data-activo={i === activo || undefined}>
            <button
              type="button"
              onClick={() => saltar(i)}
              aria-label={visual.titulo}
              aria-current={i === activo ? "true" : undefined}
            />
          </li>
        ))}
      </ol>
      <figcaption className="solo-lectores">{elementos[activo]!.titulo}</figcaption>
    </figure>
  );
}
