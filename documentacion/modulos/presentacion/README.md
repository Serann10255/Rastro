# Módulo `presentacion` — diapositivas de sustentación

Ubicación: `presentacion/` · Puerto local: 5177 · Stack: React 18 + TypeScript + Vite

## Qué hace

Sirve las dos sustentaciones como un sitio estático de tres páginas:

| Ruta | Qué hay |
|---|---|
| `/` | Índice: los dos decks, recuento de diapositivas, **quién presenta qué** y las teclas |
| `/rastro` | Deck de Rastro (Cloud Computing, ISD38) |
| `/cotejo` | Deck de Cotejo (Auditoría de Sistemas, ISD39) |
| `/rastro/?guion`, `/cotejo/?guion` | Guion: todas las diapositivas seguidas con sus notas, y aviso de las que no caben |

**El contenido no está en el código.** Se lee al construir desde
[`documentacion/sustentacion/`](../../sustentacion/): si cambia el Markdown y se
vuelve a construir, cambia el deck. En desarrollo basta con guardar el archivo.

## Cómo se usa

```bash
cd presentacion
npm install
npm run dev        # http://localhost:5177
npm test           # pruebas del compilador de guiones (Node 22.6 o superior)
npm run build      # sitio estático en presentacion/dist/
```

| Tecla | Acción |
|---|---|
| → ↓ Av Pág Espacio | Siguiente |
| ← ↑ Re Pág Mayús+Espacio | Anterior |
| Clic en el borde derecho o izquierdo | Siguiente o anterior |
| Inicio · Fin | Primera · última |
| `n` | Notas del presentador (ocultas por omisión) |
| `f` | Pantalla completa |
| Ctrl+P | Imprimir el guion |

**Enlace directo:** `/rastro#7` abre la diapositiva 7; `/rastro#bloque-4`, la
portadilla del bloque 4. La dirección se actualiza al avanzar, así que recargar
retoma donde se estaba.

**Imprimir:** desde cualquier modo, Ctrl+P saca el guion completo: una
diapositiva por página horizontal, con su número, quién la presenta y sus notas
debajo. Se imprime siempre en tema claro. Probado con Edge: 35 páginas por deck,
carta apaisada.

## Formato del guion

El compilador (`compilador/sustentacion.ts`) espera esta estructura:

~~~markdown
# Sustentación — Rastro

```yaml
proyecto: Rastro
equipo: [Nombre Uno, Nombre Dos]
```

---

## 1 · Portada          ← diapositiva numerada: el número es el del enlace
**RASTRO**
Trazabilidad verificable de envíos

> Notas: Sergio. Diez segundos, no leer.

---

# BLOQUE 1 · PRESENTACIÓN DEL SISTEMA   ← portadilla, sin número propio
~~~

| Elemento | Cómo se lee |
|---|---|
| `---` | Separa diapositivas |
| `## N · Título` | Diapositiva de contenido. **El número es obligatorio**: es el que se ve, el del enlace y el que citan las notas. Repetido detiene la construcción; con saltos, avisa |
| `# BLOQUE N · TÍTULO` | Portadilla. Enumera por sí sola las diapositivas que agrupa |
| Párrafo | **Conserva los saltos de línea**: «una frase por línea» se respeta |
| `> Notas: Nombre. …` | Nota del presentador. El nombre alimenta el reparto de intervenciones y se arrastra a las siguientes hasta que otra nota nombre a otro |
| `> …` sin «Notas:» | Cita destacada, parte del contenido |
| Tabla sin fila `\|---\|` o con encabezado vacío | Tabla sin encabezado: la primera columna nombra la fila |
| `\|:---:\|` | Columna centrada. En ella, `✓`, `—` y «Solo …» se dibujan como marcas de una matriz |
| Columna «Prob.», «Impacto», «Prioridad» o «Severidad» | Sus valores (Muy alto, Alto, Media…) llevan tono además de la palabra |
| Bloque de código con `234 superadas · 4 omitidas` | Cifras de resultado, no código |
| `![Título](figura:identificador)` | Figura de `presentacion/src/figuras/<identificador>.tsx`. Si no existe, la construcción se detiene |

## Figuras

| Identificador | Diapositiva | Contenido |
|---|---|---|
| `arquitectura-rastro` | Rastro 3 | Componentes desplegados en AWS, de [vision-general](../../arquitectura/vision-general.md), con los ocho servicios como una sola caja |
| `ejecutor-cotejo` | Cotejo 8 | El ejecutor y sus tres fuentes de evidencia (Entrega 2, tablas 9 y 11) |

Son SVG con color por clase CSS sobre las fichas de diseño: cambian con el tema
y con la identidad de cada proyecto. El texto no baja de 25 unidades en un lienzo
de 820, el ancho de una columna de la diapositiva.

## Decisiones

**Un lienzo fijo de 1920 × 1080 que se escala entero con `zoom`.** Es la única
medida fija del módulo, y es a propósito: una lámina, no un contenedor de página.
Así «24 px» significa lo mismo en el portátil del ensayo que en el proyector, y
una diapositiva que se desborda en uno se desborda en el otro.

**Tamaños por fichas, no por números sueltos.** Las fichas de `design/` están
pensadas para un teléfono; en el lienzo se multiplican por `--d-escala: 1.75`.
Cuerpo 28 px, tablas 26,25 px, y un suelo de 24 px (`--d-minimo`) que respeta
incluso el código en línea dentro de una tabla. Solo el pie y la numeración
bajan a 22,75 px: no son cuerpo.

**Si no cabe, se avisa; no se encoge.** Cada diapositiva mide su contenido. El
guion (`?guion`) lista las que se desbordan y el visor lo dice en las notas. Es
la forma de revisar tras editar el Markdown.

**Tres páginas y no una aplicación con rutas.** Cada deck lleva la identidad de
su proyecto, que se declara sobre `:root` en el `identidad.css` de cada
aplicación. Se importan esos archivos tal cual en lugar de copiar sus colores: si
cambia el azul de Rastro, cambia su deck.

**Compilador propio en lugar de una biblioteca de Markdown.** El subconjunto es
pequeño y la frontera que importa —dónde acaban las notas y empieza el
contenido— no la resuelve el Markdown estándar. Un lector propio falla en voz
alta ante lo que no entiende, con la línea del problema.

**El número de la diapositiva lo escribe el autor.** Calcularlo por posición haría
que las notas que dicen «desarrollarlo en la 23» apuntaran a otra diapositiva en
cuanto se añadiera una.

**Sin transiciones ni bibliotecas de presentaciones.** Se cambia de diapositiva en
seco; los controles se ocultan tras 2,5 s sin mover el ratón, sin animación.

**El interruptor de tema es el de las aplicaciones**, con dos diferencias: claro
por omisión, porque un proyector lava el oscuro, y su propia clave de
almacenamiento, para no proyectar en oscuro por arrastrar la preferencia de la
aplicación. Es una copia del componente de `web/`: moverlo a `design/` exigiría
tocar las dos interfaces y queda como mejora.

**Descartado:** calcular el número por posición; una biblioteca de presentaciones
(reveal.js y similares) por la regla de código propio; leer el Markdown en el
navegador, que habría hecho del guion un recurso más que servir y habría
retrasado los errores hasta abrir la página.

## Dependencias y relaciones

- **Lee**: `documentacion/sustentacion/*.md` al construir.
- **Usa**: el sistema de diseño de [`design/`](../sistema-de-diseno/README.md)
  —fichas, base, componentes y logotipos— y los `identidad.css` de
  [`interfaz-web`](../interfaz-web/README.md) y [`cotejo-web`](../cotejo-web/README.md).
- **No depende de la API** ni de ningún servicio: es contenido estático.
- **Nadie depende de él.**

## Comportamiento responsive

Pensado para proyector, pero usable en cualquier pantalla. Mismos breakpoints
del proyecto: sm 640, md 768, lg 1024, xl 1280.

| Pantalla | Qué se ve |
|---|---|
| Escritorio y tableta, o teléfono en horizontal | **Presentación**: la lámina escalada para caber, centrada, con franjas si la proporción no es 16:9 |
| Teléfono en vertical (`max-width: 767px` y vertical) | **Lectura**: las diapositivas se reflujan como tarjetas, a tamaño de aplicación, con las notas plegadas tras un botón |
| Papel | **Guion**: una diapositiva de 250 mm por página horizontal, notas a 12 pt debajo |

| Regla del proyecto | Cómo se cumple |
|---|---|
| Usable a 360 px | Modo lectura; comprobado a 360 y 375 px |
| Sin scroll horizontal en el documento | Comprobado en lectura; en presentación la lámina se escala y nunca excede la ventana |
| Tablas anchas con scroll propio | En lectura, `overflow-x: auto` con ancho mínimo de 34 rem; en el lienzo no hace falta |
| Áreas táctiles de 44 px | Botones del sistema de diseño; los bordes pulsables miden el 12 % del ancho y nunca menos de 44 px |
| Texto que no desborda | `overflow-wrap` en código, rutas y títulos |
| Navegación colapsada | La barra de controles se envuelve y se oculta sola; en lectura, las acciones pasan a filas |

## Pendiente de comprobar

- **Pantalla completa** no se pudo verificar en el navegador integrado, que no
  concede la API. Usa `requestFullscreen` estándar; comprobar en Chrome o Edge
  antes de la sustentación.
