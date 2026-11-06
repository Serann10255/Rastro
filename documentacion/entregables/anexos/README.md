# Anexos de la entrega de Rastro

Fecha: 2026-11-06

Lo que pide el formulario **«Subir anexos ahora (opcional)»** además de la
memoria técnica, que ya está en
[`../Rastro_Entrega2_AjusteAvanzado_CloudComputing_ISD38_Grupo30112.pdf`](../Rastro_Entrega2_AjusteAvanzado_CloudComputing_ISD38_Grupo30112.pdf).

| Campo del formulario | Qué se entrega | Archivo |
|---|---|---|
| Memoria técnica o documento final (PDF) | Entrega 2 | `../Rastro_Entrega2_…_Grupo30112.pdf` |
| Póster digital / imagen (JPG, PNG o PDF) | Póster A1 vertical | [`poster-rastro.pdf`](poster-rastro.pdf) (recomendado) · [`poster-rastro.png`](poster-rastro.png) · [`poster-rastro.jpg`](poster-rastro.jpg) |
| Enlace a video demostrativo (YouTube, Drive, Vimeo) | El enlace del video, una vez subido | [`video-demostrativo-rastro.mp4`](video-demostrativo-rastro.mp4) · guion en [`guion-video-demostrativo.md`](guion-video-demostrativo.md) |
| Enlace a repositorio o planos | El repositorio | `https://github.com/Serann10255/Rastro` |

Y, aparte del formulario, un **video pitch** para presentar Rastro a toda la
universidad: [`video-pitch-rastro.mp4`](video-pitch-rastro.mp4), 1 min 34 s
con música, guion en [`guion-video-pitch.md`](guion-video-pitch.md). Vende el
proyecto en lugar de enseñar a usarlo; si el formulario lo admite, también puede
ir en el campo del video.

| Video | Para quién | Qué cuenta | Duración |
|---|---|---|---|
| `video-demostrativo-rastro.mp4` | El docente | Cómo se usa: un envío de principio a fin con cada rol | 3 min 16 s, sin sonido |
| `video-pitch-rastro.mp4` | Toda la universidad | Qué problema resuelve, qué puede hacer y por qué confiar en él | 1 min 34 s, con música |

## Póster

| Archivo | Formato | Para qué |
|---|---|---|
| `poster-rastro.pdf` | A1 vertical (594 × 841 mm), una página, texto vectorial | El que se sube: se amplía sin perder nitidez y se puede imprimir |
| `poster-rastro.png` | 4939 × 6994 px (A1 a 211 ppp) | Si el formulario solo acepta imagen |
| `poster-rastro.jpg` | Igual que el PNG, más liviano | Si el formulario limita el peso del archivo |

Contenido, de arriba abajo: título, asignatura, docente, equipo y un código QR al
repositorio; cuatro cifras (9/9 requisitos, 327 pruebas superadas, 8 funciones
Lambda y 3 tablas, 10/11 controles conformes); problema; objetivo y método;
solución; cinco pantallas reales de la aplicación (panel, seguimiento, modo
ruta, consulta pública, bitácora); arquitectura en AWS con los ocho
microservicios; resultados y pruebas con el hallazgo principal; normativa;
tecnologías; conclusiones y limitaciones.

**De dónde sale cada cifra** (regla del proyecto: ninguna es decorativa):

| Cifra | Fuente |
|---|---|
| 9/9 requisitos, 4 objetivos cumplidos, 12 semanas en 4 fases | Entrega 2, apartados 3.2 y 5.2; guion de sustentación |
| 327 superadas, 5 omitidas, 0 fallos | `python -m pytest -q` en la raíz, ejecutado el 2026-11-06 (la Entrega 2 reporta 234/4 del 26/09; la suite creció con el modo ruta) |
| 8 funciones, 3 tablas, despliegue verificado 26/09 y 16/10 | `evidencias-despliegue/20260926T232402Z-verificacion.txt` y `20261016T162612Z-verificacion.txt` |
| 11 controles, 10 conformes, 1 desviado | Ejecución de referencia de Cotejo `20260926T235724886Z-4f87a8`, citada en la Entrega 2 |
| Secreto publicado 27 minutos, control C-09 | Hallazgo H-01, `documentacion/cambios/2026-09-26-h01-secreto-expuesto.md` |

Las capturas son de la pila local con datos sintéticos (`presentacion/capturas/`).

## Video demostrativo

`video-demostrativo-rastro.mp4`: MP4 H.264 de 1920 × 1080 a 30 fps, con pista de
audio en silencio. Recorre un envío de principio a fin con cada rol: el
despachador lo registra y lo asigna, el conductor sale a ruta desde el teléfono,
la empresa lo sigue en el mapa, el destinatario lo consulta sin cuenta, el
conductor lo entrega con foto, otra empresa intenta verlo y no puede, el
auditor verifica la bitácora y el administrador muestra los roles. Cada escena
lleva una leyenda con el rol y lo que se ve; **no tiene narración**. Si se
quiere voz, el texto para leer está en el
[guion](guion-video-demostrativo.md).

Se grabó automáticamente sobre la pila local, con datos sintéticos. El cierre lo
dice: el mismo código corre desplegado en AWS.

## Cómo subirlo

El formulario pide un **enlace**, no el archivo. Cualquiera de estas opciones
sirve; la de YouTube es la que mejor se reproduce en el navegador del docente.

**YouTube**

1. Entrar en <https://studio.youtube.com> con la cuenta de uno de los
   integrantes y pulsar **Crear → Subir videos**.
2. Elegir `video-demostrativo-rastro.mp4`.
3. Título: `Rastro — Trazabilidad verificable de envíos · Video demostrativo`.
   Descripción: la asignatura, el grupo, el equipo y el enlace al repositorio.
4. En **Visibilidad**, elegir **No listado**: lo ve quien tenga el enlace y no
   aparece en búsquedas. No usar **Privado**, porque el docente no podría verlo.
5. Copiar el enlace (`https://youtu.be/…`) y pegarlo en el campo «Enlace a
   video demostrativo».

**Google Drive**

1. Subir el archivo a Drive.
2. Clic derecho → **Compartir** → en «Acceso general», **Cualquier persona con
   el enlace**, rol **Lector**.
3. **Copiar enlace** y pegarlo en el formulario.

Antes de enviar el formulario, abrir el enlace en una ventana privada del
navegador: si pide iniciar sesión, el permiso no quedó bien.

## Cómo se regeneran

Las fuentes están en [`presentacion/anexos/`](../../../presentacion/anexos/); el
detalle, en el [README del módulo `presentacion`](../../modulos/presentacion/README.md#anexos-de-la-entrega-póster-y-video).

```bash
cd presentacion
npm install --no-save playwright-core@1.56.1 sharp@0.34.3 qrcode@1.5.4 ffmpeg-static@5.2.0
node anexos/exportar-poster.mjs    # póster: PDF, PNG y JPG
node anexos/grabar-demo.mjs        # video demostrativo: necesita la pila local levantada
node anexos/grabar-pitch.mjs       # video pitch: parte del MP4 del demostrativo
```
