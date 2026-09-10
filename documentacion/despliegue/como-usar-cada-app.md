# Cómo se usa cada aplicación

Fecha: 2026-09-10 · Versión: 0.3

El repositorio contiene **cuatro aplicaciones** con usuarios distintos. Esta
guía dice qué hace cada una, cómo se levanta y cómo se usa, tanto en el entorno
local como desplegada en AWS.

| Aplicación | Local | En AWS | Quién la usa |
|---|---|---|---|
| **Rastro — interfaz de operación** | http://localhost:5173 | Sitio estático en S3 | Despachador, conductor, auditor, administrador |
| **Rastro — consulta pública** | http://localhost:5173/rastreo | La misma, ruta `/rastreo` | Destinatario, **sin cuenta** |
| **Rastro — API** | http://localhost:8080 | API Gateway | Las interfaces; también auditable con `curl` |
| **Cotejo — interfaz de auditoría** | http://localhost:5175 | En la máquina del auditor | Solo el rol auditor |

---

## Local y AWS: se complementan, no se pisan

Es la propiedad más importante del montaje y conviene entenderla antes de nada.

**El mismo código corre en los dos sitios.** Lo que cambia es dónde está cada
pieza y de dónde salen los identificadores.

| Pieza | Local | En AWS |
|---|---|---|
| Puerta de enlace | nginx (`gateway/`) | API Gateway |
| Los ocho servicios | Un contenedor cada uno | Una función Lambda cada uno |
| Datos | DynamoDB Local | DynamoDB |
| Evidencias | MinIO, **sin cifrado KMS** | S3 + KMS |
| Identidad | Microservicio `auth` | El mismo servicio `auth`, desplegado como función |
| Registro de actividad | **No existe** | CloudTrail |
| Interfaces | Contenedor nginx | Sitio estático en S3 |

### Por qué no se pisan

**Ningún identificador de cuenta está escrito en el código.** Cada entorno
declara los suyos en su propio sitio:

- En local, las variables de `docker-compose.yml` y
  `web/public/configuracion.json` con `"entorno": "local"`.
- En AWS, `config/deployment.json` y el `configuracion.json` que escribe la
  etapa `60-sitios.sh`, ambos generados por la secuencia de despliegue.

`config/deployment.json` **está en `.gitignore`**: se genera al desplegar y no se
versiona. Si no existe, todo cae al valor local por omisión. Por eso trabajar en
local nunca depende de haber desplegado, y desplegar no rompe el entorno local.

**El bundle de las interfaces no contiene ninguna dirección.** La configuración
se lee en tiempo de ejecución. Un mismo `dist/` compilado sirve para local y para
AWS: lo único que cambia es el `configuracion.json` que se publica junto a él.

**Los puertos locales no chocan con nada de AWS**, porque en AWS no hay puertos:
hay direcciones HTTPS que asigna el proveedor.

### Qué NO se puede comprobar en local

Se declara en lugar de disimularse:

- Cifrado de evidencias con llave administrada (no hay KMS).
- Registro de actividad sobre la infraestructura (no hay CloudTrail).
- Bloqueo de acceso público del contenedor (el almacenamiento local no
  implementa esa operación).

Cotejo marca esos tres controles como **no ejecutados** cuando corre en local, y
lo dice en el informe. Simular un control equivaldría a no verificarlo.

---

## 1. Rastro — interfaz de operación

### Levantar en local

```bash
docker compose up -d
```

Abre http://localhost:5173. La primera vez, el contenedor `preparar-entorno`
crea las tres tablas, deriva las contraseñas, siembra los datos maestros y
genera veinte envíos con recorridos variados. Tarda algo más que los siguientes
arranques.

### Cuentas de la instalación local

Diez cuentas repartidas en dos empresas. **Las contraseñas se almacenan
derivadas con PBKDF2**; estas son las de la semilla de desarrollo y deben
cambiarse antes de cualquier despliegue con datos reales.

**Mensajería Andes S.A.S.** (`org-andes`, Bogotá)

| Correo | Clave | Rol | Nombre |
|---|---|---|---|
| `admin@andes.test` | `Andes.Admin.2026` | administrador | Ana Duarte Salcedo |
| `despacho@andes.test` | `Andes.Despacho.2026` | despachador | Diego Rojas Mena |
| `coordinacion@andes.test` | `Andes.Coord.2026` | coordinador | Paula Restrepo Vega |
| `carlos@andes.test` | `Andes.Carlos.2026` | conductor | Carlos Nieto Pardo |
| `camila@andes.test` | `Andes.Camila.2026` | conductor | Camila Ortiz Bravo |
| `auditor@andes.test` | `Andes.Auditor.2026` | auditor | Alicia Peña Cardona |

**Envíos Sabana Ltda.** (`org-sabana`, Chía)

| Correo | Clave | Rol | Nombre |
|---|---|---|---|
| `admin@sabana.test` | `Sabana.Admin.2026` | administrador | Mauricio Lemus Rico |
| `despacho@sabana.test` | `Sabana.Despacho.2026` | despachador | Sofía Lemus Rico |
| `santiago@sabana.test` | `Sabana.Santiago.2026` | conductor | Santiago Bravo Niño |
| `auditor@sabana.test` | `Sabana.Auditor.2026` | auditor | Sara Gil Montero |

> **La pantalla de acceso no las muestra.** Antes las listaba con un botón para
> rellenarlas; era cómodo y era exactamente lo que un sistema real no debe
> hacer: publicar usuarios válidos en la única pantalla abierta a cualquiera.
> Están aquí, que es donde corresponde.

`coordinacion@andes.test` usa el rol **coordinador**: más que un despachador
—autoriza envíos detenidos y mantiene catálogos— y menos que un administrador
—no toca cuentas ni roles—. Antes tenía `despachador + administrador`, que en la
práctica era poder de administrador porque no existía nada intermedio.

### Recorrido como despachador

1. **Panel** — el tablero de la empresa: totales, tasa de entrega, los nueve
   estados con su código, la serie de los últimos treinta días y las tres listas
   sobre las que hay que actuar hoy (sin asignar, con incidencia, estancados).
2. **Órdenes** — el listado, con búsqueda por destinatario, orden de compra o
   identificador, y filtro por estado. Cada fila muestra el código y el nombre
   del estado.
3. **Nueva orden** — registro individual, o **carga masiva desde CSV**: se pega
   o se sube el archivo, la pantalla muestra qué filas se aceptan y cuáles no
   **antes** de enviar nada, y el servidor registra las válidas aunque alguna
   falle. La respuesta dice el índice y el motivo de cada rechazo.
4. **Generar guías** — marcar varias órdenes en el listado y pulsar *Guías*
   abre la pantalla de impresión con una etiqueta por envío: código de barras
   Code 128, destinatario, dirección, bultos y peso. Se imprime desde el
   navegador (`Ctrl/Cmd + P`); el salto de página entre etiquetas ya está
   fijado. **La guía no lleva el valor declarado**, a propósito: va pegada a la
   caja.
5. **Exportar** — descarga el CSV de la operación, con el código de estado
   además del nombre, para abrirlo en una hoja de cálculo o entregarlo a un
   sistema que no habla español.
6. **Asignar mensajero** — desde el detalle. Los conductores **activos** de la
   empresa aparecen como opciones, tomados del directorio: no hay que saberse su
   identificador, y un mensajero dado de alta hoy aparece hoy.
7. Si un envío queda en **INCIDENCIA**, solo un despachador puede reanudarlo. El
   conductor reporta el incidente; otro rol decide si continúa.
8. Un envío que no llega puede cerrarse: **DEVUELTO** si ya salió a la calle,
   **CANCELADO** si todavía no se había recogido. Sin esos dos cierres, un envío
   fallido quedaría abierto para siempre.

### Recorrido como conductor

1. **Panel** — el mismo tablero, acotado a sus envíos. La pantalla lo dice con
   esas palabras, para que no crea que la empresa entera mueve seis envíos.
2. **Órdenes** — solo las asignadas a él. El filtro lo aplica el servidor.
3. Abrir el envío y **registrar punto de control**: los estados alcanzables
   aparecen como botones grandes, con su código. La ubicación se adjunta con una
   casilla.
4. Antes de entregar, **cargar la evidencia**. La pantalla muestra los tres
   pasos: solicitar enlace, cargar el archivo, confirmar. En el teléfono se abre
   la cámara trasera.
5. Con la evidencia confirmada, el botón **ENTREGADO** se habilita. Sin ella, el
   servidor rechaza la entrega.

### Recorrido como administrador

1. **Administración → Usuarios** — crear cuentas, cambiar roles, desactivar
   accesos y restablecer contraseñas. Dos reglas que el sistema no deja saltarse:
   la organización no puede quedarse sin administradores, y un administrador no
   puede desactivarse a sí mismo.
2. **Administración → Empresa** — razón social, NIT, dirección y contacto: lo que
   sale impreso en las guías.
3. **Maestros** — tiendas, clientes y transportistas. Eliminar **desactiva**, no
   borra: los envíos históricos apuntan a ellos y borrarlos falsearía la
   trazabilidad.
4. **Roles y permisos** — qué puede hacer cada rol. Los de fábrica se ajustan y
   se pueden crear otros; el editor muestra qué hace cada operación. El
   administrador no se edita, y ningún rol puede a la vez operar y leer la
   bitácora.
5. **Operaciones** — los módulos de la empresa. Los que no están disponibles
   aparecen con su motivo. Un administrador puede apagar uno que su operación no
   use; apagarlo exige decir por qué, y no afecta a las demás empresas.
4. **Mi cuenta → Cambiar contraseña** — pide la actual y cierra las demás
   sesiones.

### Recorrido como auditor

1. **Panel** — el tablero de la organización auditada.
2. **Bitácora** — tabla con búsqueda y filtro por resultado. Cada fila se abre
   para ver el detalle completo, incluidos el hash previo y el propio. Los
   intentos fallidos de inicio de sesión también aparecen aquí: es lo que
   permite distinguir un olvido de un ataque por fuerza bruta.
3. **Verificar cadena** — recalcula el encadenamiento y dibuja los eslabones;
   los rotos aparecen en rojo. La verificación también queda registrada.

El auditor no puede escribir nada. Si lo intenta, recibe 403 y el intento queda
en la bitácora.

### Comprobar el aislamiento entre empresas

Entrar como `despacho@sabana.test` e intentar abrir un envío de `org-andes` por
su identificador: el sistema responde como si no existiera. El intento queda en
la bitácora de `org-sabana`, no en la de `org-andes`.

---

## 2. Rastro — consulta pública

http://localhost:5173/rastreo

Es el único punto que responde **sin cuenta**. Se pega el identificador del envío
y se ve el avance: barra de progreso sobre el flujo, línea de tiempo y si hubo
evidencia.

Lo que **no** muestra: identificador de organización, identidad del mensajero,
dirección de origen, coordenadas, ni el nombre completo del destinatario (se
enmascara: `Laura M. R.`).

El enlace es compartible: `/rastreo?envio=<identificador>`.

---

## 3. Rastro — API

http://localhost:8080 · Contratos en [`api/contratos.md`](../api/contratos.md).

Útil para comprobar controles a mano:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"correo":"carlos@andes.test","clave":"Andes.Carlos.2026"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Un conductor no puede crear envíos: responde 403 y queda en bitácora.
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/envios \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"origen":{"linea":"a b c"},"destino":{"linea":"d e f"},"destinatario":{"nombre":"Nadie"}}'
```

El catálogo de estados es abierto y sirve para comprobar que la pila responde
sin necesidad de token:

```bash
curl -s http://localhost:8080/catalogos/estados
```

Un usuario inexistente responde lo mismo que una clave incorrecta —401 con el
mismo mensaje—, que es lo que impide enumerar cuentas:

```bash
curl -s -X POST http://localhost:8080/auth/token -H "Content-Type: application/json" -d '{"correo":"nadie@andes.test","clave":"cualquiera"}'
```

Cada servicio expone además su documentación interactiva con `/docs` en su
puerto directo:

| Puerto | Servicio | Puerto | Servicio |
|---|---|---|---|
| 8001 | identidad | 8005 | consulta pública |
| 8002 | envíos | 8006 | bitácora |
| 8003 | rastreo | 8008 | maestros |
| 8004 | evidencias | 8009 | tablero |

El 8007 es de **Cotejo**, que es otro proyecto.

---

## 4. Cotejo — interfaz de auditoría

http://localhost:5175 · Solo el rol **auditor** entra.

Entrar con `auditor@andes.test` / `Andes.Auditor.2026`. La identidad la resuelve el
proveedor de Rastro: el auditor es un usuario de la organización auditada.

### Las tres pestañas

**Catálogo.** Los ocho controles con su marco de referencia, criterio,
procedimiento y severidad, más los dos hallazgos permanentes. Conviene mirarlo
antes de ejecutar: el criterio se declara de antemano justamente para que no
pueda acomodarse al resultado.

**Ejecución.** El botón recorre el catálogo completo en una sola invocación.
Al terminar muestra:

- **Cobertura** — cuántos controles tienen resultado. En local es `5/8`.
- **Resultado por control** — pulsar uno abre su papel de trabajo con la salida
  literal y la comprobación de que su huella coincide con la registrada.
- **Verificar almacén** — recalcula todas las huellas y detecta si alguien editó
  un archivo de evidencia.
- **Ver informe** — el informe completo en texto plano.
- **Hallazgos** — cada uno con condición, criterio, causa, efecto, severidad,
  recomendación y referencia a su papel de trabajo.

**Reproducibilidad.** Compara dos ejecuciones y comprueba que clasifican igual
los ocho controles. Avisa si ambas se hicieron bajo la misma identidad: la
comprobación vale más cuando la segunda la ejecuta un integrante distinto.

### Desde línea de comandos

La línea de comandos es el camino principal —es la que se versiona— y usa las
mismas funciones que la interfaz:

```bash
cd cotejo
python -m cotejo catalogo
python -m cotejo ejecutar
python -m cotejo verificar <ejecución>
python -m cotejo comparar <ej-a> <ej-b>
python -m cotejo glosario
```

> Contra el entorno local hacen falta credenciales ficticias, porque las pruebas
> de cumplimiento consultan la interfaz del proveedor:
>
> ```bash
> AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=localsecreto \
> COTEJO_ENDPOINT_S3=http://localhost:9000 python -m cotejo ejecutar
> ```

> En un despliegue con datos reales, las claves de la semilla ya no valen. Se
> pasan por entorno para no editar el programa:
>
> ```bash
> COTEJO_CLAVES='{"auditor@andes.test":"la clave real"}' python -m cotejo ejecutar
> ```

Códigos de salida: `0` todo conforme · `1` hay desviaciones · `3` algo no pudo
comprobarse.

---

## Desarrollo de las interfaces

Con la pila levantada, para iterar sobre una interfaz con recarga en caliente:

```bash
cd web          # o: cd cotejo/web
npm install
npm run dev
```

Vite reenvía las llamadas a la API, de modo que no hay diferencia de origen entre
desarrollo y el sitio publicado. El contenedor `web` puede seguir corriendo: usa
otro puerto y no estorba.

Antes de dar por terminado un cambio:

```bash
npm run typecheck
npm run build
```

---

## En AWS

La secuencia de despliegue compila y publica las interfaces automáticamente:

```bash
./deploy/aws/desplegar.sh
```

La etapa `60-sitios.sh` compila, crea el contenedor del sitio, escribe el
`configuracion.json` con la dirección real de la API y sincroniza los archivos.

**La interfaz de Cotejo no se publica por omisión.** El almacén de papeles de
trabajo concentra información sobre las debilidades del sistema auditado, y
publicarla en un sitio de lectura pública ampliaría la superficie sin necesidad.
Se sirve en la máquina del auditor con `npm run dev`, o se publica de forma
explícita:

```bash
RASTRO_PUBLICAR_COTEJO=si ./deploy/aws/60-sitios.sh
```

Detalles del despliegue, restricciones del laboratorio y migración entre cuentas
en [`entorno-aws.md`](entorno-aws.md).
