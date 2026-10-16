# ADR-014 · El mapa usa Leaflet y teselas de OpenStreetMap

Fecha: 2026-10-16 · Estado: aceptada · Afecta a `web/src/componentes/Mapa.tsx`,
`web/package.json` y `design/componentes.css`

## Contexto

Las rutas de entrega ([ADR-013](adr-013-ubicacion-en-vivo-por-sondeo.md))
necesitan un mapa en tres pantallas: el modo ruta del conductor, el seguimiento
de la empresa y la consulta pública.

La interfaz no usa bibliotecas de componentes de terceros (lo explica la cabecera
de `componentes/ui.tsx`): el sitio se audita a sí mismo y conviene que lo que se
sirve sea código propio y revisable. Un mapa pone esa regla a prueba.

## Decisión

**Leaflet 1.9.4, fijado a versión exacta, envuelto en un componente propio y
cargado solo donde hay un mapa. Teselas de OpenStreetMap, con el proveedor
configurable en `configuracion.json`.**

- **Por qué una biblioteca aquí y no en el resto.** Dibujar teselas, proyectar
  coordenadas y responder a arrastrar y pellizcar con dos dedos es un problema
  resuelto y difícil de resolver bien. Hacerlo de nuevo sería código propio,
  pero peor y sin revisar: justo lo contrario de lo que la regla busca.
- **Por qué Leaflet.** No tiene dependencias propias —no arrastra una cadena de
  suministro— y es estable desde hace años. MapLibre exige WebGL y un estilo
  vectorial; Google Maps, una clave y un contrato.
- **Sin `react-leaflet`.** Sería otra dependencia para resolver lo que cabe en un
  archivo. `Mapa.tsx` crea el mapa una vez y actualiza marcadores y trazos.
- **Versión exacta** (`"leaflet": "1.9.4"`, sin `^`) y tipos `@types/leaflet`
  1.9.21. Una actualización es una decisión, no un efecto de `npm install`.
- **Carga diferida.** El componente se importa con `lazy()`: la biblioteca
  (≈ 45 KB comprimida) llega solo a quien abre un mapa. Quien consulta un envío
  ya entregado no la descarga.

### Teselas

- Por omisión, `tile.openstreetmap.org`, con su atribución visible.
- El sitio sirve las páginas con `Referrer-Policy: no-referrer`, y el servidor de
  OpenStreetMap deja de servir teselas a quien no dice desde qué sitio las pide.
  Las teselas llevan `referrerPolicy: strict-origin-when-cross-origin`: envían
  el origen y no la ruta, que puede llevar el identificador de un envío.
- El proveedor se puede cambiar sin recompilar, con la clave opcional `teselas`
  de `configuracion.json` (`{ "url": ..., "atribucion": ... }`). Es la misma
  razón que REQ-09 para la URL de la API: un uso intensivo exige mudarse a un
  proveedor con acuerdo, y eso no debería requerir un despliegue de código.
- En tema oscuro las teselas se invierten con un filtro CSS: un rectángulo
  blanco deslumbra de noche, cuando más se reparte.

### Accesibilidad y táctil

- Los controles de zoom miden 44 × 44 px (los de Leaflet, 30). Las reglas que lo
  imponen llevan `.leaflet-container` en el selector, porque la hoja de Leaflet
  llega después que la del sistema y con la misma especificidad ganaba; se
  detectó midiendo en el navegador.
- El mapa no es el único camino a un dato: cada pantalla dice con texto quién
  está dónde, desde hace cuánto y qué paradas quedan.
- Sin zoom con la rueda del ratón: en una página que se recorre con la rueda, el
  mapa se tragaba el gesto.

## Consecuencias

- Una dependencia de terceros en el sitio, la primera fuera de React y React
  Query. Se revisa al actualizarla.
- Las teselas se piden a un tercero. Lo que recibe es la zona del mapa que se
  mira y el origen del sitio; no recibe identificadores ni datos del envío.
- El uso del servidor público de OpenStreetMap está pensado para volumen bajo.
  Para una operación real hay que pasar a un proveedor con acuerdo, cambiando
  `teselas` en la configuración.
