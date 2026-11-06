# Guion del video demostrativo — Rastro

Fecha: 2026-11-06 · Duración: 3 min 16 s · Archivo:
[`video-demostrativo-rastro.mp4`](video-demostrativo-rastro.mp4)

| | |
|---|---|
| Formato | MP4, H.264, 1920 × 1080, 30 fps; pista de audio AAC en silencio |
| Peso | ≈ 14 MB |
| Entorno | Pila local (`docker compose up -d`) con los datos sintéticos de `seed/` |
| Cómo se grabó | `presentacion/anexos/grabar-demo.mjs`: Playwright sobre el Edge del equipo, escena por escena, montado con ffmpeg |
| Narración | No tiene. Cada escena lleva una franja con el rol y lo que se ve. Abajo está el texto para grabar voz encima si se quiere |

El video sigue **un solo envío de principio a fin**, de modo que cada escena
continúa la anterior: se crea la orden de «Valentina Ríos Acosta», se asigna a
Carlos Nieto Pardo, sale en su ruta, se sigue en el mapa, la destinataria la
consulta sin cuenta, se entrega con foto y, al final, se comprueban los
controles: aislamiento entre empresas, bitácora y roles.

---

## Escenas

Tiempos de la grabación del 2026-11-06. Al regrabar cambian unos segundos,
porque cada escena dura lo que tarda la aplicación en responder.

| # | Tiempo | Rol | Qué se ve | Franja en pantalla |
|---|---|---|---|---|
| 0 | 0:00 – 0:07 | — | Portada: Rastro, asignatura, grupo, equipo, CUN. «Grabado sobre la pila local con datos sintéticos; el mismo código corre en AWS» | — |
| 1 | 0:07 – 0:27 | Despachador | Entra con su cuenta y llega al panel de Mensajería Andes: en curso, entregados, con incidencia, sin asignar, envíos sin movimiento, los nueve estados | *Entra con su cuenta* · *Panel de la empresa* |
| 2 | 0:27 – 0:52 | Despachador | Nueva orden: tienda de origen, dirección de entrega, peso, destinatario, teléfono, cliente, orden de compra. Al registrar, el detalle muestra el identificador aleatorio (UUID) | *Registra una orden* |
| 3 | 0:52 – 1:01 | Despachador | Asigna el mensajero eligiéndolo de la lista; el histórico pasa de CREADO a ASIGNADO | *Asigna el mensajero* |
| 4 | 1:01 – 1:25 | Conductor (teléfono) | En **Entregas**: marca la guía como recogida, elige tres paradas y sale a ruta. Aparece «Compartiendo su ubicación», el mapa con su posición y las paradas con Llamar, Cómo llegar, Novedad y Entregar | *Recoge la guía y sale a ruta* |
| 5 | 1:25 – 1:46 | Despachador | **Seguimiento**: el conductor en el mapa; al elegir su ruta se dibuja el recorrido y se listan las paradas. La posición avanza mientras se mira | *Seguimiento en vivo* |
| 6 | 1:46 – 2:02 | Destinatario (teléfono) | Consulta pública, sin cuenta: pega el identificador y ve el avance (CREADO → EN REPARTO), «Su envío va en camino» y el vehículo en el mapa. El nombre sale enmascarado | *Consulta su envío* |
| 7 | 2:02 – 2:18 | Conductor (teléfono) | **Entregar**: elige la foto, escribe «Recibió en portería» y confirma. La parada pasa a cerradas | *Entrega con evidencia* |
| 8 | 2:18 – 2:29 | Destinatario (teléfono) | Vuelve a consultar: ENTREGADO, con fecha y hora de cada paso, y ya no se muestra el vehículo | *Entregado* |
| 9 | 2:29 – 2:40 | Despachador de otra empresa | Envíos Sabana abre la guía de Mensajería Andes: «No se pudo abrir el envío. El envío no existe o no pertenece a su organización» | *Aislamiento entre empresas* |
| 10 | 2:40 – 2:56 | Auditor | **Bitácora**: pulsa *Verificar cadena* → «La cadena verifica» y el estado pasa a *íntegra*; debajo, cada registro con actor, acción, resultado (ALLOW/DENY) y hash | *Bitácora encadenada por hash* |
| 11 | 2:56 – 3:07 | Administrador | **Roles y permisos**: los cinco de fábrica y sus operaciones; ninguno combina escritura con lectura de la bitácora | *Roles y permisos* |
| 12 | 3:07 – 3:16 | — | Cierre: 9/9 requisitos, 327 pruebas superadas, despliegue en AWS verificado, 10/11 controles conformes, repositorio y equipo | — |

---

## Voz en off (opcional)

Para leer encima del video, a unas 130 palabras por minuto. Cada bloque cabe en
su escena. Si se graba, se puede montar la voz sobre el MP4 con cualquier
editor (Clipchamp, que viene con Windows, basta) o directamente con ffmpeg:

```bash
ffmpeg -i video-demostrativo-rastro.mp4 -i voz.m4a -map 0:v -map 1:a -c:v copy -c:a aac -shortest video-con-voz.mp4
```

**0 · Portada.** Rastro: trazabilidad verificable de envíos sobre servicios
gestionados en la nube. Lo que sigue es la aplicación real, con datos
sintéticos.

**1 · Acceso y panel.** El despachador entra con su cuenta. Desde aquí, todo lo
que haga queda a su nombre y con su hora. El panel resume la operación de la
empresa: lo que está en curso, lo entregado, lo detenido por una incidencia y lo
que espera mensajero.

**2 · Nueva orden.** Registra una orden: de qué tienda sale, a dónde va, quién la
recibe. Al guardarla, el sistema le asigna un identificador aleatorio, que no se
puede adivinar. Ese identificador es la guía que recibe el destinatario.

**3 · Asignar.** Elige el mensajero. El paso de creado a asignado lo valida la
máquina de estados: un salto no permitido se rechaza y queda registrado.

**4 · Salir a ruta.** En el teléfono, el conductor marca la guía como recogida,
elige sus paradas y sale a ruta. Solo desde ahora, y solo mientras la ruta esté
abierta, comparte su ubicación.

**5 · Seguimiento.** En la oficina, el despachador ve a cada conductor en el
mapa, con su recorrido y sus paradas. Se actualiza solo.

**6 · Consulta pública.** La destinataria no necesita cuenta: pega el
identificador y ve en qué va su envío y dónde está el vehículo. Su nombre
aparece enmascarado.

**7 · Entrega.** Al llegar, el conductor toma la foto y confirma. La foto sube por
un enlace que vence en cinco minutos; en AWS queda cifrada con una llave propia.
Sin evidencia, el servidor no acepta la entrega.

**8 · Entregado.** La destinataria vuelve a consultar: entregado, con la fecha y
la hora de cada paso.

**9 · Aislamiento.** Ahora, otra empresa intenta abrir esa misma guía. El sistema
responde como si no existiera, y el intento queda registrado. Las empresas
comparten la infraestructura, no los datos.

**10 · Bitácora.** El auditor revisa la bitácora: cada operación, permitida o
rechazada, encadenada por hash. Verificar recalcula la cadena completa; si
alguien alterara un registro, se sabría dónde. El auditor puede leer, pero no
escribir nada.

**11 · Roles.** El administrador gestiona los roles. Ninguno combina escribir en
el sistema con leer la bitácora.

**12 · Cierre.** Nueve de nueve requisitos cumplidos, trescientas veintisiete
pruebas superadas, despliegue verificado en AWS y una auditoría independiente.
Rastro.

---

## Lista de tomas, para grabarlo a mano

Por si se prefiere grabar con OBS o con la grabación de pantalla de Windows
(`Win + Alt + R` en la Xbox Game Bar), en lugar de regenerar el automático.

**Preparación**

1. `docker compose up -d` en la raíz y esperar a que `preparar-entorno`
   termine (`docker compose ps`).
2. Las cuentas son las de la semilla: tabla en el
   [README del repositorio](../../../README.md) y en
   [cómo usar cada app](../../despliegue/como-usar-cada-app.md). Se usan la del
   despachador, la de Carlos (conductor), la del auditor y la del
   administrador de Mensajería Andes, y la del despachador de Envíos Sabana.
3. Cada rol en una ventana **privada** distinta: la sesión vive en la pestaña,
   así que dos roles en dos pestañas normales también funcionan, pero en
   ventanas separadas no se confunden al grabar.
4. Para el conductor, las herramientas de desarrollo del navegador en modo
   dispositivo (`F12`, `Ctrl + Shift + M`, 390 × 844) y la ubicación fijada en
   **Sensors** (Bogotá). La ubicación solo funciona en `localhost` o con HTTPS.
5. Ventana del navegador a 1280 × 720 o mayor, zoom al 100 %, sin marcadores ni
   extensiones a la vista.

**Tomas**, en el orden de la tabla de escenas: cada una de 10 a 25 segundos,
con una pausa de dos segundos al empezar y al terminar para poder cortar. La
guía que se crea en la toma 2 es la que se usa en todas las siguientes:
copiarla con el botón **Copiar** del detalle.

---

## Cómo se regenera

Con la pila levantada, desde `presentacion/`:

```bash
npm install --no-save playwright-core@1.56.1 sharp@0.34.3 ffmpeg-static@5.2.0
node anexos/grabar-demo.mjs
```

Tarda unos cinco minutos y sobrescribe el MP4. Cada ejecución crea una orden
nueva en la pila local y cierra al final la ruta del conductor. Detalle en el
[README del módulo `presentacion`](../../modulos/presentacion/README.md#anexos-de-la-entrega-póster-y-video).
