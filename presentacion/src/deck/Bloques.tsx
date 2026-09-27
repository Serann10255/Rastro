/* Dibujo de los bloques de una diapositiva.
 *
 * Las tablas se leen a distancia: letra de cuerpo, celdas holgadas y sin la
 * retícula de una tabla de documento. Algunos valores llevan tono propio, y
 * siempre por su texto, nunca solo por el color: la marca «✓», el «—» de lo
 * vedado, los niveles de probabilidad, impacto o prioridad, y las tres
 * conclusiones de Cotejo con los mismos colores que usa su interfaz.
 */

import type { ComponentType } from "react";

import { FIGURAS, type PropiedadesFigura } from "@/figuras";

import { EnLinea, Lineas, textoPlano } from "./formato";
import type { Alineacion, Bloque, Cifra, Linea } from "./tipos";

export function Bloques({ bloques }: { bloques: Bloque[] }) {
  return (
    <>
      {bloques.map((bloque, i) => (
        <BloqueUnico key={i} bloque={bloque} />
      ))}
    </>
  );
}

function BloqueUnico({ bloque }: { bloque: Bloque }) {
  switch (bloque.tipo) {
    case "parrafo": {
      // Un párrafo que es solo un dato en código (una cuenta, un repositorio) se
      // presenta como dato, no como frase.
      const soloCodigo = bloque.lineas.every((l) => l.length === 1 && l[0]!.t === "codigo");
      return (
        <p className={soloCodigo ? "d-parrafo d-parrafo--dato" : "d-parrafo"}>
          <Lineas lineas={bloque.lineas} />
        </p>
      );
    }
    case "subtitulo":
      return (
        <h3 className="d-subtitulo">
          <EnLinea nodos={bloque.linea} />
        </h3>
      );
    case "lista": {
      const elementos = bloque.elementos.map((linea, i) => (
        <li key={i}>
          <EnLinea nodos={linea} />
        </li>
      ));
      return bloque.ordenada ? (
        <ol className="d-lista d-lista--ordenada" start={bloque.inicio}>
          {elementos}
        </ol>
      ) : (
        <ul className="d-lista">{elementos}</ul>
      );
    }
    case "tabla":
      return <Tabla encabezado={bloque.encabezado} filas={bloque.filas} alineacion={bloque.alineacion} />;
    case "cita":
      return (
        <blockquote className="d-cita">
          <EnLinea nodos={bloque.linea} />
        </blockquote>
      );
    case "resultado":
      return <Resultado cifras={bloque.cifras} />;
    case "codigo":
      return (
        <pre className="d-bloque-codigo">
          <code>{bloque.texto}</code>
        </pre>
      );
    case "figura":
      return <Figura id={bloque.id} titulo={bloque.titulo} />;
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
}: {
  encabezado: Linea[] | null;
  filas: Linea[][];
  alineacion: Alineacion[];
}) {
  const columnasDeNivel = (encabezado ?? []).map((c) => COLUMNAS_DE_NIVEL.test(textoPlano(c).trim()));
  // Sin encabezado, la primera columna nombra la fila: «Condición», «Criterio»…
  const encabezaFilas = encabezado === null;

  return (
    <div className="d-tabla-contenedor">
      <table className={encabezaFilas ? "d-tabla d-tabla--por-filas" : "d-tabla"}>
        {encabezado && (
          <thead>
            <tr>
              {encabezado.map((celda, c) => (
                <th key={c} scope="col" className={claseAlineacion(alineacion[c] ?? null)}>
                  <EnLinea nodos={celda} />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {filas.map((fila, f) => {
            const veredicto = encabezaFilas ? VEREDICTOS[textoPlano(fila[0] ?? []).trim()] : undefined;
            return (
              <tr key={f} className={veredicto ? `d-veredicto d-veredicto--${veredicto}` : undefined}>
                {fila.map((celda, c) => {
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

function Resultado({ cifras }: { cifras: Cifra[] }) {
  return (
    <dl className="d-resultado">
      {cifras.map((cifra, i) => (
        <div key={i} className={`d-cifra d-cifra--${tono(cifra)}`}>
          <dt className="d-cifra__etiqueta">{cifra.etiqueta}</dt>
          <dd className="d-cifra__valor">{cifra.valor}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------------ */
/* Figuras                                                                  */
/* ------------------------------------------------------------------------ */

function Figura({ id, titulo }: { id: string; titulo: string }) {
  // El compilador ya comprobó que existe; si faltara, se dice en lugar de dejar
  // un hueco que parezca una diapositiva rota.
  const Componente: ComponentType<PropiedadesFigura> | undefined = FIGURAS[id];
  return (
    <figure className="d-figura">
      {Componente ? <Componente titulo={titulo} /> : <p className="d-parrafo">Falta la figura «{id}».</p>}
      {/* El título ya lo dice la diapositiva: en pantalla sobraría y le quitaría
          altura a la figura. Se conserva para lectores de pantalla. */}
      <figcaption className="solo-lectores">{titulo}</figcaption>
    </figure>
  );
}
