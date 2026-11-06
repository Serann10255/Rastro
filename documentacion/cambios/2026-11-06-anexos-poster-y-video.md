# Cambios · 2026-11-06 · Anexos de la entrega: póster digital y video demostrativo

El formulario de entrega de Rastro pide, además de la memoria técnica, un
**póster digital** (JPG, PNG o PDF) y el **enlace a un video demostrativo**
(YouTube, Drive o Vimeo). Ninguno de los dos existía. Ahora están en
[`documentacion/entregables/anexos/`](../entregables/anexos/README.md), junto
con los pasos para subirlos.

## Qué se entrega

| Archivo | Qué es |
|---|---|
| `poster-rastro.pdf` | Póster A1 vertical, una página, texto vectorial (8,7 MB) |
| `poster-rastro.png` · `.jpg` | El mismo póster a 4939 × 6994 px (4,3 MB y 2,8 MB) |
| `video-demostrativo-rastro.mp4` | 3 min 16 s, 1920 × 1080, H.264, con franja de leyenda y sin narración (14 MB) |
| `guion-video-demostrativo.md` | Escenas con tiempos, texto para voz en off y lista de tomas para grabarlo a mano |
| `README.md` | Qué archivo va en qué campo, de dónde sale cada cifra y cómo subir el video |

El póster tiene problema, objetivo y método, solución, cinco pantallas reales,
arquitectura en AWS con los ocho microservicios, resultados y pruebas,
normativa, tecnologías, conclusiones, el equipo y un QR al repositorio. El video
sigue una orden de principio a fin con los cinco roles y el destinatario, y
termina comprobando el aislamiento, la bitácora y los roles.

## Video pitch para la universidad

Después, el mismo día, se pidió un segundo video: no para enseñar a usar Rastro
sino **para presentarlo a toda la universidad**, como un pitch.
[`video-pitch-rastro.mp4`](../entregables/anexos/video-pitch-rastro.mp4) dura
1 min 34 s: gancho («Su pedido va en camino. ¿Dónde?»), el problema de la
información repartida, la marca, las tres personas que la usan, seis
funcionalidades con la aplicación real, «Seguro por diseño», cuatro cifras y un
cierre con QR al repositorio. Tiene **música original**, sintetizada para el
video, así que se puede publicar sin problemas de derechos. Escenas, cifras y
una locución opcional en
[`guion-video-pitch.md`](../entregables/anexos/guion-video-pitch.md).

Se renderiza cuadro a cuadro desde `presentacion/anexos/pitch.html` con
`grabar-pitch.mjs`, y la música sale de `musica-pitch.mjs`. Las frases y cifras
son las de la presentación a la universidad.

### Correcciones al pitch, señaladas por el equipo

- **«Sin instalar nada» no era cierto**: Rastro también se instala, como app
  de Android y de escritorio con el cliente Flet. La escena de las tres
  personas dice ahora «En el navegador o instalada como app, en Android y en el
  computador».
- **El mapa de seguimiento «se desubicaba»**: el fragmento venía del video
  demostrativo, donde el conductor avanza a saltos de 450 m y el mapa se
  reencuadra al elegir la ruta. Se grabó un plano propio
  (`grabar-seguimiento.mjs` → `presentacion/anexos/fragmentos/seguimiento-en-vivo.mp4`)
  con el conductor a velocidad de ciudad y la vista fija, y el pitch se volvió a
  renderizar.

## Fuentes nuevas

En `presentacion/anexos/`: `poster.html`, `exportar-poster.mjs`,
`grabar-demo.mjs`, `grabar-seguimiento.mjs`, `pitch.html`, `grabar-pitch.mjs` y `musica-pitch.mjs`, y el plano `fragmentos/seguimiento-en-vivo.mp4`. Cómo funcionan, qué se descartó y por qué, en el
[README del módulo `presentacion`](../modulos/presentacion/README.md#anexos-de-la-entrega-póster-y-video).
No se añadieron dependencias al módulo ni cambió la construcción del deck.

## Cifras

La suite de pruebas se volvió a ejecutar el 2026-11-06 sobre `239128a`:
**327 superadas, 5 omitidas, 0 fallos**. Es la cifra que llevan el póster y el
cierre del video. La Entrega 2 reporta 234 y 4 porque es del 26/09: la suite
creció con el modo ruta. El resto de cifras son las de la Entrega 2 y de las
evidencias del despliegue, sin cambios.

## Encontrado al grabar

- **La imagen `minio/minio:RELEASE.2025-04-22T22-12-26Z` ya no se puede
  descargar de Docker Hub** («pull access denied … repository does not
  exist»), así que `docker compose up -d` falla en un equipo que no la tenga en
  caché. Para grabar se levantó la pila con un archivo de Compose adicional,
  fuera del repositorio, que sustituye el servicio `almacen` por
  `cgr.dev/chainguard/minio:latest` (mismo binario de MinIO, con `user: "0"` para
  escribir en el volumen). `docker-compose.yml` no se tocó: **queda pendiente**
  elegir y fijar una imagen de reemplazo para el almacenamiento local.
