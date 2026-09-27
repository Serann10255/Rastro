/* Compila un guion de sustentación en un deck.
 *
 * Estructura que espera el archivo (la de `documentacion/sustentacion/*.md`):
 *
 *   # Título del guion
 *   ```yaml  ← metadatos: proyecto, subtítulo, asignatura, equipo, marca…
 *   ---
 *   ## 1 · Portada          ← diapositiva de contenido, numerada
 *   …
 *   > Notas: Sergio. …      ← notas del presentador
 *   ---
 *   # BLOQUE 1 · TÍTULO     ← portadilla de bloque, sin número propio
 *   ---
 *
 * El número que el autor escribe en el título es el de la diapositiva: el que
 * se ve en pantalla, el del enlace directo (`/rastro#7`) y el que citan las
 * notas («desarrollarlo en la 23»). Por eso se exige y se comprueba: un número
 * repetido es un error y un salto en la numeración, un aviso.
 */

import type {
  Deck,
  Diapositiva,
  DiapositivaBloque,
  DiapositivaContenido,
  Metadatos,
  ReferenciaBloque,
} from "../src/deck/tipos.ts";
import { ErrorDeLectura, leerBloques } from "./markdown.ts";

export { ErrorDeLectura };

export interface OpcionesCompilacion {
  /** Ruta del archivo dentro del repositorio, para los mensajes y la pantalla. */
  archivo: string;
  /** Identificadores de las figuras que existen en `src/figuras/`. */
  figuras: ReadonlySet<string>;
}

export interface Compilado {
  deck: Deck;
  avisos: string[];
}

interface Seccion {
  lineas: string[];
  /** Línea del archivo (desde 1) en que empieza la sección. */
  inicio: number;
}

function dividirEnSecciones(texto: string): Seccion[] {
  const secciones: Seccion[] = [];
  let actual: Seccion = { lineas: [], inicio: 1 };
  let enCodigo = false;

  texto.split("\n").forEach((linea, indice) => {
    if (/^```/.test(linea.trim())) enCodigo = !enCodigo;
    if (!enCodigo && linea.trim() === "---") {
      secciones.push(actual);
      actual = { lineas: [], inicio: indice + 2 };
      return;
    }
    actual.lineas.push(linea);
  });
  secciones.push(actual);
  return secciones;
}

function leerMetadatos(yaml: string): Metadatos {
  const meta: Metadatos = {};
  for (const linea of yaml.split("\n")) {
    const m = /^([\w-]+)\s*:\s*(.*)$/.exec(linea.trim());
    if (!m) continue;
    const valor = m[2]!.trim();
    const lista = /^\[(.*)\]$/.exec(valor);
    meta[m[1]!] = lista
      ? lista[1]!.split(",").map((v) => v.trim()).filter(Boolean)
      : valor.replace(/^["']|["']$/g, "");
  }
  return meta;
}

/** Quita las líneas en blanco de los extremos sin perder la posición. */
function recortar(seccion: Seccion): Seccion {
  let inicio = 0;
  let fin = seccion.lineas.length;
  while (inicio < fin && !seccion.lineas[inicio]!.trim()) inicio++;
  while (fin > inicio && !seccion.lineas[fin - 1]!.trim()) fin--;
  return { lineas: seccion.lineas.slice(inicio, fin), inicio: seccion.inicio + inicio };
}

export function compilarSustentacion(fuente: string, opciones: OpcionesCompilacion): Compilado {
  const avisos: string[] = [];
  const error = (linea: number, mensaje: string) =>
    new ErrorDeLectura(`${opciones.archivo}:${linea}: ${mensaje}`);

  const texto = fuente.replace(/\r\n?/g, "\n");
  const [preambulo, ...resto] = dividirEnSecciones(texto);

  // -- Preámbulo: título y metadatos ------------------------------------------
  const cabecera = preambulo!.lineas.join("\n");
  const titulo = /^#\s+(.+)$/m.exec(cabecera)?.[1]?.trim() ?? opciones.archivo;
  const yaml = /```ya?ml\s*\n([\s\S]*?)\n```/.exec(cabecera)?.[1];
  const meta = yaml ? leerMetadatos(yaml) : {};
  if (!yaml) avisos.push(`${opciones.archivo}: no se encontró el bloque yaml de metadatos.`);

  // -- Diapositivas -----------------------------------------------------------
  const diapositivas: Diapositiva[] = [];
  const numerosVistos = new Map<number, number>();
  let bloqueActual: ReferenciaBloque | null = null;
  let presentadorActual: string | null = null;

  for (const bruta of resto) {
    const seccion = recortar(bruta);
    if (seccion.lineas.length === 0) continue;

    const [primera, ...cuerpo] = seccion.lineas;

    // Portadilla de bloque: un único título de primer nivel.
    const h1 = /^#\s+(.+)$/.exec(primera!);
    if (h1) {
      if (cuerpo.some((l) => l.trim())) {
        throw error(
          seccion.inicio,
          "una portadilla de bloque (# …) solo puede llevar su título. Si es una diapositiva " +
            "de contenido, use «## N · Título».",
        );
      }
      const bloque = /^BLOQUE\s+(\d+)\s*·\s*(.+)$/i.exec(h1[1]!.trim());
      const numero = bloque ? Number(bloque[1]) : null;
      const tituloBloque = (bloque ? bloque[2]! : h1[1]!).trim();
      bloqueActual = { numero, titulo: tituloBloque };
      diapositivas.push({
        tipo: "bloque",
        clave: numero !== null ? `bloque-${numero}` : `bloque-${diapositivas.length + 1}`,
        numero,
        titulo: tituloBloque,
        contenido: [],
      });
      continue;
    }

    const h2 = /^##\s+(.+)$/.exec(primera!);
    if (!h2) {
      throw error(seccion.inicio, `se esperaba un título «## N · Título» y se encontró «${primera}».`);
    }
    const encabezado = /^(\d+)\s*·\s*(.+)$/.exec(h2[1]!.trim());
    if (!encabezado) {
      throw error(
        seccion.inicio,
        `la diapositiva «${h2[1]}» no lleva número. El número es el del enlace directo y el ` +
          "que citan las notas: escríbalo como «## N · Título».",
      );
    }
    const numero = Number(encabezado[1]);
    if (numerosVistos.has(numero)) {
      throw error(
        seccion.inicio,
        `el número ${numero} ya se usó en la línea ${numerosVistos.get(numero)}. Dos diapositivas ` +
          "con el mismo número tendrían el mismo enlace directo.",
      );
    }
    numerosVistos.set(numero, seccion.inicio);

    let leido: ReturnType<typeof leerBloques>;
    try {
      leido = leerBloques(cuerpo, seccion.inicio + 1);
    } catch (e) {
      throw error(seccion.inicio, (e as Error).message);
    }
    avisos.push(...leido.avisos.map((a) => `${opciones.archivo}: ${a}`));

    for (const bloque of leido.bloques) {
      if (bloque.tipo === "figura" && !opciones.figuras.has(bloque.id)) {
        const disponibles = [...opciones.figuras].join(", ") || "ninguna";
        throw error(
          seccion.inicio,
          `la figura «${bloque.id}» no existe en presentacion/src/figuras/. Disponibles: ${disponibles}.`,
        );
      }
    }

    if (leido.notas.length === 0) {
      avisos.push(`${opciones.archivo}:${seccion.inicio}: la diapositiva ${numero} no tiene notas.`);
    }
    const declarado = leido.notas.find((n) => n.presentador)?.presentador ?? null;
    if (declarado) presentadorActual = declarado;

    const tituloDiapositiva = encabezado[2]!.trim();
    diapositivas.push({
      tipo: "contenido",
      clave: String(numero),
      numero,
      titulo: tituloDiapositiva,
      portada: tituloDiapositiva.toLowerCase() === "portada",
      bloques: leido.bloques,
      notas: leido.notas,
      presentador: presentadorActual,
      bloque: bloqueActual,
    });
  }

  // -- Comprobaciones de conjunto ---------------------------------------------
  const contenido = diapositivas.filter((d): d is DiapositivaContenido => d.tipo === "contenido");
  if (contenido.length === 0) {
    throw new ErrorDeLectura(`${opciones.archivo}: el guion no tiene ninguna diapositiva.`);
  }
  contenido.forEach((d, k) => {
    const esperado = k === 0 ? 1 : contenido[k - 1]!.numero + 1;
    if (d.numero !== esperado) {
      avisos.push(
        `${opciones.archivo}: la diapositiva «${d.titulo}» lleva el número ${d.numero} y le ` +
          `correspondía el ${esperado}. Revise también las notas que citan números.`,
      );
    }
  });

  // Sumario de cada portadilla: lo que agrupa hasta la siguiente.
  let portadilla: DiapositivaBloque | null = null;
  for (const d of diapositivas) {
    if (d.tipo === "bloque") portadilla = d;
    else portadilla?.contenido.push({ numero: d.numero, titulo: d.titulo });
  }

  const intervenciones = new Map<string, number[]>();
  for (const d of contenido) {
    if (!d.presentador) continue;
    intervenciones.set(d.presentador, [...(intervenciones.get(d.presentador) ?? []), d.numero]);
  }

  return {
    deck: {
      archivo: opciones.archivo,
      titulo,
      meta,
      diapositivas,
      resumen: {
        total: diapositivas.length,
        contenido: contenido.length,
        bloques: diapositivas.length - contenido.length,
        intervenciones: [...intervenciones].map(([presentador, numeros]) => ({ presentador, numeros })),
      },
    },
    avisos,
  };
}
