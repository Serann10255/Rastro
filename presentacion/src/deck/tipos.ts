/* Forma de un deck ya compilado.
 *
 * El compilador (`compilador/sustentacion.ts`) lee el Markdown al construir y
 * produce esta estructura; la interfaz solo la dibuja. Ningún texto de las
 * diapositivas vive en el código: si vive aquí es una etiqueta de la interfaz,
 * no contenido de la sustentación.
 *
 * Solo tipos: lo importan tanto el compilador, que corre en Node, como la
 * interfaz, que corre en el navegador.
 */

export type Inline =
  | { t: "texto"; v: string }
  | { t: "fuerte"; hijos: Inline[] }
  | { t: "enfasis"; hijos: Inline[] }
  | { t: "codigo"; v: string }
  | { t: "enlace"; href: string; hijos: Inline[] };

/** Una línea de texto con formato. Los párrafos de las diapositivas conservan
 *  sus saltos de línea: el autor escribe una frase por línea a propósito. */
export type Linea = Inline[];

export type Alineacion = "izquierda" | "centro" | "derecha" | null;

export interface Cifra {
  valor: string;
  etiqueta: string;
}

export type Bloque =
  | { tipo: "parrafo"; lineas: Linea[] }
  | { tipo: "subtitulo"; linea: Linea }
  | { tipo: "lista"; ordenada: boolean; inicio: number; elementos: Linea[] }
  | {
      tipo: "tabla";
      /** `null` cuando la tabla no declara encabezado o lo deja vacío. */
      encabezado: Linea[] | null;
      filas: Linea[][];
      alineacion: Alineacion[];
    }
  | { tipo: "cita"; linea: Linea }
  /** Un bloque de código cuyo contenido son cifras separadas por «·». */
  | { tipo: "resultado"; cifras: Cifra[] }
  | { tipo: "codigo"; lenguaje: string; texto: string }
  | { tipo: "figura"; id: string; titulo: string };

export interface Nota {
  /** Quien presenta, si la nota empieza por un nombre: «Notas: Sergio. …». */
  presentador: string | null;
  texto: Linea;
}

export interface ReferenciaBloque {
  numero: number | null;
  titulo: string;
}

export interface DiapositivaContenido {
  tipo: "contenido";
  /** Lo que va tras la almohadilla del enlace directo: `/rastro#7`. */
  clave: string;
  numero: number;
  titulo: string;
  portada: boolean;
  bloques: Bloque[];
  notas: Nota[];
  /** Quien presenta: el último nombre declarado en las notas hasta aquí. */
  presentador: string | null;
  bloque: ReferenciaBloque | null;
}

export interface DiapositivaBloque {
  tipo: "bloque";
  clave: string;
  numero: number | null;
  titulo: string;
  /** Las diapositivas que agrupa, para el sumario de la portadilla. */
  contenido: { numero: number; titulo: string }[];
}

export type Diapositiva = DiapositivaContenido | DiapositivaBloque;

export type Metadatos = Record<string, string | string[]>;

export interface Deck {
  /** Ruta del Markdown dentro del repositorio, para citarla en pantalla. */
  archivo: string;
  titulo: string;
  meta: Metadatos;
  diapositivas: Diapositiva[];
  resumen: {
    total: number;
    contenido: number;
    bloques: number;
    /** Diapositivas de contenido que presenta cada integrante. */
    intervenciones: { presentador: string; numeros: number[] }[];
  };
}
