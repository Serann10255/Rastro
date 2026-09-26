# Cambios · 2026-09-26 · Primer despliegue en AWS Academy

Primera ejecución de `deploy/aws/` contra la cuenta del Learner Lab, desde
Windows con Git Bash, en una cuenta vacía. Hasta hoy los guiones solo se habían
escrito, nunca ejecutado ([estado anterior](../despliegue/entorno-aws.md#estado-de-verificacion)).

**Resultado:** la secuencia completa termina sin errores en unos ocho minutos,
`95-verificar.sh` confirma todos los componentes y una segunda ejecución no
duplica recursos ni datos.

---

## Qué quedó desplegado

| Componente | Recurso |
|---|---|
| Sitio de Rastro | `http://rastro-web-484948252891.s3-website-us-east-1.amazonaws.com` |
| Interfaz HTTP | `https://l7ymvbqqc4.execute-api.us-east-1.amazonaws.com` — 46 rutas, 8 integraciones |
| Funciones | `rastro-auth`, `-shipments`, `-tracking`, `-evidence`, `-public`, `-audit`, `-masters`, `-dashboard` (python3.12, `LabRole`) |
| Datos | Tablas `rastro-envios`, `rastro-bitacora`, `rastro-maestros`; llave `alias/rastro` con rotación |
| Contenedores | `rastro-evidencias-*` (cifrado, versionado, privado, CORS), `rastro-registro-*`, `rastro-web-*` |
| Registro | CloudTrail `rastro-actividad` con validación de integridad; eventos de datos desactivados |
| Semilla | 2 organizaciones, 10 usuarios, 8 roles, 20 envíos sintéticos |

Los identificadores son de esta cuenta del laboratorio. En otra cuenta cambian
solos (REQ-09); esta tabla es constancia de lo desplegado hoy, no configuración.

---

## Defectos que la primera ejecución destapó

Ninguno se veía en local. Los dos primeros habrían dejado el sistema inservible
**con todos los guiones terminando en verde**, y por eso importan más que los
demás.

### 1. El validador de API Gateway habría bloqueado todas las rutas protegidas

`40-api.sh` intentaba crear el validador JWT para responder a SU-01 y, si lo
lograba, lo asociaba a todas las rutas protegidas. Con el proveedor propio el
token va firmado con HS256 y el emisor no publica un JWKS: el validador habría
rechazado todo token válido y cada ruta protegida habría respondido 401.

**Corrección:** crear el validador sigue siendo la prueba de SU-01, pero solo se
asocia a las rutas con un proveedor de clave pública. Con el propio, nunca.

### 2. El navegador no podía subir evidencias

El dispositivo sube la foto directamente al contenedor con un enlace
prefirmado. El contenedor de evidencias no tenía CORS, de modo que el navegador
bloqueaba la carga aunque la firma fuera válida. En local no se notaba porque
MinIO acepta cualquier origen.

**Corrección:** `10-datos.sh` aplica CORS al contenedor, solo para el origen del
sitio de Rastro (configurable con `RASTRO_ORIGENES_WEB`). Comprobado: la carga
con el enlace que genera el propio código responde 200, el objeto queda cifrado
con la llave del proyecto y un origen ajeno recibe 403.

### 3. Solo se creaban 26 de las 46 rutas

Con `--output text`, la CLI aplica `--query` a cada página por separado. Pasadas
las 25 rutas, buscar una inexistente devolvía `None` una vez por página, y el
guion lo tomaba por un identificador: daba por existente lo que no existía.

**Corrección:** `primer_resultado` en `comun.sh` consulta con `--output json`,
que une las páginas antes de aplicar la consulta. Se usa en las cuatro búsquedas
de `40-api.sh`.

### 4. SU-01 se declaraba descartado por un motivo que no era de permisos

El validador se rechazaba porque el emisor propio (`https://rastro-api.<cuenta>.rastro`)
no es una URL válida, y el guion concluía «el laboratorio no lo permite». Era un
falso hallazgo.

**Corrección:** la prueba usa como emisor la dirección de la propia interfaz, y
el resultado distingue tres casos: *confirmado*, *descartado* (solo ante una
denegación de permisos) e *indeterminado* (cualquier otro rechazo), con el
mensaje del proveedor en la salida.

**Resultado hoy: indeterminado.** API Gateway descarga el documento OpenID del
emisor al crear el validador, y el sistema no publica uno. Confirmarlo exige un
emisor OpenID real.

### 5. Empaquetado de funciones en Windows

- Git Bash no trae `zip`. `30-funciones.sh` recurre a la biblioteca estándar de
  Python y fija permisos Unix explícitos (`0644`), porque un archivo comprimido
  en Windows no los trae y Lambda podría no poder leer el código.
- La CLI de AWS es un ejecutable nativo y no entiende `fileb:///tmp/...`.
  `ruta_nativa` en `comun.sh` convierte la ruta con `cygpath` cuando existe.
- Las dependencias aceptan también ruedas `manylinux_2_28` (Lambda python3.12
  corre sobre Amazon Linux 2023) y se instalan sin `.pyc` del equipo local.

### 6. Variables de entorno de las funciones en JSON

Se pasaban con la sintaxis abreviada de la CLI. El emisor lleva `:` y `/`, y un
secreto en base64 puede llevar `=`. Ahora se pasan en JSON.

### 7. Elección del intérprete de Python

`20-identidad.sh` elegía `python3` antes que `python`. En Windows `python3` es
el de la Microsoft Store, sin `boto3`. Ahora elige el primer intérprete que
importa `boto3`, o el de `RASTRO_PYTHON`.

---

## Otros cambios

- `40-api.sh` aplica CORS en cada ejecución y no solo al crear la interfaz, y
  expone `content-disposition` para que la exportación CSV conserve el nombre
  de archivo.
- `30-funciones.sh` lee el secreto de firma de `config/.jwt.env` si no está en
  el entorno. El archivo se añadió a `.gitignore`; esa exclusión se retiró
  después por error y el secreto llegó al repositorio público, donde hubo que
  rotarlo ([H-01](2026-09-26-h01-secreto-expuesto.md)).
- Documentación: [despliegue en AWS](../despliegue/entorno-aws.md) (estado,
  sección para Windows, limitaciones del sitio) y
  [plan de pruebas](../pruebas/plan-y-trazabilidad.md) (REQ-09 pasa a parcial).

---

## Pendiente

- **SU-01:** confirmarlo con un emisor OpenID real.
- **REQ-09:** simulacro de migración a otra cuenta con la versión corregida.
- **Cotejo contra AWS:** `cd cotejo && python -m cotejo ejecutar`, ahora que
  los ocho controles son ejecutables.
- **Contraseñas de la semilla:** son de desarrollo y están en el repositorio.
  Sirven para la demostración; no para datos reales.
