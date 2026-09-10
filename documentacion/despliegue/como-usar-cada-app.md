# Cómo se usa cada aplicación

Fecha: 2026-09-10 · Versión: 0.2

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
| Los seis servicios | Un contenedor cada uno | Una función Lambda cada uno |
| Datos | DynamoDB Local | DynamoDB |
| Evidencias | MinIO, **sin cifrado KMS** | S3 + KMS |
| Identidad | Microservicio `auth` | Amazon Cognito |
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

Abre http://localhost:5173.

### Cuentas sintéticas

| Correo | Clave | Organización | Rol |
|---|---|---|---|
| `admin@andes.test` | `Andes.2026` | org-andes | administrador |
| `despacho@andes.test` | `Andes.2026` | org-andes | despachador |
| `carlos@andes.test` | `Andes.2026` | org-andes | conductor |
| `auditor@andes.test` | `Andes.2026` | org-andes | auditor |
| `despacho@sabana.test` | `Sabana.2026` | org-sabana | despachador |

La pantalla de acceso las lista: pulsar una rellena el formulario.

### Recorrido como despachador

1. **Panel** — envíos en curso, sin asignar y con incidencia, más la
   distribución del proceso.
2. **Registrar** — crear un envío. El sistema devuelve un identificador
   aleatorio; ese es el que se le entrega al destinatario. La pantalla de detalle
   ofrece copiarlo.
3. Abrir el envío y **asignar mensajero**. Hay tres botones con los conductores
   sintéticos, o se escribe el identificador a mano.
4. Si un envío queda en **INCIDENCIA**, solo el despachador puede reanudarlo. El
   conductor reporta el incidente; otro rol decide si continúa.

### Recorrido como conductor

1. **Panel** — su siguiente parada, con acceso directo.
2. **Mis envíos** — solo los asignados a él. El filtro lo aplica el servidor.
3. Abrir el envío y **registrar punto de control**: los estados alcanzables
   aparecen como botones grandes. La ubicación se adjunta con una casilla.
4. Antes de entregar, **cargar la evidencia**. La pantalla muestra los tres
   pasos: solicitar enlace, cargar el archivo, confirmar. En el teléfono se abre
   la cámara trasera.
5. Con la evidencia confirmada, el botón **ENTREGADO** se habilita. Sin ella, el
   servidor rechaza la entrega.

### Recorrido como auditor

1. **Panel** — registros en bitácora, intentos rechazados y estado de la cadena.
2. **Bitácora** — tabla con búsqueda y filtro por resultado. Cada fila se abre
   para ver el detalle completo, incluidos el hash previo y el propio.
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
  -d '{"usuario":"carlos@andes.test","clave":"Andes.2026"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Un conductor no puede crear envíos: responde 403 y queda en bitácora.
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/envios \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"origen":{"linea":"a b c"},"destino":{"linea":"d e f"},"destinatario":{"nombre":"Nadie"}}'
```

Cada servicio expone además su documentación interactiva en su puerto directo:
8001 auth, 8002 envíos, 8003 rastreo, 8004 evidencias, 8005 público, 8006
bitácora, con `/docs`.

---

## 4. Cotejo — interfaz de auditoría

http://localhost:5175 · Solo el rol **auditor** entra.

Entrar con `auditor@andes.test` / `Andes.2026`. La identidad la resuelve el
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
```

> Contra el entorno local hacen falta credenciales ficticias, porque las pruebas
> de cumplimiento consultan la interfaz del proveedor:
>
> ```bash
> AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=localsecreto \
> COTEJO_ENDPOINT_S3=http://localhost:9000 python -m cotejo ejecutar
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
