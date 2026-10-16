# Cambios · 2026-10-16 · Diapositivas con capturas de la aplicación y movimiento

Las diapositivas describían el sistema pero no lo mostraban, y se cambiaba de
una a otra en seco. Ahora **enseñan las dos aplicaciones con capturas de
pantalla reales** y el visor **anima la entrada de cada diapositiva**, sin
añadir ninguna: siguen siendo 9 en Rastro y 10 en Cotejo.

---

## Qué ve el jurado

| Diapositiva | Antes | Ahora |
|---|---|---|
| Rastro 1 · Portada | Logotipo grande y texto | A la derecha, una ventana de navegador con el **panel**, el **detalle de un envío**, la **consulta pública** y la **bitácora**, que van pasando solas |
| Rastro 6 · Roles | Tabla a todo el ancho | Tabla a la izquierda; a la derecha, la pantalla de **roles y permisos** y, a los cinco segundos, la **bitácora con la sesión del auditor** |
| Cotejo 1 · Portada | Logotipo grande y texto | **Revisión**, **catálogo**, **repetición** y un **papel de trabajo**, pasando solos |
| Cotejo 2 · Sistema auditado | Solo texto | El **panel de Rastro** y, después, el **catálogo de Cotejo** |
| Cotejo 8 · Hallazgos | Solo texto | «**Lo que hay que arreglar**» en la pantalla de revisión, con C-09b en MAL |
| Cotejo 9 · También nos auditamos | Solo texto | Un **papel de trabajo abierto**: las dos huellas que coinciden, qué se hizo y qué contestó |

En todas, `z` o un clic amplía la captura a toda la ventana; `Esc` vuelve.

Y en todas las diapositivas: la anterior se desvanece hacia un lado y la nueva
entra por el otro; el título, las tablas fila a fila, las listas y los párrafos
aparecen escalonados; las cifras («234 superadas») cuentan desde cero; las
flechas de las figuras se trazan; las capturas respiran. Nada dura más de dos
segundos ni bloquea el avance. Quien tenga `prefers-reduced-motion` no ve nada
de esto.

## Capturas

Trece pantallas en `presentacion/capturas/` (WebP, 2880 × 1800, 2 MB en
total), generadas con `presentacion/capturas/capturar.mjs`: Playwright sobre
el Edge del equipo, contra la pila local y con los usuarios de la semilla. El
guion intercepta `configuracion.json` para que las interfaces, construidas con
la configuración de AWS, hablen con la pila local durante la captura. Para
Cotejo lanza dos revisiones y muestra la ejecución del 1/10/2026, que tiene el
hallazgo C-09b. Detalle y orden de ejecución en el
[README del módulo](../modulos/presentacion/README.md#capturas-de-pantalla).

Las cifras de esas pantallas son de la pila local (en Cotejo, lo que necesita
la cuenta de AWS sale SIN REVISAR); la respuesta preparada de Cotejo 8 lo
explica y la ejecución de referencia sigue siendo la del 26/09/2026.

## Cambios en el módulo `presentacion`

| Qué | Dónde |
|---|---|
| `![Título](captura:nombre)` y galerías (dos o más visuales seguidos); comprobación de que la captura existe, como con las figuras | `compilador/markdown.ts`, `compilador/sustentacion.ts`, `compilador/plugin.ts`, `src/deck/tipos.ts` |
| Registro de capturas por `import.meta.glob`, sin lista aparte | `src/capturas.ts` |
| Ventana de navegador, galería que pasa sola, contador de cifras, `--i`/`--j` para escalonar | `src/deck/Bloques.tsx` |
| Visual a la derecha; portada con visual; estado `entra`/`sale` y dirección | `src/deck/Diapositiva.tsx` |
| Transición con la saliente superpuesta, ampliación con `z`/clic/`Esc` | `src/deck/Visor.tsx`, `src/deck/animacion.ts` |
| Estilos de ventana, galería, ampliación y todas las animaciones; en lectura, la galería se despliega y nada se inclina; en papel, nada se mueve | `src/estilos/presentacion.css` |
| Flechas con `pathLength={1}` para trazarse | `src/figuras/*.tsx` |
| Guion de captura | `capturas/capturar.mjs` |
| Tecla `z` en el índice | `src/Inicio.tsx` |
| Seis pruebas nuevas: captura, galería con y sin línea en blanco, visual suelto, captura inexistente dentro y fuera de una galería, imagen que no es ni figura ni captura | `compilador/sustentacion.test.ts` |

Guiones: `documentacion/sustentacion/sustentacion-rastro.md` (portada y 6) y
`sustentacion-cotejo.md` (portada, 2, 8 y 9), con las indicaciones de escena
para las galerías y dos respuestas preparadas nuevas: en Cotejo 8, por qué las
cifras de la pantalla son de la pila local; en Cotejo 2, por qué Cotejo no es
una página web —la línea de comandos es la vía principal, la interfaz de
consulta del rol auditor está declarada en el apartado 7.2 del documento y no
se publica a propósito, porque los papeles de trabajo enumeran las debilidades
del sistema auditado—. Ninguna cifra cambió y el guion hablado es el mismo:
≈ 4 min 10 s por deck.

Documentación: [módulo presentacion](../modulos/presentacion/README.md),
[sustentación](../sustentacion/README.md#capturas-de-pantalla-2026-10-16) e
[instalación y uso](../guias/instalacion-y-uso.md#presentar-la-sustentación).

## PDF

Regenerados en [`entregables/sustentacion/`](../entregables/sustentacion/) con
`npm run pdf` y tema claro: `Rastro · sustentación.pdf` (9 páginas) y
`Cotejo · sustentación.pdf` (10), una diapositiva por página; y
`… guion.pdf`, el documento de texto, una hoja por diapositiva (9 y 10). En
las diapositivas cada galería muestra su elemento de reposo: la primera
pantalla en las portadas y la última en el resto.

## Exportar el PDF sin el diálogo

Al exportar desde el diálogo del navegador, las diapositivas y el guion salían
**en vertical y partidos en dos hojas**. La causa no está en el deck: la hoja
de estilos fija tamaño y orientación con `@page`, y el navegador solo los
respeta cuando el destino es *Guardar como PDF*; con *Microsoft Print to PDF*
u otra impresora del sistema manda el papel del controlador, carta vertical.
Comprobado con el motor de Edge: respetando el CSS salen 960 × 540 pt y carta
apaisada, una página por diapositiva.

| Qué | Dónde |
|---|---|
| `npm run pdf`: genera los cuatro PDF con el Edge instalado y `preferCSSPageSize`, sin diálogo; `--tema=oscuro` para la versión oscura | `presentacion/exportar-pdf.mjs`, `package.json` |
| Aviso bajo los botones de la página del guion: elegir *Guardar como PDF*, sin márgenes ni encabezados | `src/deck/Guion.tsx`, `presentacion.css` |
| **El guion impreso ya no lleva las láminas**: es un documento de texto en vertical, una hoja por diapositiva —la hoja N es la diapositiva N—, con bloque, número y título, quién la presenta, tiempo, guion, indicación y respuesta preparada, y la cabecera con el reparto en la primera hoja. Sale con el tema que se está viendo, y por eso sin margen de página sino relleno propio. Antes cada hoja era la lámina con las notas debajo: con los márgenes del diálogo el sobrante producía hojas casi en blanco y notas bajo la diapositiva siguiente, y fijar cada hoja a una página seguía siendo frágil | `src/deck/Guion.tsx`, `presentacion.css` |
| En el PDF de solo diapositivas cada lámina es exactamente una hoja y se escala al área de página (`tan(atan2(100vw, 1920px))` bajo `@supports`), así que cabe aunque el diálogo imponga márgenes o papel carta | `presentacion.css` |
| Cómo imprimir y qué hacer si sale vertical | [README del módulo](../modulos/presentacion/README.md#cómo-se-usa), [guía de uso](../guias/instalacion-y-uso.md#presentar-la-sustentación) |

## Verificación

- `npm test`: 25 pruebas, 0 fallos; `npm run typecheck` sin errores; los dos
  guiones compilan sin avisos.
- `/rastro/?guion` y `/cotejo/?guion`: «Ninguna se desborda».
- Impresión comprobada con el motor de Edge, en claro y en oscuro: el guion
  sale en vertical, una hoja por diapositiva y sin láminas, también forzando
  carta con márgenes de 10 mm o A4 desde el diálogo; las diapositivas, 9 y 10
  páginas de 960 × 540 pt respetando el CSS, y una por página aunque el
  diálogo imponga carta o A4.
- Visor: portadas, Rastro 2, 6 y 8, Cotejo 1, 2, 8 y 9 revisadas en claro y
  oscuro; la galería de Cotejo 2 llega al catálogo y se queda; `z` amplía y
  `Esc` cierra; sin errores en consola.
- A 375 px en vertical (modo lectura): sin scroll horizontal; las galerías se
  despliegan completas y las ventanas caben en el ancho.
- Imagen de Docker reconstruida con las capturas dentro.
- Pendiente: cronometrar en voz alta con las galerías en pantalla, para
  comprobar que la última pantalla de Rastro 6 y Cotejo 2 llega cuando toca.
