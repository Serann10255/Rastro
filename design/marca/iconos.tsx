/* Iconografía del sistema.
 *
 * Trazos sobre una retícula de 24, grosor 1.8 y extremos redondeados: los
 * mismos parámetros que los logotipos, de modo que un icono junto a la marca no
 * parece de otro juego.
 *
 * Sustituyen a los emoji que había antes. Un emoji se dibuja distinto en cada
 * sistema operativo —el mismo 📦 es marrón en Windows y beige en Android—, no
 * hereda el color del texto y en tema oscuro se queda con su propio fondo. Estos
 * heredan `currentColor` y por eso funcionan en los dos temas sin variantes.
 *
 * El nombre del icono llega desde la base de datos, en el campo `icono` de cada
 * módulo. Si un módulo pide uno que no existe, se dibuja el genérico en lugar de
 * un hueco: una pantalla con un agujero parece rota, y el problema real es solo
 * que falta un dibujo.
 */

interface PropiedadesIcono {
  nombre: string;
  tamano?: number;
  className?: string;
}

const TRAZADOS: Record<string, string> = {
  // Operación
  paquete: "M21 8v8l-9 5-9-5V8l9-5 9 5ZM3 8l9 5 9-5M12 13v8",
  mas: "M12 5v14M5 12h14",
  etiqueta: "M3 7v5.6a2 2 0 0 0 .6 1.4l7 7a2 2 0 0 0 2.8 0l6.6-6.6a2 2 0 0 0 0-2.8l-7-7a2 2 0 0 0-1.4-.6H5a2 2 0 0 0-2 2Z M7.5 7.5h.01",
  rastro: "M4 18h2m4 0h2m4 0h4M6 6l4 4 4-4 4 4",
  camion: "M3 7h10v9H3zM13 10h4l3 3v3h-7zM7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM17 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
  tienda: "M4 10v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9M3 10l1.4-5.2A1 1 0 0 1 5.4 4h13.2a1 1 0 0 1 1 .8L21 10a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0ZM10 20v-5h4v5",
  recoleccion: "M12 3v10m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  mapa: "M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Zm0 0v13m6-10.5v13",

  // Personas
  usuarios: "M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20M9.5 10.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM21 20v-1.5a4 4 0 0 0-3-3.87M16.5 3.9a4 4 0 0 1 0 7.2",
  clientes: "M4 20v-1a4 4 0 0 1 4-4h3a4 4 0 0 1 4 4v1M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM17 8h5M19.5 5.5v5",

  // Documentos y control
  documento: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6M9 17h4",
  bitacora: "M5 4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4Zm0 4h13M9 12h5M9 16h3",
  factura: "M6 2h12v20l-3-2-3 2-3-2-3 2V2ZM9.5 7h5M9.5 11h5M9.5 15h3",
  estados: "M4 6h4v4H4zM4 14h4v4H4zM12 8h8M12 16h8",
  panel: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  auditoria: "M4 5h10v14H4zM8 9h6M8 13h4M16 8l4 4-4 4",

  // Estados de la comprobación
  verificado: "M4.5 12.5 9 17l10.5-11",
  alerta: "M12 3 2.5 20h19L12 3Zm0 6v5m0 3h.01",
  cadena: "M9 14a4 4 0 0 1 0-5.7l2-2a4 4 0 0 1 5.7 5.7l-1 1M15 10a4 4 0 0 1 0 5.7l-2 2A4 4 0 0 1 7.3 12l1-1",
  reloj: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3.5 2",

  // Genérico: se dibuja cuando el nombre pedido no existe.
  generico: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 8h.01M11 12h1v5h1",
};

export function Icono({ nombre, tamano = 18, className }: PropiedadesIcono) {
  const trazado = TRAZADOS[nombre] ?? TRAZADOS.generico!;

  return (
    <svg
      viewBox="0 0 24 24"
      width={tamano}
      height={tamano}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={trazado} />
    </svg>
  );
}

/** Los nombres que el sistema sabe dibujar. Lo usa la documentación y las
 *  pruebas: un módulo con un icono que no existe se ve, pero no debería. */
export const ICONOS_DISPONIBLES = Object.keys(TRAZADOS);
