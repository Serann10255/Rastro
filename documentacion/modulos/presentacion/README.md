# Módulo `presentacion` — diapositivas de sustentación y de la universidad

Ubicación: `presentacion/` · Puerto local: 5177 · Stack: React 18 + TypeScript + Vite

## Qué hace

Sirve las dos sustentaciones y la presentación de Rastro a la universidad como
un sitio estático de cuatro páginas:

| Ruta | Qué hay |
|---|---|
| `/` | Índice: los tres decks, recuento de diapositivas, **quién presenta qué y cuánto habla** y las teclas |
| `/rastro` | Deck de Rastro (Cloud Computing, ISD38) |
| `/cotejo` | Deck de Cotejo (Auditoría de Sistemas, ISD39) |
| `/universidad` | Rastro para toda la universidad: público general, sin tecnicismos, con demostración en vivo (2026-10-26) |
| `/rastro/?guion`, `/cotejo/?guion`, `/universidad/?guion` | Guion: todas las diapositivas seguidas con su texto hablado, y aviso de las que no caben |

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
| `z` o clic sobre una captura | Amplía la captura de pantalla a toda la ventana; `Esc` o un clic la cierra |
| Ctrl+P | Imprimir el guion |

**Enlace directo:** `/rastro#7` abre la diapositiva 7; `/rastro#bloque-4`, la
portadilla del bloque 4 (solo en un guion con portadillas). La dirección se
actualiza al avanzar, así que recargar retoma donde se estaba.

**Imprimir.** Dos formatos:

| Formato | Cómo | Qué sale |
|---|---|---|
| Guion | Ctrl+P desde cualquier modo, o **Imprimir guion** en `?guion` | **Un documento de texto en vertical, sin las láminas, una hoja por diapositiva**: la hoja N es la diapositiva N, con su bloque, número y título, quién la presenta, el tiempo estimado, el texto hablado, la indicación y la respuesta preparada. La primera hoja lleva además la cabecera con el reparto. **Con el tema que se está viendo** |
| Solo diapositivas | **PDF de diapositivas** en `?guion`, o Ctrl+P desde `/rastro/?diapositivas` | Cada diapositiva a página completa de 16:9 (13,33 × 7,5 in), sin notas. **Con el tema que se está viendo**: claro u oscuro |

**En el diálogo, el destino tiene que ser *Guardar como PDF*** (el del propio
Edge o Chrome), con márgenes «Ninguno» y sin encabezados ni pies. El tamaño y
la orientación los fija la hoja de estilos (`@page`), y el navegador solo los
respeta con ese destino: con *Microsoft Print to PDF* o cualquier impresora del
sistema manda el papel del controlador, carta vertical, y cada diapositiva sale
en vertical y partida en dos hojas. Es el síntoma que se vio el 2026-10-16; la
página del guion lo advierte debajo de los botones. Comprobado con el motor de
Edge: respetando el CSS salen 960 × 540 pt las diapositivas, una por página,
y el guion en carta vertical, una hoja por diapositiva; 9 páginas Rastro, 10
Cotejo y 11 la de la universidad, en los dos formatos. Están
en [`entregables/sustentacion/`](../../entregables/sustentacion/), junto a los
de la versión completa de 35 páginas.

**Sin diálogo, que es lo recomendable:** con el sitio en el puerto 5177 (el
contenedor o `npm run dev`),

```bash
cd presentacion
npm install --no-save playwright-core@1.56.1
npm run pdf                         # los seis PDF (dos por deck), tema claro
npm run pdf -- --tema=oscuro        # los seis, tema oscuro, con «oscuro» en el nombre
npm run pdf -- --solo=universidad   # solo los de ese deck (o rastro,cotejo)
```

`--solo` existe para no regenerar los PDF de los demás decks cuando solo cambió
uno: cada exportación reescribe el archivo aunque el contenido sea el mismo, y
el historial se llenaría de binarios idénticos.

`exportar-pdf.mjs` imprime con el Edge instalado y `preferCSSPageSize`, escribe
en `documentacion/entregables/sustentacion/` y dice cuántas páginas salieron.
`?tema=` abre la página con ese tema sin guardarlo como preferencia; el guion
también funciona con la orden cruda de Edge
(`msedge --headless=new --no-pdf-header-footer --print-to-pdf=… "http://localhost:5177/rastro/?diapositivas&tema=claro"`),
que es lo que se usaba antes.

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
| Bloque de código con `234 superadas · 4 omitidas` | Cifras de resultado, no código. En el visor, cada cifra cuenta desde cero |
| `![Título](figura:identificador)` | Figura de `presentacion/src/figuras/<identificador>.tsx`. Si no existe, la construcción se detiene |
| `![Título](captura:nombre)` | Captura de pantalla de `presentacion/capturas/<nombre>.webp` (o `.png`, `.jpg`), dentro de una ventana de navegador cuya barra muestra el título. Si no existe, la construcción se detiene |
| Dos o más figuras o capturas seguidas | **Galería**: ocupan el sitio de una y en el visor pasan solas cada 5 s. En una diapositiva de contenido pasa una vez y se queda en la última; en la portada da vueltas. Fuera del visor se ve ese elemento de reposo, y en el teléfono, todos |

Figuras, capturas y galerías van siempre a la columna derecha de la
diapositiva, con el texto a la izquierda. En la portada, el visual sustituye al
logotipo grande, que se recoge sobre el nombre.

## Figuras

| Identificador | Diapositiva | Contenido |
|---|---|---|
| `arquitectura-rastro` | Rastro 2 | Componentes desplegados en AWS, de [vision-general](../../arquitectura/vision-general.md), con los ocho servicios como una sola caja |
| `ejecutor-cotejo` | Cotejo 4 | El ejecutor y sus tres fuentes de evidencia (Entrega 2, tablas 9 y 11) |
| `informacion-repartida` | Universidad 2 | El paquete en el centro y los cuatro sitios donde vive lo que se sabe de él, unidos con línea discontinua |
| `viaje-del-paquete` | Universidad 4 | Los seis estados del camino normal, con su código y una frase; «En reparto» resaltado y «Entregado» en verde |
| `demo-en-vivo` | Universidad 6 | Mensajero → empresa → cliente → entregado: quién hace qué durante la demostración |
| `pago-por-uso` | Universidad 7 | Un día de 24 horas: el servidor propio cobra todas, la nube solo las de uso. Ilustración, no medición |
| `cadena-de-registros` | Universidad 8 | Cuatro registros de la bitácora encadenados; el tercero, cambiado, rompe el eslabón siguiente |

Las cinco de la universidad explican ideas, no la arquitectura: ninguna nombra
un servicio de AWS. Usan dos variantes nuevas de caja, `exito` y `peligro`, que
siempre van con una palabra que dice lo mismo («Entregado», «cambiado»): el
color nunca es el único portador del significado.

Son SVG con color por clase CSS sobre las fichas de diseño: cambian con el tema
y con la identidad de cada proyecto. El texto no baja de 25 unidades en un lienzo
de 820, el ancho de una columna de la diapositiva. Las flechas llevan
`pathLength={1}` para que el visor pueda trazarlas al entrar.

## Capturas de pantalla

Las pantallas de las dos aplicaciones, en `presentacion/capturas/`, citadas en
el guion como `![Título](captura:nombre)`:

| Archivo | Pantalla | Dónde se usa |
|---|---|---|
| `rastro-panel` | Panel de la organización, sesión de administrador | Rastro 1 · Cotejo 1 y 2 · Universidad 1 y 3 |
| `rastro-envio` | Detalle de un envío con su histórico | Rastro 1 · Universidad 3 |
| `rastro-rastreo` | Consulta pública del destinatario, sin cuenta | Rastro 1 |
| `rastro-bitacora` | Bitácora de auditoría con la cadena verificada, sesión de auditor | Rastro 1 y 6 · Universidad 1 y 8 |
| `rastro-roles` | Roles y permisos | Rastro 6 |
| `rastro-seguimiento` | Seguimiento: el mapa de la empresa con una ruta en curso, su recorrido y sus paradas | Universidad 1 y 5 |
| `rastro-modo-ruta` | Modo ruta del conductor: ubicación compartida, mapa y paradas con sus botones | Universidad 5 |
| `rastro-rastreo-en-camino` | Consulta pública de un envío en reparto: «Su envío va en camino» con el mapa | Universidad 1, 5 y 11 |
| `rastro-envios`, `rastro-operaciones`, `rastro-acceso` | Lista de órdenes, operaciones, acceso | Disponibles, sin usar |
| `cotejo-revision` | Revisión con el resumen de resultados y los primeros controles | Cotejo 1 |
| `cotejo-catalogo` | Qué se revisa: el catálogo con su criterio | Cotejo 1 y 2 |
| `cotejo-comparacion` | Repetir: dos revisiones comparadas | Cotejo 1 |
| `cotejo-hallazgos` | «Lo que hay que arreglar» en la revisión | Cotejo 8 · Universidad 9 |
| `cotejo-papel` | Un papel de trabajo abierto, con las dos huellas que coinciden | Cotejo 1 y 9 |

`cotejo-revision` no se usa en la de la universidad a propósito: es de la pila
local y dice «6 bien, 1 mal, 4 sin revisar», junto a una lámina que da las
cifras de la revisión en AWS (10 conformes, 1 desviado). Ante público general,
dos cifras distintas en la misma lámina parecen una contradicción.

Son WebP de 2880 × 1800 (una ventana de 1440 × 900 a doble densidad, calidad
82, entre 40 y 220 KB cada una): nítidas a media diapositiva de 1920 px y
ampliadas a toda la pantalla, sin pasar de 2 MB en total. Las genera
`capturas/capturar.mjs` con Playwright sobre el Edge del equipo y con la pila
local levantada:

```bash
docker compose up -d                       # desde la raíz: las dos aplicaciones
cd presentacion
npm install --no-save playwright-core@1.56.1 sharp@0.34.3
node capturas/capturar.mjs                 # todas
node capturas/capturar.mjs --solo=ruta     # solo las del modo ruta (o rastro, cotejo)
```

La imagen `web` tiene que incluir el modo ruta: si se construyó antes del
2026-10-16, `docker compose up -d --build --no-deps web`. El 2026-10-23 la del
equipo era anterior y `/entregas` no existía.

Qué hace el guion de captura, y por qué así:

- **Intercepta `configuracion.json`.** Las dos interfaces se construyen con la
  configuración del despliegue en AWS (`web/public/configuracion.json` apunta a
  la cuenta real), así que el contenedor local llamaría a AWS. El guion responde
  esa petición con la pila local sin tocar el archivo: las pantallas salen de
  los datos sintéticos de `seed/`, que es lo único que se puede proyectar.
- **Entra con los usuarios de la semilla**, leídos de `seed/organizaciones.json`:
  el administrador para el panel, las órdenes y los roles; el auditor para la
  bitácora y para Cotejo. Ninguna clave se escribe en el guion.
- **En Cotejo lanza dos revisiones** y luego elige, entre las guardadas, la
  primera que tenga un hallazgo («1 mal»), para que la pantalla de hallazgos y
  el papel de trabajo muestren C-09b y H-01. En la pila local esa ejecución es
  la del 1/10/2026 (`cotejo/papeles/20261001T235320510Z-4f7bea`), hecha desde
  el equipo con `git` disponible; hay que copiarla al volumen una vez:
  `docker compose cp cotejo/papeles/20261001T235320510Z-4f7bea cotejo-api:/papeles/`.
  Las dos revisiones del día son las que compara la pantalla de repetición.
- **El modo ruta se prepara por la API**, como lo haría el teléfono: el
  conductor de la semilla con más guías en su poder sale a ruta con todas y
  reporta treinta posiciones por Chapinero (de la calle 45 a la 65 por la
  Caracas). Si ya tenía una ruta abierta de una captura anterior, la cierra
  antes. **Espera unos treinta segundos** antes de reportar: el servidor recorta
  al presente cualquier hora futura y ordena el recorrido por hora, así que con
  horas inventadas hacia adelante todas quedaban iguales y el trazo salía en
  zigzag (se vio el 2026-10-23). Después captura el mapa de Seguimiento como
  administrador, el modo ruta como conductor con el GPS del navegador fijado en
  el último punto, y la consulta pública de la primera parada. Las teselas son
  de OpenStreetMap: hace falta conexión. Deja la ruta abierta en la pila local;
  la siguiente captura la cierra.
- **No añade dependencias al módulo.** `playwright-core` usa el canal `msedge`
  instalado, sin descargar navegadores, y `sharp` convierte a WebP; se
  instalan sin guardar y `npm ci` los retira.

Las cifras de esas pantallas son de la pila local: los controles que necesitan
la cuenta de AWS quedan SIN REVISAR, y así lo dice la respuesta preparada de
Cotejo 8. La ejecución de referencia sigue siendo la del 26/09/2026.

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

**Movimiento solo en el visor, y solo con hoja de estilos** (2026-10-16). Hasta
esta fecha se cambiaba de diapositiva en seco. Ahora la saliente se desvanece
hacia el lado contrario al avance y la entrante llega por el otro (460 ms); el
contenido aparece escalonado en el orden en que se lee —bloque a bloque, y
dentro de una tabla o lista, fila a fila—; las cifras de resultado cuentan desde
cero; las flechas de las figuras se trazan; las capturas respiran con un
acercamiento del 4,5 % en 16 s. Nada dura más de dos segundos ni bloquea: se
puede avanzar en mitad de la entrada. El código solo decide cuál sale y cuál
entra (`lienzo--sale`, `lienzo--entra`, `--direccion`) y numera los bloques
(`--i`) y las filas (`--j`); los tiempos viven en `presentacion.css`. El guion,
la lectura en el teléfono y el papel no animan nada, y `prefers-reduced-motion`
lo apaga todo. Sigue sin haber biblioteca de presentaciones, y los controles se
siguen ocultando tras 2,5 s sin mover el ratón.

**Las capturas van en una ventana de navegador**, con su barra y el título de la
pantalla: separa la imagen del fondo de la lámina en los dos temas y ahorra el
pie de figura. En el visor, un clic o `z` la amplía a toda la ventana sobre un
fondo oscurecido, por si el jurado pide verla de cerca; `Esc` vuelve. La
ampliación es interfaz del visor y no parte del lienzo: mide en unidades de
pantalla.

**Una galería pasa sola.** Dos o más visuales seguidos en el Markdown comparten
el sitio de uno y se turnan cada cinco segundos, con un fundido de 700 ms. En
una diapositiva de contenido la galería pasa una vez y se queda en el último
elemento, que es el que se imprime y el que debe acompañar el final del guion
hablado; en la portada da vueltas, porque está en pantalla mientras el jurado se
acomoda. Los puntos permiten saltar a un elemento, pero la idea es que el
presentador no tenga que tocar nada: en cinco minutos no sobran clics.
Descartado: avanzar la galería con la flecha, como los «fragmentos» de otras
herramientas, porque multiplica los clics y rompe el reparto de tiempo.

**El interruptor de tema es el de las aplicaciones**, con dos diferencias: claro
por omisión, porque un proyector lava el oscuro, y su propia clave de
almacenamiento, para no proyectar en oscuro por arrastrar la preferencia de la
aplicación.

**Se imprime lo que se ve.** El guion y el PDF de solo diapositivas salen con el
tema que se está viendo; si es el del sistema, se resuelve en el momento de
imprimir y se fija, para no depender de cómo trate cada navegador esa
preferencia. Ninguna hoja lleva margen de página sino relleno propio: el margen
de página no se pinta, y en oscuro quedaba un marco blanco. Se decide en el
evento `beforeprint`,
que Chrome y Edge lanzan con Ctrl+P y con `window.print()`; la impresión sin
interfaz de Edge no lo lanza, y por eso ahí el tema se fija con `?tema=`. Es una copia del componente de `web/`: moverlo a `design/` exigiría
tocar las dos interfaces y queda como mejora.

**El formato de impresión se marca en la raíz, no se elige en la hoja de
estilos.** `@page` no admite condiciones por clase, así que las diapositivas
sueltas usan una página con nombre (`@page diapositiva`) que solo se asigna
cuando la raíz lleva `data-impresion="diapositivas"`. El lienzo se imprime a
0,6666: un pelo por debajo de 2/3, porque a 2/3 exactos el redondeo empuja cada
lámina a una segunda página en blanco.

**El guion impreso no lleva las láminas** (2026-10-16). Hasta este día cada
hoja del guion era una diapositiva apaisada con sus notas debajo. Nunca tuvo
sitio de sobra: iba justa (689–807 px de los 816 de una carta apaisada) y en
cuanto el diálogo añadía sus márgenes de 10 mm casi todas se pasaban, el
sobrante saltaba a una hoja casi vacía y las notas seguían bajo la diapositiva
siguiente. Se probó fijar cada hoja a `100vh` con la lámina más pequeña y las
notas en dos columnas, y seguía siendo un equilibrio frágil que dependía del
papel y de los márgenes. La salida fue quitar la lámina: el guion es un
documento de texto en vertical con una hoja por diapositiva —la hoja N es la
diapositiva N, y la primera lleva además la cabecera con el reparto—, así que
nada puede recortarse ni saltar: la entrada más larga ocupa poco más de media
hoja. Las láminas ya se descargan aparte con **PDF de diapositivas**, que es
donde se ven a tamaño completo; en el documento basta el bloque, el número y el
título para saber en cuál se está. Sale con el tema que se está viendo, como
las diapositivas, y por eso tampoco lleva margen de página sino relleno propio
de 16 × 18 mm en cada hoja: el margen de página no se pinta y en oscuro dejaba
un marco blanco. En el formato de solo diapositivas, cada lámina es
exactamente una hoja (`100vh`, con el sobrante recortado) y la escala se
calcula desde el área de página (`tan(atan2(100vw, 1920px))`, que es cómo se
dividen dos longitudes en CSS) dentro de `@supports`, de modo que con márgenes
impuestos la lámina se encoge en lugar de salirse; sin soporte, queda la escala
fija de 0,6666.

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

**Un tercer deck para toda la universidad** (2026-10-26). El proyecto fue
seleccionado para presentarse ante la comunidad de la CUN: estudiantes de
cualquier carrera, docentes y directivos. Las sustentaciones no sirven ahí:
siguen los siete bloques del docente y hablan de controles, normas y roles de
IAM. Se escribió un guion aparte, `presentacion-universidad.md`, con el mismo
motor, la misma identidad de Rastro y las mismas reglas (ninguna cifra
decorativa, guion hablado en cada lámina, «Si preguntan» para lo técnico).

- **Ideas antes que piezas.** Cada lámina cuenta una idea con algo que el
  público ya conoce: esperar un paquete, el recibo de la luz, una cadena, un
  cofre. Los nombres de los servicios de AWS solo aparecen en «Si preguntan».
- **El modo ruta en el centro**, con una demostración en vivo (lámina 6) y las
  tres pantallas en capturas justo antes, que son el respaldo si el GPS del
  salón no responde.
- **Sin bloques.** No lleva `# BLOQUE`: la prueba de los siete bloques aplica a
  las sustentaciones y no a este guion, que tiene su propia prueba (compila sin
  avisos, cada lámina con guion y quien la presente, los tres integrantes).
- **Página propia, `/universidad`**, y no un modo de `/rastro`: comparte
  identidad pero no contenido, y así cada uno se imprime y se enlaza por su
  cuenta.

Descartado: reutilizar el deck de Rastro quitando láminas, porque el problema
no era la cantidad sino el registro (mínimo privilegio, ISO 27001, C-09 no le
dicen nada a quien no estudia sistemas); y una plataforma externa de
presentaciones, porque perdería las capturas, el guion y la exportación que ya
tiene este módulo.

## Dependencias y relaciones

- **Lee**: `documentacion/sustentacion/*.md` y `presentacion/capturas/*.webp` al
  construir.
- **Para regenerar las capturas** necesita la pila local completa
  (`docker compose up -d`) y el Edge del equipo; no es una dependencia de la
  construcción ni del contenedor.
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
| Usable a 360 px | Modo lectura; comprobado a 360 y 375 px, y `/universidad` y el índice con tres decks a 360 px el 2026-10-26 (`scrollWidth` = 360) |
| Sin scroll horizontal en el documento | Comprobado en lectura; en presentación la lámina se escala y nunca excede la ventana |
| Tablas anchas con scroll propio | En lectura, `overflow-x: auto` con ancho mínimo de 34 rem; en el lienzo no hace falta |
| Áreas táctiles de 44 px | Botones del sistema de diseño; los bordes pulsables miden el 12 % del ancho y nunca menos de 44 px |
| Texto que no desborda | `overflow-wrap` en código, rutas y títulos |
| Navegación colapsada | La barra de controles se envuelve y se oculta sola; en lectura, las acciones pasan a filas |

## Pendiente de comprobar

- **Pantalla completa** no se pudo verificar en el navegador integrado, que no
  concede la API. Usa `requestFullscreen` estándar; comprobar en Chrome o Edge
  antes de la sustentación.
- **La demostración en vivo de `/universidad`** depende de la cuenta de AWS
  (laboratorio abierto, o la cuenta de la universidad) y del GPS de un teléfono
  dentro del auditorio. Ensayarla en el lugar, con la red de la sala.
