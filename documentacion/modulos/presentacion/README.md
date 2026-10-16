# Módulo `presentacion` — diapositivas de sustentación

Ubicación: `presentacion/` · Puerto local: 5177 · Stack: React 18 + TypeScript + Vite

## Qué hace

Sirve las dos sustentaciones como un sitio estático de tres páginas:

| Ruta | Qué hay |
|---|---|
| `/` | Índice: los dos decks, recuento de diapositivas, **quién presenta qué y cuánto habla** y las teclas |
| `/rastro` | Deck de Rastro (Cloud Computing, ISD38) |
| `/cotejo` | Deck de Cotejo (Auditoría de Sistemas, ISD39) |
| `/rastro/?guion`, `/cotejo/?guion` | Guion: todas las diapositivas seguidas con su texto hablado, y aviso de las que no caben |

**El contenido no está en el código.** Se lee al construir desde
[`documentacion/sustentacion/`](../../sustentacion/): si cambia el Markdown y se
vuelve a construir, cambia el deck. En desarrollo basta con guardar el archivo.

## Cómo se usa

Para presentar, con Docker y sin Node en el equipo:

```bash
docker compose up -d --build presentacion   # http://localhost:5177
docker compose stop presentacion
```

La imagen compila el sitio y lo sirve con nginx. El guion queda dentro de la
imagen: tras editar el Markdown, `--build` lo vuelve a compilar (unos segundos;
las dependencias quedan en caché). Un guion que no compila detiene la
construcción con el mismo error que `npm run build`.

Para editar, con Node:

```bash
cd presentacion
npm install
npm run dev        # http://localhost:5177, recarga al guardar el Markdown
npm test           # pruebas del compilador de guiones (Node 22.6 o superior)
npm run build      # sitio estático en presentacion/dist/
```

El contenedor y el servidor de desarrollo usan el mismo puerto: no pueden
correr a la vez.

| Tecla | Acción |
|---|---|
| → ↓ Av Pág Espacio | Siguiente |
| ← ↑ Re Pág Mayús+Espacio | Anterior |
| Clic en el borde derecho o izquierdo | Siguiente o anterior |
| Inicio · Fin | Primera · última |
| `n` | Guion de la diapositiva: qué decir, cómo y qué responder (oculto por omisión) |
| `f` | Pantalla completa |
| Ctrl+P | Imprimir el guion |

**Enlace directo:** `/rastro#7` abre la diapositiva 7; `/rastro#bloque-4`, la
portadilla del bloque 4 (solo en un guion con portadillas). La dirección se
actualiza al avanzar, así que recargar retoma donde se estaba.

**Imprimir.** Dos formatos:

| Formato | Cómo | Qué sale |
|---|---|---|
| Guion | Ctrl+P desde cualquier modo, o **Imprimir guion** en `?guion` | Una diapositiva por página horizontal, con su número, quién la presenta, el tiempo estimado, su texto hablado, la indicación y la respuesta preparada. **Con el tema que se está viendo** |
| Solo diapositivas | **PDF de diapositivas** en `?guion`, o Ctrl+P desde `/rastro/?diapositivas` | Cada diapositiva a página completa de 16:9 (13,33 × 7,5 in), sin notas. **Con el tema que se está viendo**: claro u oscuro |

Para el PDF, en el diálogo se elige *Guardar como PDF*; el tamaño de página ya
viene dado. Probado con Edge: una página por diapositiva en los dos formatos
(carta apaisada el guion, 960 × 540 pt las diapositivas); con la versión corta
del 2026-10-16, 9 páginas Rastro y 10 Cotejo. Están en
[`entregables/sustentacion/`](../../entregables/sustentacion/), junto a los de
la versión completa de 35 páginas.

Sin diálogos, desde la terminal y con el servidor en marcha:

```bash
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --no-pdf-header-footer --virtual-time-budget=8000 --print-to-pdf="Rastro-diapositivas.pdf" "http://localhost:5177/rastro/?diapositivas&tema=claro"
```

Para el guion impreso, la misma orden con `http://localhost:5177/rastro/?tema=claro`.
Desde Git Bash, la ruta de salida va con barras `/`: con `\` delante de una
variable, Bash no la expande y el PDF cae en la carpeta de arriba con un nombre
literal. Para la versión oscura, `tema=oscuro` en lugar de `tema=claro`. `?tema=` abre la
página con ese tema sin guardarlo como preferencia.

## Formato del guion

El compilador (`compilador/sustentacion.ts`) espera esta estructura:

~~~markdown
# Sustentación — Rastro

```yaml
proyecto: Rastro
equipo: [Nombre Uno, Nombre Dos]
portadillas: no        ← opcional: los bloques no ocupan diapositiva propia
```

---

## 1 · Portada          ← diapositiva numerada: el número es el del enlace
**RASTRO**
Trazabilidad verificable de envíos

> Guion: Sergio. Buenos días, profesor. Somos…
> Indicación: Diez segundos. Mirar al jurado.
> Si preguntan: …

---

# BLOQUE 1 · PRESENTACIÓN DEL SISTEMA   ← portadilla, sin número propio
~~~

| Elemento | Cómo se lee |
|---|---|
| `---` | Separa diapositivas |
| `## N · Título` | Diapositiva de contenido. **El número es obligatorio**: es el que se ve, el del enlace y el que citan las notas. Repetido detiene la construcción; con saltos, avisa |
| `# BLOQUE N · TÍTULO` | Portadilla. Enumera por sí sola las diapositivas que agrupa. Con `portadillas: no` no ocupa diapositiva: solo marca el bloque de las siguientes. En los dos casos, cada diapositiva de contenido muestra su bloque sobre el título |
| Párrafo | **Conserva los saltos de línea**: «una frase por línea» se respeta |
| `> Guion: Nombre. …` | **Lo que se dice**, en la voz de quien lo dice. El nombre alimenta el reparto de intervenciones y se arrastra a las siguientes hasta que otro guion nombre a otro. Sus palabras dan el tiempo estimado |
| `> Indicación: …` (o `> Notas: …`) | Cómo decirlo. Se muestra debajo del guion, en menor jerarquía. No lleva nombre |
| `> Si preguntan: …` | Respuesta preparada para una repregunta probable |
| `> …` sin ninguno de esos prefijos | Cita destacada, parte del contenido |
| Tabla sin fila `\|---\|` o con encabezado vacío | Tabla sin encabezado: la primera columna nombra la fila |
| `\|:---:\|` | Columna centrada. En ella, `✓`, `—` y «Solo …» se dibujan como marcas de una matriz |
| Columna «Prob.», «Impacto», «Prioridad» o «Severidad» | Sus valores (Muy alto, Alto, Media…) llevan tono además de la palabra |
| Bloque de código con `234 superadas · 4 omitidas` | Cifras de resultado, no código |
| `![Título](figura:identificador)` | Figura de `presentacion/src/figuras/<identificador>.tsx`. Si no existe, la construcción se detiene |

## Figuras

| Identificador | Diapositiva | Contenido |
|---|---|---|
| `arquitectura-rastro` | Rastro 2 | Componentes desplegados en AWS, de [vision-general](../../arquitectura/vision-general.md), con los ocho servicios como una sola caja |
| `ejecutor-cotejo` | Cotejo 4 | El ejecutor y sus tres fuentes de evidencia (Entrega 2, tablas 9 y 11) |

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

**El guion es texto hablado, no consejos.** Cada diapositiva lleva lo que dice
quien la presenta, escrito a partir de lo que la diapositiva muestra y de la
Entrega 2; las indicaciones de escena y las respuestas preparadas van aparte y
en menor jerarquía. El tiempo se estima a 130 palabras por minuto, un ritmo
tranquilo: sirve para repartir, no sustituye cronometrarse en voz alta. Es un
texto para ensayar, no para leer delante del jurado.

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
aplicación.

**Se imprime lo que se ve.** El guion y el PDF de solo diapositivas salen con el
tema que se está viendo; si es el del sistema, se resuelve en el momento de
imprimir y se fija, para no depender de cómo trate cada navegador esa
preferencia. La hoja no lleva margen de página sino relleno propio: con margen,
el navegador pinta los bordes con su color y en oscuro quedaba un marco negro. Se decide en el evento `beforeprint`,
que Chrome y Edge lanzan con Ctrl+P y con `window.print()`; la impresión sin
interfaz de Edge no lo lanza, y por eso ahí el tema se fija con `?tema=`. Es una copia del componente de `web/`: moverlo a `design/` exigiría
tocar las dos interfaces y queda como mejora.

**El formato de impresión se marca en la raíz, no se elige en la hoja de
estilos.** `@page` no admite condiciones por clase, así que las diapositivas
sueltas usan una página con nombre (`@page diapositiva`) que solo se asigna
cuando la raíz lleva `data-impresion="diapositivas"`. El lienzo se imprime a
0,6666: un pelo por debajo de 2/3, porque a 2/3 exactos el redondeo empuja cada
lámina a una segunda página en blanco.

**Portadillas opcionales y el bloque sobre el título** (2026-10-16). Con cinco
minutos por sustentación, siete portadillas eran siete clics sin contenido. Se
pueden apagar con `portadillas: no`; los `# BLOQUE` siguen en el Markdown y
siguen marcando el bloque de cada diapositiva, que ahora se rotula sobre el
título («BLOQUE 4 · RIESGOS Y CONTROLES») en lugar de en el pie, donde a 22,75 px
no se leía desde el fondo de la sala. La prueba de los guiones ya no cuenta
portadillas: comprueba que los siete bloques aparecen, en orden, con al menos
una diapositiva cada uno.

**Imagen de Docker con el sitio compilado** (2026-10-16). Para presentar sin
instalar Node ni dependencias en el equipo de la sala. Sigue el patrón de
`web/` y `cotejo/web/`: una etapa compila con Node y la final es nginx con los
archivos, sin Node. El contexto es la raíz del repositorio y las rutas dentro
de la imagen reproducen las del repositorio, para que los alias de
`vite.config.ts` resuelvan sin cambios. Dos detalles propios:

- **Su propio `Dockerfile.dockerignore`.** El `.dockerignore` de la raíz deja
  fuera toda la documentación, y este módulo necesita `documentacion/sustentacion/`.
  En lugar de abrir esa excepción para todas las imágenes, el de este módulo es
  una lista de lo permitido: entran sus fuentes, `design/`, los estilos y
  `public/` de las dos interfaces y los guiones. El contexto pesa unos pocos KB.
- **`absolute_redirect off` en nginx.** `/rastro` redirige a `/rastro/`, como
  en desarrollo. Con la redirección absoluta, nginx escribiría el puerto en el
  que escucha dentro del contenedor (80) y no el publicado (5177).

Descartados: servir `npm run dev` en el contenedor con el Markdown montado como
volumen, que recargaría al guardar pero arrastra Node y `node_modules` a la
imagen y depende de que la vigilancia de archivos atraviese el montaje en
Windows; para editar ya está `npm run dev` sin Docker. Y un servicio con perfil
aparte en el compose: la sustentación también muestra la pila, así que conviene
que `docker compose up -d` la levante con todo.

**Descartado:** calcular el número por posición; una biblioteca de presentaciones
(reveal.js y similares) por la regla de código propio; leer el Markdown en el
navegador, que habría hecho del guion un recurso más que servir y habría
retrasado los errores hasta abrir la página. Para la versión corta, un segundo
par de guiones junto a los completos: dos fuentes de las mismas cifras acaban
contradiciéndose, y la completa ya está en el historial y en PDF.

## Dependencias y relaciones

- **Lee**: `documentacion/sustentacion/*.md` al construir.
- **Usa**: el sistema de diseño de [`design/`](../sistema-de-diseno/README.md)
  —fichas, base, componentes y logotipos— y los `identidad.css` de
  [`interfaz-web`](../interfaz-web/README.md) y [`cotejo-web`](../cotejo-web/README.md).
- **No depende de la API** ni de ningún servicio: es contenido estático. En
  `docker-compose.yml` es el servicio `presentacion`, sin `depends_on`, y se
  puede levantar solo.
- **Nadie depende de él.**

## Comportamiento responsive

Pensado para proyector, pero usable en cualquier pantalla. Mismos breakpoints
del proyecto: sm 640, md 768, lg 1024, xl 1280.

| Pantalla | Qué se ve |
|---|---|
| Escritorio y tableta, o teléfono en horizontal | **Presentación**: la lámina escalada para caber, centrada, con franjas si la proporción no es 16:9 |
| Teléfono en vertical (`max-width: 767px` y vertical) | **Lectura**: las diapositivas se reflujan como tarjetas, a tamaño de aplicación, con las notas plegadas tras un botón |
| Papel | **Guion**: una diapositiva de 220 mm por página horizontal y su texto hablado a 11,5 pt debajo, a todo el ancho. **Solo diapositivas**: página de 16:9 sin márgenes |

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
