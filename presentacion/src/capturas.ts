/* Registro de capturas de pantalla.
 *
 * Una captura existe si existe su imagen en `presentacion/capturas/`:
 * `rastro-panel.webp` se cita en el guion como `![Título](captura:rastro-panel)`.
 * El compilador comprueba la misma carpeta al construir, de modo que no hay una
 * lista aparte que pueda quedarse atrás. Las imágenes se generan con
 * `capturas/capturar.mjs` a partir de la pila local.
 */

const modulos = import.meta.glob<string>("../capturas/*.{webp,png,jpg,jpeg}", {
  eager: true,
  query: "?url",
  import: "default",
});

export const CAPTURAS: Record<string, string> = Object.fromEntries(
  Object.entries(modulos).map(([ruta, url]) => [
    ruta.replace(/^.*\//, "").replace(/\.(webp|png|jpe?g)$/, ""),
    url,
  ]),
);
