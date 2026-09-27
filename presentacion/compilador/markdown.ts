/* Lector del subconjunto de Markdown que usan los guiones de sustentación.
 *
 * No es un intérprete general de Markdown ni pretende serlo: entiende lo que
 * los dos guiones escriben —párrafos, listas, tablas, citas, bloques de código,
 * negrita, cursiva, código en línea y figuras— y falla en voz alta ante lo que
 * no entiende, en lugar de dibujarlo mal en silencio. Una biblioteca general
 * resolvería más casos de los que existen y ocultaría los que importan: dónde
 * acaban las notas del presentador y dónde empieza el contenido.
 *
 * Dos decisiones de lectura que no son las de Markdown estándar:
 *
 * 1. **Los saltos de línea de un párrafo se conservan.** El autor escribe «una
 *    frase por línea» a propósito; unirlas en un solo renglón cambiaría la
 *    diapositiva.
 * 2. **En las citas (`>`) los saltos se unen**, porque ahí sí son el ajuste de
 *    línea del editor. Una cita que empieza por «Notas:» es una nota del
 *    presentador; cualquier otra es contenido y se dibuja como cita destacada.
 */

import type { Alineacion, Bloque, Cifra, Inline, Linea, Nota } from "../src/deck/tipos.ts";

export class ErrorDeLectura extends Error {}

/* ------------------------------------------------------------------------ */
/* Formato en línea                                                         */
/* ------------------------------------------------------------------------ */

/** Busca el cierre de un delimitador sin entrar en el código en línea. */
function buscarCierre(texto: string, delimitador: string, desde: number): number {
  let enCodigo = false;
  for (let i = desde; i < texto.length; i++) {
    const c = texto[i];
    if (c === "\\") {
      i++;
      continue;
    }
    if (c === "`") enCodigo = !enCodigo;
    if (enCodigo || !texto.startsWith(delimitador, i)) continue;
    // Un «*» suelto no cierra una negrita, y el «*» de una negrita no cierra
    // una cursiva.
    if (delimitador === "*" && texto[i + 1] === "*") {
      i++;
      continue;
    }
    // La cursiva no cierra tras un espacio: «a * b * c» no es cursiva.
    if (delimitador === "*" && /\s/.test(texto[i - 1] ?? " ")) continue;
    return i;
  }
  return -1;
}

export function enLinea(texto: string): Inline[] {
  const nodos: Inline[] = [];
  let acumulado = "";
  const volcar = () => {
    if (acumulado) nodos.push({ t: "texto", v: acumulado });
    acumulado = "";
  };

  let i = 0;
  while (i < texto.length) {
    const c = texto[i]!;

    if (c === "\\" && i + 1 < texto.length && /[\\`*_[\]|]/.test(texto[i + 1]!)) {
      acumulado += texto[i + 1];
      i += 2;
      continue;
    }

    if (c === "`") {
      const fin = texto.indexOf("`", i + 1);
      if (fin > i) {
        volcar();
        nodos.push({ t: "codigo", v: texto.slice(i + 1, fin) });
        i = fin + 1;
        continue;
      }
    }

    if (texto.startsWith("**", i)) {
      const fin = buscarCierre(texto, "**", i + 2);
      if (fin > i + 2) {
        volcar();
        nodos.push({ t: "fuerte", hijos: enLinea(texto.slice(i + 2, fin)) });
        i = fin + 2;
        continue;
      }
    }

    if (c === "*" && !/\s/.test(texto[i + 1] ?? " ")) {
      const fin = buscarCierre(texto, "*", i + 1);
      if (fin > i + 1) {
        volcar();
        nodos.push({ t: "enfasis", hijos: enLinea(texto.slice(i + 1, fin)) });
        i = fin + 1;
        continue;
      }
    }

    if (c === "[") {
      const enlace = /^\[([^\]]+)\]\(([^)\s]+)\)/.exec(texto.slice(i));
      if (enlace) {
        volcar();
        nodos.push({ t: "enlace", href: enlace[2]!, hijos: enLinea(enlace[1]!) });
        i += enlace[0].length;
        continue;
      }
    }

    acumulado += c;
    i++;
  }

  volcar();
  return nodos;
}

/* ------------------------------------------------------------------------ */
/* Bloques                                                                  */
/* ------------------------------------------------------------------------ */

const VALLA = /^```\s*([\w-]*)\s*$/;
const FILA_TABLA = /^\s*\|/;
const SEPARADOR_TABLA = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
const CITA = /^\s*>/;
const ELEMENTO_ORDENADO = /^\s*(\d+)\.\s+(.*)$/;
const ELEMENTO = /^\s*[-*+]\s+(.*)$/;
const SUBTITULO = /^#{3,6}\s+(.+)$/;
const IMAGEN = /^!\[([^\]]*)\]\(([^)\s]+)\)\s*$/;
const PREFIJO_NOTA = /^\*{0,2}Notas\*{0,2}\s*:\s*\*{0,2}\s*/i;
/** «Sergio.», «Nicolás.», «Oscar Rincón.»: un nombre propio de hasta tres palabras. */
const PRESENTADOR = /^(\p{Lu}\p{Ll}+(?:\s\p{Lu}\p{Ll}+){0,2})\.\s*/u;

function iniciaBloque(linea: string): boolean {
  return (
    VALLA.test(linea) ||
    FILA_TABLA.test(linea) ||
    CITA.test(linea) ||
    ELEMENTO_ORDENADO.test(linea) ||
    ELEMENTO.test(linea) ||
    SUBTITULO.test(linea) ||
    IMAGEN.test(linea)
  );
}

function celdas(fila: string): string[] {
  let s = fila.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);

  const resultado: string[] = [];
  let actual = "";
  let enCodigo = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "\\" && s[i + 1] === "|") {
      actual += "\\|";
      i++;
      continue;
    }
    if (c === "`") enCodigo = !enCodigo;
    if (c === "|" && !enCodigo) {
      resultado.push(actual.trim());
      actual = "";
      continue;
    }
    actual += c;
  }
  resultado.push(actual.trim());
  return resultado;
}

function alineaciones(separador: string): Alineacion[] {
  return celdas(separador).map((celda) => {
    const izquierda = celda.startsWith(":");
    const derecha = celda.endsWith(":");
    if (izquierda && derecha) return "centro";
    if (derecha) return "derecha";
    if (izquierda) return "izquierda";
    return null;
  });
}

/** Cifras de resultado: «234 superadas · 4 omitidas · 0 fallos». */
export function comoCifras(texto: string): Cifra[] | null {
  const limpio = texto.trim();
  if (!limpio || limpio.includes("\n")) return null;
  const cifras: Cifra[] = [];
  for (const parte of limpio.split(/\s*·\s*/)) {
    const m = /^(\d[\d.,]*)\s+(.+)$/.exec(parte.trim());
    if (!m) return null;
    cifras.push({ valor: m[1]!, etiqueta: m[2]! });
  }
  return cifras.length > 0 ? cifras : null;
}

export interface ResultadoBloques {
  bloques: Bloque[];
  notas: Nota[];
  avisos: string[];
}

/**
 * Lee el cuerpo de una diapositiva. `primeraLinea` es el número de línea del
 * archivo en que empieza, para que los errores señalen dónde mirar.
 */
export function leerBloques(lineas: string[], primeraLinea: number): ResultadoBloques {
  const bloques: Bloque[] = [];
  const notas: Nota[] = [];
  const avisos: string[] = [];

  let i = 0;
  while (i < lineas.length) {
    const linea = lineas[i]!;
    const numeroLinea = primeraLinea + i;

    if (!linea.trim()) {
      i++;
      continue;
    }

    // -- Código ---------------------------------------------------------------
    const valla = VALLA.exec(linea);
    if (valla) {
      const contenido: string[] = [];
      i++;
      while (i < lineas.length && !/^```\s*$/.test(lineas[i]!)) contenido.push(lineas[i++]!);
      if (i >= lineas.length) {
        throw new ErrorDeLectura(`Línea ${numeroLinea}: el bloque de código no se cierra.`);
      }
      i++;
      const texto = contenido.join("\n");
      const cifras = comoCifras(texto);
      bloques.push(
        cifras ? { tipo: "resultado", cifras } : { tipo: "codigo", lenguaje: valla[1] ?? "", texto },
      );
      continue;
    }

    // -- Tabla ----------------------------------------------------------------
    if (FILA_TABLA.test(linea)) {
      const filasTexto: string[] = [];
      while (i < lineas.length && FILA_TABLA.test(lineas[i]!)) filasTexto.push(lineas[i++]!);

      let encabezado: string[] | null = null;
      let alineacion: Alineacion[] = [];
      let cuerpo = filasTexto;
      if (filasTexto.length > 1 && SEPARADOR_TABLA.test(filasTexto[1]!)) {
        encabezado = celdas(filasTexto[0]!);
        alineacion = alineaciones(filasTexto[1]!);
        cuerpo = filasTexto.slice(2);
      }
      const filas = cuerpo.map(celdas);
      const columnas = Math.max(encabezado?.length ?? 0, ...filas.map((f) => f.length));
      if (filas.some((f) => f.length !== columnas) || (encabezado && encabezado.length !== columnas)) {
        avisos.push(`Línea ${numeroLinea}: la tabla tiene filas con distinto número de columnas.`);
      }
      const completar = (f: string[]) => [...f, ...Array(columnas - f.length).fill("")];
      const encabezadoVacio = encabezado?.every((c) => !c) ?? true;

      bloques.push({
        tipo: "tabla",
        encabezado: encabezadoVacio ? null : completar(encabezado!).map(enLinea),
        filas: filas.map((f) => completar(f).map(enLinea)),
        alineacion: Array.from({ length: columnas }, (_, k) => alineacion[k] ?? null),
      });
      continue;
    }

    // -- Cita o nota del presentador -----------------------------------------
    if (CITA.test(linea)) {
      const partes: string[] = [];
      while (i < lineas.length && CITA.test(lineas[i]!)) {
        const contenido = lineas[i++]!.replace(/^\s*>\s?/, "").trim();
        if (contenido) partes.push(contenido);
      }
      const texto = partes.join(" ");
      if (PREFIJO_NOTA.test(texto)) {
        let resto = texto.replace(PREFIJO_NOTA, "");
        const nombre = PRESENTADOR.exec(resto);
        if (nombre) resto = resto.slice(nombre[0].length);
        notas.push({ presentador: nombre?.[1] ?? null, texto: enLinea(resto) });
      } else {
        bloques.push({ tipo: "cita", linea: enLinea(texto) });
      }
      continue;
    }

    // -- Listas ---------------------------------------------------------------
    const ordenado = ELEMENTO_ORDENADO.exec(linea);
    if (ordenado || ELEMENTO.test(linea)) {
      const patron = ordenado ? ELEMENTO_ORDENADO : ELEMENTO;
      const elementos: string[] = [];
      while (i < lineas.length) {
        const actual = lineas[i]!;
        const m = patron.exec(actual);
        if (m) {
          elementos.push((ordenado ? m[2] : m[1])!.trim());
        } else if (/^\s{2,}\S/.test(actual) && elementos.length > 0) {
          // Continuación sangrada del elemento anterior.
          elementos[elementos.length - 1] += ` ${actual.trim()}`;
        } else {
          break;
        }
        i++;
      }
      bloques.push({
        tipo: "lista",
        ordenada: Boolean(ordenado),
        inicio: ordenado ? Number(ordenado[1]) : 1,
        elementos: elementos.map(enLinea),
      });
      continue;
    }

    // -- Subtítulo ------------------------------------------------------------
    const subtitulo = SUBTITULO.exec(linea);
    if (subtitulo) {
      bloques.push({ tipo: "subtitulo", linea: enLinea(subtitulo[1]!.trim()) });
      i++;
      continue;
    }

    // -- Figura ---------------------------------------------------------------
    const imagen = IMAGEN.exec(linea);
    if (imagen) {
      const [, titulo, destino] = imagen;
      if (!destino!.startsWith("figura:")) {
        throw new ErrorDeLectura(
          `Línea ${numeroLinea}: solo se admiten figuras del propio módulo, con la forma ` +
            `![Título](figura:identificador). Se encontró «${destino}».`,
        );
      }
      bloques.push({ tipo: "figura", id: destino!.slice("figura:".length), titulo: titulo!.trim() });
      i++;
      continue;
    }

    // -- Párrafo --------------------------------------------------------------
    const parrafo: string[] = [];
    while (i < lineas.length && lineas[i]!.trim() && (parrafo.length === 0 || !iniciaBloque(lineas[i]!))) {
      parrafo.push(lineas[i++]!.trim());
    }
    bloques.push({ tipo: "parrafo", lineas: parrafo.map(enLinea) });
  }

  return { bloques, notas, avisos };
}

/** Texto plano de una línea con formato: para títulos accesibles y búsquedas. */
export function textoPlano(linea: Linea): string {
  return linea
    .map((n) => (n.t === "texto" || n.t === "codigo" ? n.v : textoPlano(n.hijos)))
    .join("");
}
