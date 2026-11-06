# ADR-016 · Rastro y Cotejo también en Flet: un código para escritorio, web y Android

Fecha: 2026-10-26 · Estado: aceptada · Afecta a `cliente-flet/` (nuevo),
`deploy/aws/60-sitios.sh` (copia la configuración de ejecución) y, por un fallo
encontrado al portarla, a `web/src/componentes/codigo-barras.tsx`

## Contexto

El equipo pidió (2026-10-23) una versión **adicional** de las dos interfaces en
Flet, con todo lo que hoy funciona, para ejecutarla en **escritorio, web y como
APK de Android**. Las interfaces React (`web/`, `cotejo/web/`) siguen siendo las
publicadas en AWS; esta versión no las sustituye.

Flet escribe la interfaz en Python y la dibuja con Flutter. La versión 1.0.5
(la vigente) trae un modo declarativo —componentes, `use_state`, `use_effect`,
contextos y un enrutador— que se parece a React. Las APIs del servidor no
cambian: los dos clientes hablan con los mismos contratos
([contratos](../api/contratos.md)).

## Decisión

Un proyecto, `cliente-flet/`, con dos aplicaciones y un núcleo común:

```
cliente-flet/src/
├── comun/        diseño, piezas de interfaz, HTTP, configuración, datos
├── rastro_app/   las 14 pantallas de Rastro
├── cotejo_app/   las 4 pantallas de Cotejo
├── rastro.py     entrada de Rastro
└── cotejo.py     entrada de Cotejo
```

### 1. Modo declarativo, pantalla por pantalla

Cada pantalla de React tiene su par en Python con el mismo nombre, las mismas
rutas (`/envios/<id>`, `/rastreo?envio=<id>`…) y los mismos textos. Se eligió el
modo declarativo de Flet 1.0 y no el imperativo (`page.add` y `update()` a mano)
porque permite leer una pantalla junto a su versión web: los mismos estados, los
mismos efectos, el mismo control de acceso por permiso. Lo que en la web hace
React Query aquí lo hace `comun/datos.py` (caché, refresco, invalidación tras
escribir, reintento solo de lo transitorio).

### 2. Dos aplicaciones, no una

Rastro y Cotejo son proyectos distintos y uno audita al otro: se construyen como
**paquetes separados** (`herramientas/construir.py` prepara una copia con solo
el código de cada una). El APK de Cotejo no pide ubicación ni cámara: una
aplicación que audita no debe pedir más permisos de los que usa.

### 3. La configuración sigue fuera del código (REQ-09)

Igual que en la web, la dirección de la API no se escribe en el código. Hay tres
fuentes, por orden: la dirección fijada en el propio dispositivo desde
«Conexión» (para reapuntar un APK instalado sin reconstruirlo), una variable de
entorno (`RASTRO_CONFIGURACION`, `COTEJO_CONFIGURACION`) y el
`configuracion.json` empaquetado, que la etapa `60-sitios.sh` copia junto al de
la web.

### 4. El sistema de diseño se traduce, no se copia (ADR-008)

`comun/fichas.py` lo genera `herramientas/generar_fichas.py` a partir de
`design/tokens.css` y de cada `identidad.css`. Una prueba falla si dejan de
coincidir.

### 5. Lo que en la web resuelve el navegador

| Necesidad | Web | Flet |
|---|---|---|
| Imprimir guías | `@media print` | PDF de 100 × 150 mm compuesto en el dispositivo (`guias_pdf.py`), sin dependencias |
| Mapa | Leaflet + OpenStreetMap (ADR-014) | `flet-map` (flutter_map) con las mismas teselas |
| GPS del modo ruta | `navigator.geolocation` | `flet-geolocator`; en Android, con servicio en primer plano |
| Pantalla encendida | Wake Lock del navegador | `ft.Wakelock` donde no hay servicio en primer plano |
| Elegir la foto | `<input type="file" capture>` | `FilePicker` (galería o cámara), recomprimida al 75 % |
| Sesión | `sessionStorage` (se pierde al cerrar la pestaña) | memoria (se pierde al cerrar la aplicación) |

**La diferencia de fondo está en Android.** El navegador detiene la página con
la pantalla apagada y por eso la web pide mantenerla encendida (ADR-013). La
aplicación instalada pide a Android un servicio en primer plano, con su
notificación permanente, y sigue transmitiendo con la pantalla apagada mientras
la ruta esté abierta. La notificación no es decorativa: compartir la ubicación
de una persona es algo que esa persona tiene que ver que está pasando.

### 6. La web de Flet la sirve un proceso de Python

`flet build web` produce un sitio estático que ejecuta Python en el navegador
(Pyodide), donde `httpx` no puede abrir conexiones. Por eso la variante web se
sirve con el proceso de Python (`flet run --web`, o el mismo programa con
`FLET_FORCE_WEB_SERVER=true`): el navegador dibuja y el servidor ejecuta la
lógica. Cada pestaña es una sesión aparte; por eso **nada de la sesión vive en
variables de módulo**.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Una sola aplicación con Rastro y Cotejo dentro | Juntaría al auditor con lo auditado en el mismo paquete y con los mismos permisos |
| Modo imperativo de Flet | Más código por pantalla y ninguna correspondencia con la versión web; cada cambio de estado exige recordar qué `update()` llamar |
| `flet build web` estático | `httpx` no funciona en Pyodide; habría que escribir otro cliente HTTP solo para esa variante |
| Generar el PDF con una biblioteca (reportlab, fpdf) | Una dependencia más en el APK por lo que caben 200 líneas propias, en un proyecto que se audita a sí mismo |
| Guardar la sesión en el dispositivo para no volver a entrar | En un teléfono que comparten varios mensajeros, quien lo tome después entraría con la cuenta del anterior. La ruta abierta no se pierde: vive en el servidor |
| `CameraFit` de `flutter_map` para encuadrar el mapa | Con él no se dibujaban las teselas en el cliente de Flet; el encuadre se calcula con Mercator (`mapa.encuadrar`) |

## Consecuencias

- **Dos interfaces que mantener.** Un cambio de pantalla se hace dos veces. Lo
  compensan los contratos compartidos, las pruebas de `cliente-flet/tests` (que
  repiten las reglas de la web: renovación de sesión única, transmisión,
  lote, guías) y que los textos y decisiones estén escritos igual en las dos.
- **Portarla encontró un fallo en la web.** La tabla del código de barras traía
  dos patrones inexistentes en Code 128 y corría todos los valores desde el 83,
  incluido el inicio B: las guías impresas no las leía un lector. Se corrigió en
  las dos versiones y quedó una prueba con valores de la norma
  (`test_codigo_barras.py`). El sitio de AWS tiene el fallo hasta el siguiente
  despliegue de `60-sitios.sh`.
- **La web de Flet no se publica en AWS.** Necesita un proceso vivo; en el
  laboratorio eso sería otra pieza de cómputo encendida (ADR-001). Se ejecuta en
  local o en el equipo de quien presenta.
- **El APK sale firmado con la clave de depuración** de Flutter: sirve para
  instalarlo en un teléfono de prueba, no para publicarlo en una tienda.
- **Pendiente de verificar en un teléfono real**: la transmisión con la pantalla
  apagada (servicio en primer plano) y la cámara al elegir la foto. En escritorio
  y en el navegador integrado de pruebas no hay GPS: allí el modo ruta muestra
  «ubicación bloqueada», que es lo correcto.
