# Cambios · 2026-10-26 · Presentación a la universidad, plan de la cuenta nueva y comprobación general

El proyecto fue seleccionado para presentarse ante toda la universidad, y la
universidad va a asignar una cuenta de AWS para dejar la aplicación completa.
Trabajo hecho entre el 2026-10-23 y el 2026-10-26.

## 1. Un deck para público general

Las sustentaciones hablan al jurado de la materia: controles, normas, roles de
IAM. Para la comunidad universitaria se escribió un guion aparte con el mismo
motor de diapositivas:
[`presentacion-universidad.md`](../sustentacion/presentacion-universidad.md),
servido en `/universidad`. Once láminas, ≈ 5 min 40 s de guion hablado más unos
dos minutos de demostración en vivo del modo ruta. Lo técnico pasó a «Si
preguntan». Reparto y lista de comprobación en el
[README de los guiones](../sustentacion/README.md#presentación-a-la-universidad-2026-10-26).

| Archivo | Qué cambió |
|---|---|
| `documentacion/sustentacion/presentacion-universidad.md` | El guion: contenido, guion hablado, indicaciones y respuestas preparadas |
| `presentacion/universidad/index.html`, `src/entradas/universidad.tsx` | La página nueva, con la identidad de Rastro |
| `presentacion/vite.config.ts` | Tercera entrada y redirección `/universidad` → `/universidad/` |
| `presentacion/src/entradas/inicio.tsx`, `src/Inicio.tsx` | El índice muestra los tres decks y se titula «Presentaciones» |
| `presentacion/src/figuras/` | Cinco figuras nuevas: `informacion-repartida`, `viaje-del-paquete`, `demo-en-vivo`, `pago-por-uso`, `cadena-de-registros` |
| `presentacion/src/deck/piezas-svg.tsx`, `src/estilos/presentacion.css` | Variantes de caja `exito` y `peligro`, celdas de la figura de pago por uso y eslabones de la cadena |
| `presentacion/capturas/capturar.mjs` | Parte nueva del modo ruta y opción `--solo=` |
| `presentacion/capturas/` | Tres capturas nuevas: `rastro-seguimiento`, `rastro-modo-ruta`, `rastro-rastreo-en-camino` |
| `presentacion/exportar-pdf.mjs` | Exporta también el deck nuevo; opción `--solo=`; los nombres de archivo de las sustentaciones no cambian |
| `presentacion/compilador/sustentacion.test.ts` | Prueba del guion nuevo, sin la regla de los siete bloques |
| `documentacion/entregables/sustentacion/` | `Rastro · presentación a la universidad.pdf` (11 láminas) y su `guion.pdf` |

### Capturas del modo ruta

No había capturas del modo ruta a resolución de diapositiva (las del módulo de
rutas son de 576 px). Se añadió a `capturar.mjs` una parte que abre una ruta
por la API con treinta posiciones por Chapinero y captura Seguimiento, el modo
ruta del conductor y la consulta pública. Dos tropiezos, ya resueltos:

- **La imagen `web` del equipo era anterior al modo ruta** (2026-10-16, 09:37)
  y no tenía `/entregas` ni `/seguimiento`. Se reconstruyó solo esa imagen.
- **El primer recorrido salió en zigzag.** Las posiciones se reportaban con
  horas futuras; el servidor las recorta al presente, todas quedaban con la
  misma hora y el recorrido, que se ordena por hora, unía los puntos en
  cualquier orden. Ahora el guion espera el tiempo real del recorrido y reparte
  las horas entre el inicio y ese momento.

### Una contradicción evitada

La captura de la revisión de Cotejo es de la pila local y dice «6 bien, 1 mal,
4 sin revisar»; la lámina 9 da las cifras de la revisión en AWS (10 conformes,
1 desviado). Ante público general, dos cifras distintas en la misma lámina
parecen un error, así que la lámina usa solo la pantalla de hallazgos, que no
lleva recuento y además explica en lenguaje llano por qué el rol compartido es
un problema: justo lo que arregla la cuenta nueva.

## 2. Plan para la cuenta de la universidad

[`plan-cuenta-universidad.md`](../despliegue/plan-cuenta-universidad.md): cómo
saber qué tipo de cuenta es, qué restricciones del laboratorio desaparecen y
qué cierra cada una, la migración paso a paso con `migrar.sh` (que es el
simulacro pendiente de REQ-09), el rol de ejecución que hará falta si no existe
`LabRole`, y el análisis de RDS.

**RDS queda como decisión del equipo.** Rastro ya tiene base de datos
(DynamoDB) y está completa sin RDS; añadirlo trae un cargo por hora, red
privada y, si se migrara todo, reescribir la capa de datos. Si es un requisito,
el plan recomienda RDS solo para informes, alimentado desde DynamoDB, que no
pone en riesgo la operación.

`.gitignore` excluye ahora `migracion/`, donde `migrar.sh exportar` deja los
envíos, la bitácora y las evidencias de la cuenta que se abandona.

## Comprobado

- `npm test` en `presentacion/`: 26 pruebas, 0 fallos; los tres guiones
  compilan sin avisos. `npm run typecheck` sin errores.
- Con Edge sin interfaz a 1440 × 900, el guion de los tres decks dice
  «Ninguna se desborda».
- `/universidad` y el índice a 360 px: `scrollWidth` = 360, sin scroll
  horizontal.
- Revisadas las once láminas a 1920 × 1080; los puntos de la galería ya no
  tapan la última caja de la cadena de registros.
- `npm run pdf -- --solo=universidad`: 11 páginas en los dos formatos.
- `docker compose build presentacion` termina sin errores y compila los tres
  guiones (11, 9 y 10 diapositivas): se puede presentar sin Node en el equipo.
- Suite de Python del repositorio el 2026-10-23: 327 superadas, 5 omitidas.

## No comprobado

- **La demostración en vivo** contra AWS: necesita el laboratorio abierto, un
  teléfono con GPS y el auditorio. Las cuentas con contraseña del sitio de AWS
  las recorre el equipo.
- **El plan de la cuenta** no se ha ejecutado: no hay cuenta todavía.

## 3. RDS en espera y comprobación del resto

El equipo decidió **no hacer nada con RDS** hasta que el docente entregue una
cuenta que permita configurarlo, y comprobar mientras tanto que lo demás
funciona. El plan de la cuenta lo dice en su sección 5.

**Suite de pruebas** (26/10): 327 superadas y 5 omitidas, que son omisiones
esperadas (cuatro módulos apagados y el adaptador de Lambda, que solo viaja en
el paquete).

**Pila local con imágenes reconstruidas el 26/10.** Las de los servicios y las
de Cotejo eran del 16/10, anteriores al último cambio de Cotejo (C-09 en AWS).
Recorrido automático por la API con los usuarios de la semilla: **40 de 40
comprobaciones**. En la primera pasada salieron 39: la que faltaba mandaba un
cuerpo inválido y recibía 422 en lugar de 403. Era un error de la prueba;
repetida con un cuerpo válido, pasa (véase la observación de abajo).

| Qué se comprobó | Resultado |
|---|---|
| Las tres interfaces, la puerta de enlace y la API de Cotejo responden | ✓ |
| Registrar, asignar, recoger; un salto a `ENTREGADO` se rechaza | ✓ |
| Salir a ruta (a `EN_REPARTO` por el flujo principal) y reportar posición | ✓ |
| El administrador ve la ruta; el auditor no ve ubicaciones (403) | ✓ |
| Consulta pública sin cuenta, nombre enmascarado, vehículo en el mapa; identificador no canónico, 422 | ✓ |
| Sin evidencia no se entrega; foto subida directo al almacenamiento, confirmada y entregada | ✓ |
| El conductor no descarga la evidencia; el despachador sí | ✓ |
| La ruta se cierra como `completada` y la ubicación deja de mostrarse | ✓ |
| Otra empresa recibe 404; el auditor y el conductor no crean envíos (403); el administrador no lee la bitácora (403); sin token, 401 | ✓ |
| La cadena de la bitácora verifica (496 registros) | ✓ |
| Cotejo desde su API: C-04 a C-08 conformes; un despachador recibe 403 | ✓ |
| Cotejo desde el equipo, con `git`: C-09a y C-09c conformes, C-09b desviado (H-01, conocido) | ✓ como se esperaba |

C-01 a C-03 solo se pueden revisar contra AWS, y C-09 no se ejecuta dentro del
contenedor local porque ahí no hay `git`. En AWS sí corre: la función de
Cotejo lleva `git`.

Una observación menor: con un cuerpo inválido, `POST /envios` responde 422
antes de comprobar el permiso, incluso a quien no puede crear envíos. Con un
cuerpo válido responde 403, como debe ser. Es el orden de FastAPI (valida la
petición antes de ejecutar la función) y no expone datos, solo la forma del
formulario.

**AWS, el 26/10, con el laboratorio cerrado:** los dos sitios cargan (200) y las
dos API responden 500. Es la RE-06 de siempre y no un fallo nuevo; las
credenciales de la CLI también vencieron. Para verificar el despliegue hay que
abrir el laboratorio y ejecutar `deploy/aws/95-verificar.sh`.

**El cliente en Flet** no se comprobó: la otra sesión lo sigue construyendo.

`documentacion/api/contratos.md`: el contrato de `POST /envios/{id}/evidencias`
no decía qué lleva la petición; ahora dice que `nombre_archivo` es obligatorio
y qué tipos admite.

## A tener en cuenta

- Otra sesión está construyendo el cliente en Flet (`cliente-flet/`). Este
  cambio no toca sus archivos; el plan de la cuenta describe cómo lee su
  configuración y qué hacer con ella al migrar.
