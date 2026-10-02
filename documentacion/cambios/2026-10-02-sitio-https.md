# Cambios · 2026-10-02 · Revisión del despliegue y sitio por HTTPS

Dos cosas en la misma sesión: se investigó por qué Rastro estaba caído y se
añadió la entrada HTTPS al sitio
([ADR-012](../decisiones/adr-012-sitio-https-por-api-gateway.md)).

---

## 1. La caída

**Qué pasó.** El 2026-10-02 entre las 13:40 y las 13:50 UTC (08:40 a 08:50 en
Bogotá), con la sesión del laboratorio cerrada, la API recibió 29 peticiones y
**22 respondieron 5xx**. Las 7 restantes son, por la cuenta, las peticiones
previas CORS que responde API Gateway sin llegar a ninguna función. En esa
ventana las funciones `auth`, `masters`, `shipments` y `dashboard` registran
errores pero **ninguna invocación, ninguna duración y ninguna línea de log**: el
código no llegó a ejecutarse.

**Por qué.** Al arrancar en frío, Lambda descifra las variables de entorno de la
función con la llave `aws/lambda`, usando el rol de ejecución. CloudTrail
registra cada uno de esos intentos rechazado:

```
User: arn:aws:sts::484948252891:assumed-role/LabRole/rastro-auth is not
authorized to perform: kms:Decrypt on resource: arn:aws:kms:us-east-1:
484948252891:key/a2b65ba9-cce5-4db4-8713-778ca4d93e69 with an explicit deny
in a service control policy: arn:aws:organizations::246880240156:policy/
o-nuzfir8dhd/service_control_policy/p-risxnkh6
```

La denegación viene de una **política de control de servicios de la
organización de AWS Academy** (cuenta 246880240156), no de nada que el proyecto
configure ni pueda cambiar. La misma noche, a las 08:07 UTC, Lambda desactivó
los disparadores de DynamoDB de otro proyecto de la cuenta
(`saas-multiinquilino-30112-pedidos`) con el motivo `Unable to assume role`:
es la misma restricción vista desde otro servicio.

**Cuándo se levantó.** Al abrir la sesión del laboratorio a las 14:54 UTC. Desde
las 15:01 todas las peticiones responden.

**Lo que no se explica.** El 2026-09-27 y el 2026-09-28, con el laboratorio
también cerrado desde el 2026-09-26, las funciones descifraron sus variables sin
problema y la API respondió sin un solo 5xx. Y los disparadores del otro
proyecto funcionaron cinco días seguidos sin sesión. La restricción no estaba
activa en el cierre anterior y sí en este. La política es de AWS Academy y la
cuenta no puede leerla (`organizations:DescribeOrganization` también está
denegado), de modo que el motivo del cambio no se puede determinar desde aquí.

**Qué no fue.** CloudTrail, consultado completo desde el 2026-09-26 23:30 UTC
(172 eventos de escritura), no registra ningún borrado ni cambio sobre recursos
de Rastro antes de esta sesión de trabajo. Ningún dato se perdió: 96 envíos, 63
maestros y 128 entradas de bitácora (el 2026-09-26 eran 84, 63 y 0).

| Comprobación, ya con la sesión abierta | Resultado |
|---|---|
| `95-verificar.sh` | Todos los componentes verificados |
| Sitio de S3 | HTTP 200 |
| Punto público | 404 ante un identificador inexistente, el esperado |
| `POST /auth/token` con credenciales falsas | 401 `NO_AUTENTICADO`: la función lee su tabla |
| Concurrencia reservada de las ocho funciones | Sin límite: ninguna estrangulada |
| Llave `alias/rastro` | Habilitada |

### Consecuencia operativa

**Rastro solo está garantizado con la sesión del laboratorio abierta.** El sitio
de S3 y la entrada HTTPS cargan siempre, porque no ejecutan nada, pero toda
operación que pase por una función puede fallar con la sesión cerrada. Antes de
una demostración o una sustentación hay que pulsar *Start Lab*.

No hay un arreglo fiable del lado del proyecto. Quitar las variables de entorno
evitaría el descifrado al arrancar, pero los disparadores del otro proyecto
muestran que con la sesión cerrada el rol tampoco se puede asumir para leer
DynamoDB: la función arrancaría y fallaría en la primera consulta. Se registra
como restricción **RE-06** en [entorno-aws.md](../despliegue/entorno-aws.md).

### Observación para el próximo despliegue completo

**`config/.jwt.env` no existe en esta copia del repositorio.** Está excluido del
control de versiones desde H-01 y no viaja con un clon. Las funciones desplegadas
no se ven afectadas, porque tienen el secreto en su configuración, pero
`desplegar.sh` completo se detendría en `30-funciones.sh`, que se niega a
desplegar sin secreto. Si se genera uno nuevo, todas las sesiones abiertas se
cierran. Generarlo: ver [entorno-aws.md](../despliegue/entorno-aws.md#el-secreto-de-firma).

---

## 2. Sitio por HTTPS

El alojamiento estático de S3 solo responde por HTTP. CloudFront, que era la
solución prevista, está impedido en el laboratorio: la sesión no puede ni listar
distribuciones. Se registra como **RE-05**.

### Qué cambió

| Archivo | Cambio |
|---|---|
| `deploy/aws/65-sitio-https.sh` | **Nuevo.** Interfaz `rastro-sitio` de API Gateway que sirve el sitio por HTTPS leyendo el contenedor por su punto REST, también HTTPS. Enlaces directos en 200; un recurso que falta en 404 |
| `deploy/aws/comun.sh` | `NOMBRE_API_SITIO`, `origenes_web` y `aplicar_cors_evidencias`. La regla CORS de evidencias pasa aquí porque ahora la aplican dos etapas |
| `deploy/aws/10-datos.sh` | Usa `aplicar_cors_evidencias` en lugar de la regla en línea |
| `deploy/aws/desplegar.sh` | Incluye la etapa 65 entre `60-sitios` y `90-configuracion` |
| `deploy/aws/90-configuracion.sh` | Escribe `url_sitio` en `config/deployment.json` |
| `deploy/aws/95-verificar.sh` | Comprueba la interfaz del sitio, la raíz y `/rastreo` en 200 por HTTPS, y que `configuracion.json` llegue como archivo y no como el índice |
| `config/.sitio.env` | **Nuevo**, generado: identificador y dirección de la interfaz del sitio |

### Qué quedó desplegado

| Componente | Recurso |
|---|---|
| Sitio por HTTPS | `https://td70a5indc.execute-api.us-east-1.amazonaws.com` — 5 rutas, 4 integraciones |
| Certificado | `*.execute-api.us-east-1.amazonaws.com`, emitido por Amazon RSA 2048 S21, válido hasta el 2027-04-08 y renovado por el proveedor |
| CORS de evidencias | El origen del sitio de S3 y el HTTPS |

### Verificación

| Comprobación | Resultado |
|---|---|
| `/`, `/rastreo`, `/envios/abc-123` | 200, `text/html`, el índice |
| `/configuracion.json`, `/icono.svg` | 200 con su tipo: no reciben el índice |
| `/assets/index-*.js`, `/assets/index-*.css` | 200, con `max-age=31536000, immutable` |
| `/assets/no-existe.js` | 404 (S3 responde 403; la integración lo traduce) |
| Índice | `cache-control: no-cache`, el mismo que en S3 |
| Cadena del certificado | `Verify return code: 0 (ok)` |
| Petición previa CORS al contenedor de evidencias desde el origen HTTPS | 200 con `Access-Control-Allow-Origin` del sitio |
| La misma desde un origen ajeno | 403 |
| Navegador, a 1024 y a 360 px | Contexto seguro, sin errores en consola, sin desbordamiento horizontal; la página llega a la API (CORS abierto) |
| Segunda ejecución de la etapa 65 | Sin duplicados: todo «ya existente» |
| Segunda ejecución de `10-datos.sh` | Encuentra el origen HTTPS por sí sola y deja la misma regla |
| Sitio de S3 por HTTP | Sigue respondiendo 200 |

No se comprobó el inicio de sesión desde el navegador en el sitio desplegado.
Sí se comprobó que `POST /auth/token` responde 401 ante credenciales falsas, lo
que confirma que la función y su tabla están operativas.

### Evidencias

- `evidencias-despliegue/20261002T151206Z-datos.txt`
- `evidencias-despliegue/20261002T151227Z-sitio-https.txt`
- `evidencias-despliegue/20261002T151304Z-configuracion.txt`
- `evidencias-despliegue/20261002T151306Z-verificacion.txt`

Las cuatro terminan con código de salida 0.
