# Cliente Flet: ejecutar y construir (escritorio, web y Android)

Fecha: 2026-10-26 · Módulo: [cliente-flet](../modulos/cliente-flet/README.md) ·
Decisión: [ADR-016](../decisiones/adr-016-cliente-flet.md)

Todo se ejecuta desde la raíz del repositorio. Las órdenes son de Git Bash en
Windows; en PowerShell cambian las barras y la forma de poner variables.

## 1. Preparar el entorno

```bash
py -3.14 -m venv cliente-flet/.venv
cliente-flet/.venv/Scripts/python -m pip install "flet[all]==1.0.5" "flet-map==1.0.5" "flet-geolocator==1.0.5" "httpx==0.28.1" pytest
```

La primera vez que se abre en escritorio, Flet descarga su cliente (unos
40 MB) a `~/.flet/client`.

## 2. A qué API se conecta

Por omisión, al `configuracion.json` empaquetado en `cliente-flet/src/assets/`,
que apunta al despliegue de AWS (lo copia `deploy/aws/60-sitios.sh`). Con el
laboratorio cerrado, AWS responde 500. Para la pila local, un archivo propio y
la variable de entorno:

```bash
printf '{"entorno": "local", "region": "us-east-1", "url_publica_api": "http://localhost:8080"}\n' > /tmp/rastro-local.json
printf '{"entorno": "local", "url_cotejo": "http://localhost:8007", "url_rastro": "http://localhost:8080"}\n' > /tmp/cotejo-local.json
```

`RASTRO_CONFIGURACION` y `COTEJO_CONFIGURACION` aceptan una ruta o una URL. En
un teléfono no hay variables de entorno: allí se usa **Conexión**, en la
pantalla de acceso, que comprueba la dirección antes de guardarla en el
dispositivo.

## 3. Escritorio

```bash
cd cliente-flet/src && RASTRO_CONFIGURACION=/tmp/rastro-local.json ../.venv/Scripts/python rastro.py
```

```bash
cd cliente-flet/src && COTEJO_CONFIGURACION=/tmp/cotejo-local.json ../.venv/Scripts/python cotejo.py
```

## 4. Web

Flet sirve la interfaz y ejecuta la lógica en el proceso de Python (ADR-016,
punto 6). Con recarga al guardar y apertura del navegador:

```bash
cd cliente-flet/src && RASTRO_CONFIGURACION=/tmp/rastro-local.json ../.venv/Scripts/flet run --web --port 8552 rastro.py
```

Sin abrir el navegador (por ejemplo, en un servidor):

```bash
cd cliente-flet/src && FLET_FORCE_WEB_SERVER=true FLET_SERVER_PORT=8552 RASTRO_CONFIGURACION=/tmp/rastro-local.json ../.venv/Scripts/python rastro.py
```

Después de reiniciar el proceso, una pestaña que ya estaba abierta puede quedar
en blanco: se abre una nueva. La sesión vive en el proceso, así que reiniciarlo
obliga a volver a entrar.

## 5. Android (APK)

### Requisitos

- Unos 3 GB libres y conexión estable la primera vez. `flet build` instala por
  su cuenta **Flutter 3.44.8** (en `~/flutter`), un **JDK 17** (en `~/java`) y
  los componentes que falten del **SDK de Android** (en
  `%LOCALAPPDATA%\Android\Sdk`); Gradle añade después el **NDK 28.2** y
  **CMake 3.22.1**, y descarga de GitHub el intérprete de Python para Android.
  La primera compilación tarda unos 25 minutos; las siguientes, unos 10.
- **Modo de desarrollador de Windows activado** (*Configuración → Privacidad y
  seguridad → Para desarrolladores*), o la compilación lanzada desde una terminal
  de administrador. Flutter crea enlaces simbólicos para los plugins (mapa, GPS)
  y sin ese permiso se detiene con «Building with plugins requires symlink
  support».
- **Licencias del SDK de Android aceptadas.** Las acepta quien construye, una
  vez por equipo. Con Android Studio: *SDK Manager → SDK Tools*, o en una
  terminal:

  ```bash
  "$LOCALAPPDATA/Android/Sdk/cmdline-tools/latest/bin/sdkmanager.bat" --licenses
  ```

  Cuando `flet build` instala un paquete del SDK que falta, **acepta por su
  cuenta todas las licencias** que presente `sdkmanager --licenses`. Por eso
  conviene aceptarlas antes y a mano, leyéndolas, o instalar los paquetes
  `platforms;android-35` y `build-tools;34.0.0` desde Android Studio.
  `construir.py` no pasa `--yes`; se le puede añadir si se quiere que el
  instalador conteste solo.

### Construir

```bash
cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py rastro apk --no-rich-output
```

```bash
cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py cotejo apk --no-rich-output
```

`construir.py` ejecuta `flet build` en UTF-8: con la consola de Windows en
cp1252 el instalador del SDK se caía al imprimir sus textos. El resultado queda en
`cliente-flet/salida/<app>-apk/`. `construir.py` prepara antes una copia en
`cliente-flet/build/<app>/` con solo el código, el icono y la configuración de
esa aplicación; las dos carpetas están en `.gitignore`.

### Instalar en un teléfono

Con el teléfono en modo desarrollador y conectado por USB:

```bash
"$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" install -r cliente-flet/salida/rastro-apk/rastro.apk
```

O copiar el `.apk` al teléfono y abrirlo, permitiendo «instalar aplicaciones de
origen desconocido».

### Lo que hay que saber del APK

- **Tamaño.** Unos 143 MB, porque lleva Python y Flutter para tres
  arquitecturas (arm64-v8a, armeabi-v7a y x86_64, de 38 a 48 MB cada una). Un
  teléfono usa solo una. Para repartir APK más pequeños, uno por arquitectura:
  `construir.py rastro apk --split-per-abi`, o solo la de los teléfonos
  actuales: `--arch arm64-v8a`. El x86_64 es el que usa el emulador.
- **Primer arranque.** La pantalla queda en blanco unos 30 segundos mientras la
  aplicación desempaqueta Python; no es un fallo. Los siguientes arranques son
  inmediatos.
- **Firma de depuración.** Sirve para instalarlo en teléfonos de prueba, no para
  una tienda. Para publicarlo hace falta un almacén de claves propio
  (`--android-signing-key-store` y su clave), que no se versiona.
- **HTTPS.** Android no permite tráfico en claro por omisión: el APK habla con
  la API de AWS (HTTPS). Contra la pila local habría que exponerla con HTTPS.
- **Permisos.** Rastro pide ubicación precisa, servicio en primer plano de
  ubicación, notificaciones, mantener la CPU despierta y cámara
  (`pyproject.toml`). Cotejo no pide ninguno.
- **Modo ruta con la pantalla apagada.** Mientras la ruta está abierta, Android
  muestra la notificación «Rastro: ruta en curso» y la ubicación se sigue
  enviando. Al terminar la ruta, la notificación desaparece.

## 6. Windows (ejecutable)

```bash
cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py rastro windows --no-rich-output
```

```bash
cliente-flet/.venv/Scripts/python cliente-flet/herramientas/construir.py cotejo windows --no-rich-output
```

Requiere Visual Studio (o sus Build Tools) con la carga de trabajo «Desarrollo
para el escritorio con C++», que `flet build windows` comprueba antes de
empezar, y el Modo de desarrollador (sección 5).

El resultado es una **carpeta**, no un instalador: `cliente-flet/salida/<app>-windows/`,
de unos 95 MB, con `<app>.exe`, Python y las bibliotecas de Flutter. El `.exe`
no funciona separado de ella. Para llevarlo a otro equipo se comprime la carpeta
entera en un `.zip`; allí no hace falta tener Python.

- El ejecutable no está firmado: la primera vez Windows muestra «Windows
  protegió su PC»; se abre con *Más información → Ejecutar de todas formas*.
- Sigue el tema claro u oscuro de Windows, y apunta a la API del
  `configuracion-<app>.json` empaquetado (se cambia desde **Conexión**).
- El modo ruta no sirve en escritorio: el equipo no entrega GPS.

## 7. iPhone (iOS)

iOS no instala APK. Hay tres caminos, de más práctico a más costoso:

1. **La web en Safari.** Rastro y Cotejo están publicados por HTTPS (las
   direcciones están en `config/.sitio.env` y `config/.cotejo.env`, variables
   `URL_SITIO*`). *Compartir → Agregar a pantalla de inicio* deja un ícono. El
   modo ruta funciona con la pantalla encendida (la web la mantiene despierta);
   iOS no deja enviar la ubicación con la pantalla apagada o Safari en segundo
   plano.
2. **La aplicación Flet de la App Store**, solo para mostrarlo. En el PC:

   ```bash
   cd cliente-flet/src && ../.venv/Scripts/flet run --ios rastro.py
   ```

   La terminal muestra `App is running on: http://<IP-del-PC>:8551` y un QR.
   Se escanea con la cámara del iPhone (abre la aplicación Flet), o se escribe
   esa dirección en la aplicación. **No se escribe la de AWS**: Python se
   ejecuta en el PC, el iPhone solo muestra la interfaz, y es el PC el que
   habla con AWS. Hace falta que los dos estén en la misma red (las redes de
   universidades suelen aislar los equipos; el punto de acceso del teléfono
   sirve), que el firewall de Windows deje entrar a Python en redes privadas, y
   que la terminal siga abierta. Esa aplicación genérica puede no traer las
   extensiones de mapa y GPS.
3. **Aplicación nativa** con `flet build ipa`: exige un Mac con Xcode (no se
   compila desde Windows) y una cuenta de Apple Developer para firmarla y
   repartirla por TestFlight. Con un Apple ID gratuito se instala desde Xcode en
   un iPhone propio, y deja de abrir a los siete días.

## 8. Pruebas

```bash
cliente-flet/.venv/Scripts/python -m pytest cliente-flet/tests
```

## Problemas frecuentes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| «Sin conexión» al entrar | La pila local no está levantada, o la configuración apunta a AWS con el laboratorio cerrado | `docker compose up -d`, o `RASTRO_CONFIGURACION` |
| 502 al entrar justo después de `docker compose up` | Los servicios se están recreando | Esperar unos segundos y reintentar |
| Pestaña en blanco en el modo web | El proceso se reinició y la pestaña conserva la conexión vieja | Abrir una pestaña nueva |
| «Ubicación bloqueada» en el modo ruta | El navegador o el escritorio no entregan GPS | Probar el modo ruta en el teléfono (APK o navegador del teléfono por HTTPS) |
| `UnicodeEncodeError: 'charmap'` al construir | La consola de Windows no puede imprimir un carácter del instalador | Construir con `construir.py` (ya fija UTF-8) o con `PYTHONUTF8=1` |
| «Building with plugins requires symlink support» | Windows no deja crear enlaces simbólicos sin el Modo de desarrollador | Activarlo (sección 5) o compilar desde una terminal de administrador |
| `flet build` se detiene en las licencias del SDK | No están aceptadas en este equipo | `sdkmanager --licenses` (sección 5) |
| `UnknownHostException: github.com` en `downloadDistArchive` | Se cortó la red mientras Gradle descargaba el intérprete de Python | Comprobar la conexión y volver a construir |
| «No se pudo borrar cliente-flet/build/<app>» al empezar | Otro proceso tiene abierta la carpeta. `construir.py` ya reintenta cuando es el antivirus o el indexador (dura segundos) y detiene Gradle al terminar cada construcción de Android; queda el caso de un demonio de Gradle de una construcción interrumpida | Cerrar los `java.exe` de `~/java` en el Administrador de tareas y repetir |
