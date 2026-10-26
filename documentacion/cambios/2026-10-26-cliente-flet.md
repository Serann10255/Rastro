# Cambios · 2026-10-26 · Rastro y Cotejo también en Flet

Pedido del equipo (2026-10-23): una versión **adicional** de las dos interfaces
en Flet, con todo lo que hoy funciona, para escritorio, web y APK de Android.
Las interfaces React siguen siendo las publicadas; esta no las sustituye.

Documentación del módulo: [cliente-flet](../modulos/cliente-flet/README.md).
Decisión: [ADR-016](../decisiones/adr-016-cliente-flet.md). Cómo ejecutarlo y
construirlo: [despliegue del cliente Flet](../despliegue/cliente-flet.md).

---

## Qué se añadió

**`cliente-flet/`** (proyecto nuevo, Python 3.11+ y Flet 1.0.5)

- `src/comun/` — lo que comparten las dos aplicaciones: configuración en
  ejecución (REQ-09), cliente HTTP con errores tipados, consultas con caché e
  invalidación, formularios, piezas de interfaz, tema y colores generados del
  sistema de diseño, logotipos y formato de fechas.
- `src/rastro_app/` — las 14 pantallas de Rastro con las rutas de la web,
  incluidos el registro en lote desde CSV, las guías en PDF, el modo ruta con
  transmisión de la ubicación (servicio en primer plano en Android), el
  seguimiento en mapa y la consulta pública.
- `src/cotejo_app/` — la consola del auditor: revisión, catálogo, repetición y
  diccionario.
- `herramientas/` — `generar_fichas.py` (colores desde `design/`),
  `generar_iconos.py` (iconos de los paquetes) y `construir.py` (APK, Windows o
  web de cada aplicación por separado).
- `tests/` — 44 pruebas.
- `pyproject.toml` — dependencias fijadas y permisos de Android.

**Despliegue**

- `deploy/aws/60-sitios.sh` copia los `configuracion.json` de la web a
  `cliente-flet/src/assets/`, para que un paquete construido después de un
  despliegue apunte a esa cuenta.
- `.gitignore`: `cliente-flet/build/` y `cliente-flet/salida/`.

## Qué se corrigió en la web

- **`web/src/componentes/codigo-barras.tsx`**: la tabla de Code 128 traía dos
  patrones que no existen en la norma («141142» y «141241», de trece módulos en
  vez de once) en la posición 83. Corrían todos los valores siguientes, incluido
  el código de inicio B, de modo que **ninguna guía impresa se podía leer con un
  lector**. Se encontró al portar el codificador a Python y escribirle una
  prueba con valores de referencia. Se corrigió en las dos versiones.
  - Verificado: `tsc --noEmit` sin errores; la tabla queda con 106 patrones de
    once módulos y el inicio B en `211214`.
  - **Publicado en AWS** el mismo día con `deploy/aws/60-sitios.sh` (misma
    cuenta y misma API que el despliegue del 2026-10-16; Cotejo no se volvió a
    publicar porque no cambió). La tabla extraída del paquete que sirve el sitio
    tiene los 106 patrones de once módulos más el de parada, el inicio B en la
    posición 104, y coincide con la de Python. La entrada HTTPS sirve el mismo
    paquete. En los `configuracion.json` solo cambió la fecha `generado_en`.
  - La pila local conserva la tabla vieja hasta `docker compose build web`.

## Qué se probó

- `cliente-flet/tests`: 44 pruebas, todas pasan.
- Recorrido en modo web contra la pila local, a 1280 × 800 y a 360 × 780:
  acceso; panel de administrador, conductor y auditor; órdenes con selección,
  barra fija y guías; registro de un envío sintético con tienda, asignación y
  punto de control «Recolectado»; operaciones; seguimiento con recorrido;
  administración, edición de una cuenta y roles; tiendas; bitácora con
  verificación de la cadena; modo ruta y diálogo de entrega; consulta pública
  con enlace directo. Cotejo: revisión, papel de trabajo, verificación del
  almacén, comparación, catálogo y diccionario.
- Escritorio: la ventana de Windows arranca y muestra el acceso.
- **APK de Rastro** (`cliente-flet/salida/rastro-apk/rastro.apk`, 143 MB, firma
  de depuración) en el emulador de Android Studio (Android 16, 1080 × 2400):
  instala, abre en el acceso con la conexión a la API de AWS, y la consulta
  pública con un identificador inventado llega a AWS por HTTPS y responde «No
  encontramos un envío con ese identificador». Con sesión no se probó: en AWS
  entra el equipo, no el asistente.
- **APK de Cotejo** (`cliente-flet/salida/cotejo-apk/cotejo.apk`, 143 MB) en el
  mismo emulador: solo pide Internet y estado de la red (ningún permiso de
  ubicación ni de cámara), y el acceso muestra, leído de la API de Cotejo en
  AWS, que revisa la API de Rastro y tiene 11 controles por comprobar. El
  primer arranque deja la pantalla en blanco unos 30 segundos mientras
  desempaqueta Python; los siguientes son inmediatos.

## Cómo se llegó al APK

- La primera compilación instaló Flutter 3.44.8, el JDK 17 y los paquetes del
  SDK de Android que faltaban. Al instalar esos paquetes, el instalador de Flet
  aceptó por su cuenta siete licencias adicionales del SDK (Google TV, XR, ARM
  DBT, preview, GDK, MicroXR y MIPS); la licencia principal ya estaba aceptada
  desde Android Studio, y el equipo aprobó seguir con ellas. Desde entonces
  `construir.py` no pasa `--yes` y fuerza UTF-8 (la consola en cp1252 se caía).
- La segunda se detuvo porque Flutter, en Windows, necesita el **Modo de
  desarrollador** para los enlaces simbólicos de los plugins. Lo activó el
  equipo.
- Gradle instaló además el NDK 28.2 y CMake 3.22.1.
- La de Cotejo falló una vez por un corte de red (no resolvía `github.com`
  mientras descargaba el intérprete de Python) y otra porque el demonio de
  Gradle de ese intento seguía usando la carpeta. Los demonios de Gradle y de
  Kotlin quedan vivos horas después de cada construcción de Android y en
  Windows no dejan borrar `build/<app>`, así que `construir.py` ahora los
  detiene al terminar y, si aun así no puede borrar la carpeta, lo explica en
  vez de mostrar la traza. Los dos casos quedaron en la tabla de problemas de
  la [guía](../despliegue/cliente-flet.md).

## Qué queda pendiente

- En un teléfono real: la transmisión con la pantalla apagada y la cámara al
  elegir la foto. El navegador integrado de pruebas y el escritorio no entregan
  GPS.
- La descarga de archivos (exportación CSV, plantilla del lote, PDF de guías,
  informe de Cotejo) no se probó desde el navegador; el PDF se validó aparte
  con un visor y con pruebas.
