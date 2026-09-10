/* Logotipo de Cotejo.
 *
 * Cotejar es poner dos cosas una al lado de la otra y ver si dicen lo mismo. La
 * marca es exactamente eso: dos hojas superpuestas —lo declarado y lo
 * observado— y, encima, la marca de verificación que solo aparece cuando ambas
 * coinciden. Los tres eslabones del borde inferior son la cadena de huellas:
 * cada papel de trabajo enlaza con el anterior.
 *
 * No lleva lupa. Una lupa dice «buscar» y auditar no es buscar: es comparar
 * contra un criterio declarado de antemano, que es lo que distingue una
 * auditoría de una revisión improvisada.
 *
 * Comparte construcción con el logotipo de Rastro —mismo lienzo, mismo grosor
 * de trazo, mismo degradado de marca— porque son dos productos de la misma
 * familia, y cambia el color porque uno audita al otro.
 */

interface PropiedadesMarca {
  tamano?: number;
  id?: string;
  className?: string;
}

export function LogotipoCotejo({ tamano = 32, id = "marca-cotejo", className }: PropiedadesMarca) {
  const degradado = `${id}-degradado`;

  return (
    <svg
      viewBox="0 0 48 48"
      width={tamano}
      height={tamano}
      className={className}
      role="img"
      aria-label="Cotejo"
      focusable="false"
    >
      <defs>
        <linearGradient id={degradado} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--marca-1)" />
          <stop offset="100%" stopColor="var(--marca-2)" />
        </linearGradient>
      </defs>

      {/* La hoja de atrás: lo declarado, el criterio escrito antes de mirar. */}
      <rect
        x="8"
        y="6"
        width="22"
        height="28"
        rx="3"
        fill="none"
        stroke={`url(#${degradado})`}
        strokeWidth="2.4"
        opacity="0.4"
      />

      {/* La hoja de delante: lo observado en el sistema auditado. */}
      <rect
        x="16"
        y="12"
        width="22"
        height="28"
        rx="3"
        fill="var(--superficie, #fff)"
        stroke={`url(#${degradado})`}
        strokeWidth="2.4"
      />

      {/* Las líneas del registro que se compara. */}
      <path
        d="M21 20h12M21 25h12M21 30h7"
        stroke={`url(#${degradado})`}
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.45"
      />

      {/* La conclusión: solo se dibuja encima de las dos hojas, porque sin las
          dos no hay cotejo que valga. */}
      <path
        d="M20.5 26.5 L25.5 31.5 L35 20.5"
        fill="none"
        stroke={`url(#${degradado})`}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* La cadena de huellas: cada papel enlaza con el anterior. */}
      <circle cx="9" cy="41" r="2.6" fill="none" stroke={`url(#${degradado})`} strokeWidth="2" />
      <circle cx="17" cy="41" r="2.6" fill="none" stroke={`url(#${degradado})`} strokeWidth="2" />
      <path d="M11.6 41h2.8" stroke={`url(#${degradado})`} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
