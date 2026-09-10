/* Logotipo de Rastro.
 *
 * La marca es lo que hace el sistema: un rastro. Tres nodos unidos por un
 * trayecto que sube de izquierda a derecha —origen, tránsito y entrega— dentro
 * de un contenedor con las esquinas de una caja. El primer nodo va hueco
 * (registrado), el segundo a medias (en camino) y el tercero macizo, con la
 * marca de entrega: el envío existe, avanza y se cierra.
 *
 * Es geométrico a propósito. Un icono de camión diría «transporte» y este
 * sistema no transporta nada: registra lo que ocurre con lo transportado, y esa
 * diferencia es justamente lo que lo distingue de un TMS cualquiera.
 *
 * Sin colores literales: usa el degradado de marca de la aplicación que lo
 * monta, de modo que el mismo componente sirve en Rastro y en cualquier
 * documento que lo incruste, en tema claro y oscuro.
 */

interface PropiedadesMarca {
  /** Alto en píxeles. El ancho sale de la proporción del trazado. */
  tamano?: number;
  /** Identificador del degradado. Dos logotipos en la misma página no pueden
   *  compartirlo: el segundo reutilizaría el del primero. */
  id?: string;
  className?: string;
}

export function LogotipoRastro({ tamano = 32, id = "marca-rastro", className }: PropiedadesMarca) {
  const degradado = `${id}-degradado`;

  return (
    <svg
      viewBox="0 0 48 48"
      width={tamano}
      height={tamano}
      className={className}
      role="img"
      aria-label="Rastro"
      focusable="false"
    >
      <defs>
        <linearGradient id={degradado} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--marca-1)" />
          <stop offset="100%" stopColor="var(--marca-2)" />
        </linearGradient>
      </defs>

      {/* La caja: esquinas marcadas, lados abiertos. Contiene el recorrido sin
          encerrarlo, porque el envío entra y sale. */}
      <path
        d="M14 5H9a4 4 0 0 0-4 4v5M34 5h5a4 4 0 0 1 4 4v5M14 43H9a4 4 0 0 1-4-4v-5M34 43h5a4 4 0 0 0 4-4v-5"
        fill="none"
        stroke={`url(#${degradado})`}
        strokeWidth="3"
        strokeLinecap="round"
      />

      {/* El trayecto. Sube porque el envío avanza; los tramos son distintos
          porque el avance no es uniforme. */}
      <path
        d="M13 33 L24 24 L35 15"
        fill="none"
        stroke={`url(#${degradado})`}
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.35"
      />

      {/* Origen: registrado y todavía vacío. */}
      <circle cx="13" cy="33" r="3.4" fill="none" stroke={`url(#${degradado})`} strokeWidth="2.6" />

      {/* Tránsito: a medio camino, medio lleno. */}
      <circle cx="24" cy="24" r="3.4" fill={`url(#${degradado})`} opacity="0.55" />

      {/* Entrega: macizo, con la marca de que se cerró. */}
      <circle cx="35" cy="15" r="5.6" fill={`url(#${degradado})`} />
      <path
        d="M32.6 15.1 L34.4 16.9 L37.6 13.3"
        fill="none"
        stroke="var(--marca-contraste, #fff)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
