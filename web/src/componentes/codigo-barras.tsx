/* Código de barras Code 128 dibujado como SVG.
 *
 * Se implementa aquí en lugar de traer una biblioteca por dos razones. La
 * primera es que el sitio se publica como estático y el proyecto se audita a sí
 * mismo: conviene que lo que se sirve sea código propio y revisable. La segunda
 * es que el algoritmo cabe en cien líneas y una dependencia para esto arrastra
 * su propia cadena de suministro por nada.
 *
 * Se usa el juego B, que cubre letras, dígitos y guiones —todo lo que aparece
 * en un identificador de rastreo—. El juego C comprimiría los dígitos a la
 * mitad, pero un UUID no es solo dígitos y alternar juegos a mitad del código
 * añade complejidad sin ganancia para esta longitud.
 */

/** Anchos de barra y espacio de cada símbolo, en módulos. */
const PATRONES = [
  "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
  "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
  "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
  "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
  "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
  "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
  "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
  "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
  "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
  "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
  "111242", "121142", "121241", "141142", "141241", "114212", "124112", "124211",
  "411212", "421112", "421211", "212141", "214121", "412121", "111143", "111341",
  "131141", "114113", "114311", "411113", "411311", "113141", "114131", "311141",
  "411131", "211412", "211214", "211232",
];

const INICIO_B = 104;
const PARADA = "2331112";

/** Convierte el texto a la secuencia de símbolos, con su dígito de control.
 *
 * El dígito de control es lo que hace que un lector rechace una lectura
 * parcial en vez de devolver un identificador equivocado, que en una operación
 * de mensajería significaría entregar el paquete al destinatario de otro.
 */
function codificar(texto: string): string[] {
  const valores: number[] = [];

  for (const caracter of texto) {
    const codigo = caracter.charCodeAt(0);
    // El juego B cubre de espacio (32) a DEL (126). Lo que no entra se
    // sustituye por un espacio en lugar de romper el código: una guía con un
    // carácter cambiado sigue siendo escaneable, una sin código no.
    valores.push(codigo >= 32 && codigo <= 126 ? codigo - 32 : 0);
  }

  const suma = valores.reduce((total, valor, indice) => total + valor * (indice + 1), INICIO_B);
  const control = suma % 103;

  return [
    PATRONES[INICIO_B]!,
    ...valores.map((valor) => PATRONES[valor]!),
    PATRONES[control]!,
    PARADA,
  ];
}

export function CodigoBarras({
  valor,
  alto = 44,
  anchoModulo = 1.4,
  className,
}: {
  valor: string;
  alto?: number;
  /** Ancho de un módulo en píxeles. Por debajo de 1 los lectores fallan. */
  anchoModulo?: number;
  className?: string;
}) {
  const simbolos = codificar(valor);

  const barras: { x: number; ancho: number }[] = [];
  let x = 0;
  for (const simbolo of simbolos) {
    // Los dígitos del patrón alternan barra y espacio, empezando por barra.
    for (const [indice, digito] of [...simbolo].entries()) {
      const ancho = Number(digito) * anchoModulo;
      if (indice % 2 === 0) barras.push({ x, ancho });
      x += ancho;
    }
  }

  return (
    <svg
      className={className}
      width="100%"
      viewBox={`0 0 ${x} ${alto}`}
      preserveAspectRatio="none"
      // El contenido lo lee un escáner, no una persona: para el lector de
      // pantalla la información útil es el identificador, que va debajo en
      // texto.
      role="img"
      aria-label={`Código de barras: ${valor}`}
      style={{ display: "block", height: alto }}
    >
      <rect width={x} height={alto} fill="#fff" />
      {barras.map((barra, indice) => (
        <rect key={indice} x={barra.x} y={0} width={barra.ancho} height={alto} fill="#000" />
      ))}
    </svg>
  );
}
