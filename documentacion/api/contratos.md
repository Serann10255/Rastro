# Contratos de la interfaz de programación

Fecha: 2026-09-10 · Versión: 0.3

Base local: `http://localhost:8080` · En AWS: el valor de `url_publica_api` en
`config/deployment.json`.

Salvo la consulta pública, toda operación exige
`Authorization: Bearer <token>`. El token transporta el sujeto, los grupos y el
identificador de organización; ninguna operación acepta la organización en el
cuerpo de la petición.

---

## Códigos de respuesta y qué significan

| Código | Cuándo | Cuerpo |
|---|---|---|
| 200 / 201 | Operación resuelta | Recurso |
| 400 | Transición inválida o entrega sin evidencia | `TRANSICION_INVALIDA` / `SOLICITUD_INVALIDA` |
| 401 | Token ausente, inválido, caducado o sin organización | `NO_AUTENTICADO` |
| 403 | El grupo del usuario no puede ejecutar la operación | `NO_AUTORIZADO` |
| 404 | El recurso no existe **o pertenece a otra organización** | `NO_ENCONTRADO` |
| 409 | Conflicto de escritura | `CONFLICTO` |
| 422 | El identificador no tiene el formato esperado | Validación |

**El 404 ante un recurso de otra organización es deliberado.** Responder 403
confirmaría que el recurso existe, que es información que el solicitante no
debería obtener. El intento queda registrado con resultado `DENY` en la bitácora
de quien lo hizo.

Formato de error:

```json
{
  "codigo": "TRANSICION_INVALIDA",
  "mensaje": "Transicion no permitida de CREADO a ENTREGADO.",
  "detalle": { "origen": "CREADO", "destino": "ENTREGADO", "permitidas": ["ASIGNADO", "INCIDENCIA"] }
}
```

---

## Identidad — servicio `auth`

> Es un proveedor de identidad propio: las contraseñas se almacenan derivadas y
> las cuentas se administran desde el sistema. Puede sustituirse por Amazon
> Cognito sin tocar el resto, porque los demás servicios solo conocen la forma
> del token. El razonamiento está en
> [ADR-007](../decisiones/adr-007-identidad-propia.md).

### `POST /auth/token` — abierta

```json
{ "correo": "admin@andes.test", "clave": "Andes.Admin.2026" }
```

```json
{
  "token": "eyJhbGciOi...",
  "refresco": "eyJhbGciOi...",
  "tipo": "Bearer",
  "vigencia_segundos": 3600,
  "vigencia_refresco_segundos": 43200,
  "usuario": {
    "sub": "u-3f1c...", "nombre": "Marcela Ariza",
    "correo": "admin@andes.test", "org_id": "org-andes",
    "grupos": ["administrador"], "activo": true
  }
}
```

La respuesta **nunca incluye `hash_clave`**: `vista_usuario` lo retira en el
repositorio, no en cada punto de la API, para que añadir un punto nuevo no sea
una oportunidad de filtrarlo.

Ante un fallo responde 401 con **el mismo mensaje** tanto si el usuario no
existe como si la clave es incorrecta o la cuenta está inactiva. Cuando el
usuario no existe se verifica igualmente contra un señuelo: sin eso, medir el
tiempo de respuesta permite enumerar las cuentas.

### `POST /auth/refrescar` — abierta

```json
{ "refresco": "eyJhbGciOi..." }
```

Devuelve un par nuevo, con la misma forma que `/auth/token`. **El refresco se
rota**: el anterior deja de valer, de modo que un robo se nota en lugar de
convivir en silencio. Los grupos se releen del registro del usuario y no del
token, para que un cambio de rol surta efecto en la siguiente renovación.

Si la sesión fue cerrada, caducó o el refresco ya se usó, responde 401: en los
tres casos hay que volver a autenticarse.

### `POST /auth/salir`

Revoca la sesión en el servidor. Borrar el token del navegador basta para el uso
normal, pero no si el token ya se copió.

### `GET /auth/yo`

Devuelve `usuario`, `empresa` y `permisos`: es lo que la interfaz necesita al
arrancar para saber en nombre de quién se opera y qué ofrecer. Los permisos son
los efectivos, resueltos con los roles de la organización —no son un control: el
servidor decide en cada operación, y esto solo evita ofrecer botones que van a
responder 403—. El usuario se relee del registro, no del
token, de modo que un cambio de rol se ve sin esperar a la renovación.

### `POST /auth/clave`

```json
{ "clave_actual": "Andes.Admin.2026", "clave_nueva": "una clave larga de verdad" }
```

Exige la contraseña actual —tener el token no es prueba de conocerla— y **cierra
las demás sesiones**: quien cambia su clave suele hacerlo porque sospecha que
alguien más la tiene. Mínimo 12 caracteres.

### `GET /auth/roles` — abierta

El catálogo de operaciones del sistema, agrupado por área y con la descripción
de cada una, más los roles de fábrica.

```json
{
  "areas": [
    { "area": "envios", "nombre": "Envios", "operaciones": [
      { "operacion": "envio:crear", "descripcion": "Registrar envios, individuales o en lote",
        "escritura": true } ] }
  ],
  "integrados": [
    { "clave": "coordinador", "nombre": "Coordinador", "operaciones": ["envio:crear"],
      "integrado": true, "editable": true }
  ]
}
```

Es abierta porque describe el **modelo de autorización**, no los datos de
ninguna organización: es la misma información que un evaluador necesita para
juzgar el control. Los roles concretos de una empresa se piden en `/roles`.

**El catálogo es cerrado.** Un rol solo puede contener operaciones que aparezcan
aquí; lo que no esté, no existe, aunque alguien lo escriba en la tabla.

### `GET /roles`

Grupos: quien tenga `rol:consultar` (de fábrica, administrador y auditor).

```json
{ "roles": [
  { "clave": "coordinador", "nombre": "Coordinador", "descripcion": "…",
    "operaciones": ["envio:crear", "evento:reanudar"],
    "integrado": true, "editable": true, "cuentas": 1 }
], "total": 6 }
```

`cuentas` dice cuántas personas lo tienen asignado: es lo que hay que mirar
antes de recortarle permisos a un rol.

### `POST /roles` · `POST /roles/{clave}`

Permiso: `rol:administrar` (de fábrica, solo el administrador).

```json
{ "clave": "supervisor-turno", "nombre": "Supervisor de turno",
  "descripcion": "Vigila la operacion y autoriza detenidos.",
  "operaciones": ["envio:listar", "envio:consultar", "evento:reanudar"] }
```

Al actualizar, la **clave no se cambia**: es lo que guardan las cuentas, y
cambiarla dejaría a cada usuario apuntando a un rol que ya no existe.

Cuatro rechazos, en este orden:

| Situación | Respuesta |
|---|---|
| Una operación que no existe en el catálogo | 400, con el nombre de la operación |
| El rol mezcla leer la bitácora con operar | 400. **No es un aviso**: quien revisa el registro no puede ser quien lo produce |
| Se conceden operaciones que quien edita no tiene | 403, y el intento queda como `escalada_de_privilegios` |
| Es el rol `administrador` | 400. No se edita: es el seguro contra quedarse sin acceso |

### `POST /roles/{clave}/eliminar`

Permiso: `rol:administrar`. Solo roles creados por la organización y solo si
**nadie los usa** —responde 409 con las cuentas afectadas—. Los de fábrica no se
eliminan nunca; pueden ajustarse o dejar de asignarse.


### `GET /usuarios` · `POST /usuarios` · `POST /usuarios/{correo}`

Grupo: `administrador` (listar también `auditor`).

```json
{ "correo": "nuevo@andes.test", "nombre": "Ana Ruiz",
  "grupos": ["conductor"], "clave": "clave inicial larga" }
```

Dos reglas que el servicio impone y que no se pueden desactivar:

- **No se puede quedar la organización sin administradores.** Cubre a la vez el
  cambio de rol y la desactivación, porque ambos llevan al mismo bloqueo
  irreversible.
- **Un administrador no puede desactivarse a sí mismo.** Es el error de
  configuración más fácil de cometer y el más caro de deshacer.

### `GET /empresa`

Datos de la organización del token: razón social, NIT, dirección y contacto.

### `GET /equipo/mensajeros`

Grupos: `administrador`, `despachador`. Los conductores **activos** de la
organización del token.

```json
{ "mensajeros": [ { "sub": "u-aa34b9cd1af5", "nombre": "Carlos Nieto Pardo",
                    "telefono": "+57 320 118 3390" } ], "total": 1 }
```

Es una vista reducida —tres campos— y por eso la puede pedir un despachador, que
no administra cuentas pero sí asigna. Existe porque la pantalla de asignación
llevaba tres mensajeros escritos con su identificador: el día que entrara uno
nuevo, nadie iba a recompilar el sitio para que apareciera.

Un mensajero desactivado deja de aparecer: asignarle un envío a una cuenta
desactivada produce un envío que nadie puede mover.


---

## Datos maestros y catálogos — servicio `masters`

### `GET /catalogos/estados` — abierta

El catálogo completo del ciclo de vida, con código numérico, fase y si el estado
es final.

```json
{ "estados": [
  { "codigo": 10, "estado": "CREADO", "etiqueta": "Creado", "fase": "REGISTRO", "final": false },
  { "codigo": 40, "estado": "EN_TRANSITO", "etiqueta": "En transito", "fase": "TRANSPORTE", "final": false },
  { "codigo": 60, "estado": "ENTREGADO", "etiqueta": "Entregado", "fase": "CIERRE", "final": true }
] }
```

Es abierta porque no contiene datos de ninguna organización: es la definición
del proceso, la misma que un transportista externo necesita para interpretar un
archivo de intercambio. Se sirve desde el servidor y no se duplica en el cliente
porque un catálogo copiado se desincroniza en cuanto se añade un estado, y el
síntoma es una pantalla que muestra un estado en blanco sin decir por qué.

### `GET /catalogos/modulos`

Grupos: los cuatro. Los módulos de la organización del token.

```json
{ "modulos": [
  { "clave": "ordenes", "nombre": "Órdenes", "descripcion": "Registro, seguimiento y guías",
    "icono": "paquete", "ruta": "/envios", "grupos": ["administrador", "despachador", "conductor"],
    "orden": 10, "destacado": true, "disponible": true, "motivo": "", "contador": "envios_abiertos" },
  { "clave": "rutas", "nombre": "Rutas", "icono": "mapa", "ruta": "", "orden": 200,
    "destacado": false, "disponible": false,
    "motivo": "La optimizacion de rutas esta excluida del alcance del proyecto." }
], "total": 14 }
```

La lista vive en la tabla de maestros y no en la interfaz: dos empresas pueden
tener módulos distintos y dar de alta uno no puede exigir recompilar el sitio.
`icono` es **el nombre** del icono, no el dibujo; si la interfaz no lo conoce,
dibuja el genérico en lugar de dejar un hueco.

`grupos` sirve para no ofrecer un acceso que el servidor va a rechazar. **No es
el control**: la autorización se decide en cada operación.

### `POST /catalogos/modulos/{clave}`

Grupo: `administrador`. Enciende o apaga un módulo de su organización.

```json
{ "disponible": false, "motivo": "No se usa en esta operacion." }
```

Solo se cambian esos dos campos: el nombre, la ruta y los grupos describen el
sistema, no la decisión de la empresa. **Apagar exige motivo** —un módulo ausente
sin motivo parece un olvido— y apagarlo en una organización no lo apaga en las
demás.

### `/tiendas`, `/clientes`, `/transportistas`

| Operación | Grupos |
|---|---|
| `GET /tiendas` | los cuatro grupos |
| `POST /tiendas` | `administrador` |
| `POST /tiendas/{id}` | `administrador` |
| `POST /tiendas/{id}/eliminar` | `administrador` |

Igual para `/clientes` y `/transportistas`. **Leer y escribir tienen permisos
distintos**: el despachador necesita consultar las tiendas para registrar un
envío, pero cambiar la dirección de una tienda afecta a toda la operación.

**Eliminar es desactivar.** Los envíos históricos apuntan a tiendas y clientes;
borrarlos dejaría registros apuntando a nada y falsearía la trazabilidad.

---

## Tablero — servicio `dashboard`

### `GET /tablero?dias=30`

Grupos: los cuatro. `dias` entre 1 y 365.

```json
{
  "empresa": { "org_id": "org-andes", "nombre": "Andes Logistica SAS", "nit": "901..." },
  "ventana": { "dias": 30, "desde": "2026-08-12", "hasta": "2026-09-10" },
  "alcance": "organizacion",
  "totales": { "envios": 62, "abiertos": 35, "cerrados": 27, "entregados": 24 },
  "tasa_entrega": 88.9,
  "por_estado": [ { "codigo": 10, "estado": "CREADO", "cantidad": 27 } ],
  "por_fase": [ { "fase": "REGISTRO", "cantidad": 27 } ],
  "atencion": { "sin_asignar": 27, "con_incidencia": 3, "estancados": 5 },
  "serie_diaria": [ { "fecha": "2026-08-12", "creados": 2, "entregados": 1 } ],
  "equipo": { "usuarios": 6, "activos": 6, "por_grupo": [ { "grupo": "conductor", "cantidad": 3 } ] }
}
```

- **`alcance` dice qué se está mirando.** Un conductor recibe `"propios"` y
  `equipo` en nulo: es el mismo tablero con el filtro que ya aplica el resto del
  sistema, y la pantalla lo declara para que no crea que la empresa entera mueve
  seis envíos.
- **`tasa_entrega` se calcula sobre los cerrados**, no sobre el total. Con cero
  cerrados es nula, no cero: no es lo mismo «no ha entregado nada» que «todavía
  no hay nada que medir».
- **`por_estado` incluye los estados en cero** y **`serie_diaria` los días sin
  envíos**. Omitirlos haría que el tablero cambiara de forma entre dos cargas y
  que un cero —que es información— pasara inadvertido.
- **`estancados`** son los envíos abiertos sin movimiento en más de dos días.
  Están detenidos aunque su estado no lo diga, y son el caso que se pierde de
  vista.

---

## Envíos — servicio `shipments`

### `POST /envios` — REQ-01

Grupos: `administrador`, `despachador`.

```json
{
  "origen": { "linea": "Calle 100 #15-20", "ciudad": "Bogota" },
  "destino": { "linea": "Carrera 7 #32-16", "ciudad": "Bogota" },
  "destinatario": { "nombre": "Laura Mejia Rios", "telefono": "3000000001" },
  "descripcion": "Sobre con documentos"
}
```

`201` con el envío en estado `CREADO` y su identificador UUID, más el primer
evento del histórico.

### `POST /envios/lote` — REQ-01

Grupos: `administrador`, `despachador`. Hasta 500 envíos por petición, con la
misma forma que `POST /envios`.

```json
{ "envios": [ { "origen": {...}, "destino": {...}, "destinatario": {...} } ] }
```

```json
{
  "creados": [ { "envio_id": "9a75...", "estado": "CREADO", "codigo_estado": 10 } ],
  "rechazados": [ { "indice": 4, "destinatario": "Ana Ruiz", "orden_compra": "OC-7781",
                    "motivo": "La tienda no existe en la organizacion." } ],
  "resumen": { "solicitados": 20, "creados": 19, "rechazados": 1 }
}
```

**Una fila mala no aborta el lote.** Abortarlo obligaría a corregir el archivo y
reenviarlo completo, y quien despacha doscientos envíos acabaría partiéndolo a
mano para encontrar cuál falla. El rechazo dice el índice y el motivo, que es lo
que permite corregir solo esa fila.

**La bitácora registra el lote como una operación**, con su recuento. Doscientos
eslabones por un solo despacho enterrarían el resto del histórico; cada envío ya
tiene además su propio registro de creación.

### `GET /envios/exportar`

Grupos: `administrador`, `despachador`, `conductor` (los suyos). Devuelve un CSV
con `Content-Disposition: attachment`.

Incluye `codigo_estado` **además de** `estado`: el nombre es para leer, el código
es lo que hace interpretable el archivo para un sistema que no habla español.

### `POST /envios/etiquetas`

Grupos: los cuatro. Hasta 200 envíos por petición.

```json
{ "envios": ["9a757182-...", "b31c04a7-..."] }
```

Devuelve los datos de cada guía; **la interfaz los compone e imprime**. El
servicio no genera el PDF: implicaría una dependencia de composición tipográfica
dentro de una función de computo bajo demanda, y el navegador ya sabe imprimir.
Lo que el servicio sí decide es **qué datos salen en la guía**, que es la parte
que no puede quedar en el cliente.

**La guía no lleva el valor declarado.** Va pegada a la caja y la ve cualquiera
que la manipule; imprimir cuánto vale el contenido es señalar qué paquete robar.

Cada envío se carga por el camino único de `cargar_envio`, con su filtro de
organización y de conductor: pedir guías en lote no es una vía para leer envíos
ajenos «para imprimirlos». El tope de 200 impide además que sea una forma de
vaciar la tabla en una sola llamada.

### `POST /envios/{envio_id}/asignacion`

Grupos: `administrador`, `despachador`. Transición `CREADO → ASIGNADO`.

```json
{ "conductor_sub": "u-andes-cond-1", "conductor_nombre": "Carlos Nieto" }
```

### `GET /envios`

Grupos: `administrador`, `despachador`, `conductor`. El despachador ve los de su
organización; el conductor, **solo los que tiene asignados**. El filtro lo aplica
el servidor.

### `GET /envios/{envio_id}`

Devuelve el registro maestro y sus eventos en orden cronológico, cada uno con su
código de estado.

---

## Rastreo — servicio `tracking`

### `GET /envios/{envio_id}/transiciones`

Estados alcanzables desde el estado actual. La interfaz solo ofrece esos, pero
el servidor los vuelve a comprobar: lo primero reduce errores, lo segundo es el
control.

```json
{
  "envio_id": "9a757182-...",
  "estado_actual": "ASIGNADO",
  "codigo_estado": 20,
  "estado_previo_incidencia": null,
  "transiciones": ["RECOLECTADO", "INCIDENCIA", "CANCELADO"],
  "detalle_transiciones": [
    { "estado": "RECOLECTADO", "codigo": 30, "etiqueta": "Recolectado",
      "final": false, "exige_despachador": false }
  ],
  "exige_autorizacion_despachador": false
}
```

`detalle_transiciones` lleva el código, la etiqueta y si el destino exige
despachador, para que la interfaz no tenga que deducirlo con reglas propias que
se desincronizarían del servidor.

### `POST /envios/{envio_id}/eventos` — REQ-02, REQ-03

Grupos: `conductor` (sus envíos), `despachador`. Un solo formulario y ningún
campo obligatorio más allá del estado: si registrar el avance cuesta más que
enviar un mensaje de chat, el mensajero vuelve al chat.

```json
{
  "estado": "RECOLECTADO",
  "ubicacion": { "lat": 4.68213, "lon": -74.04512 },
  "nota": "Recogido en porteria",
  "evidencia_id": null
}
```

Reglas que aplica el servicio:

- La transición se valida contra la máquina de estados; si no está contemplada,
  responde 400 y registra el intento con `motivo: transicion_invalida`.
- La marca de tiempo es la del servidor. La del dispositivo es manipulable.
- `ENTREGADO` exige una `evidencia_id` **cargada y confirmada** para ese envío.
- Reanudar desde `INCIDENCIA` exige grupo `despachador`: el conductor reporta el
  incidente, otro rol autoriza continuar.

---

## Evidencias — servicio `evidence` — REQ-05

### `POST /envios/{envio_id}/evidencias`

Grupo: `conductor`. Devuelve un enlace prefirmado acotado al prefijo de la
organización.

```json
{
  "evidencia_id": "94ad6c93...",
  "clave": "org-andes/9a757182-.../94ad6c93....jpg",
  "url": "https://...",
  "metodo": "PUT",
  "vigencia_segundos": 300,
  "encabezados": { "Content-Type": "image/jpeg", "x-amz-server-side-encryption": "aws:kms" }
}
```

El archivo se carga **directamente contra el almacenamiento** con ese enlace: no
atraviesa el servicio.

### `POST /envios/{envio_id}/evidencias/{evidencia_id}/confirmacion`

El servicio no cree al cliente: consulta el objeto en el almacenamiento y solo
entonces lo asocia al envío. Devuelve sus propiedades, incluido el estado de
cifrado y la versión.

### `GET /envios/{envio_id}/evidencias`

Grupos: `administrador`, `despachador`, `auditor`. **El conductor no puede
descargar**: carga la prueba de entrega, consultarla corresponde a otros roles.

---

## Consulta pública — servicio `public` — REQ-04

### `GET /publico/envios/{envio_id}`

**Sin autenticación.** Es el único punto del sistema que responde sin token, y
por eso concentra dos controles: el identificador aleatorio y la vista reducida.

```json
{
  "envio": {
    "envio_id": "9a757182-...",
    "estado": "ENTREGADO",
    "destino_ciudad": "Bogota",
    "destinatario_nombre": "Laura M. R."
  },
  "eventos": [
    { "estado": "CREADO", "ts": "...", "nota": "", "tiene_evidencia": false },
    { "estado": "ENTREGADO", "ts": "...", "nota": "", "tiene_evidencia": true }
  ]
}
```

Lo que **no** devuelve: identificador de organización, identidad del mensajero,
dirección de origen, coordenadas, ni el nombre completo del destinatario. El
nombre se enmascara por minimización de datos.

Un identificador que no sea un UUID canónico responde 422 sin llegar a consultar
el almacenamiento.

---

## Bitácora — servicio `audit` — REQ-07, REQ-08

**Este servicio no expone ninguna operación de escritura.** Los eslabones los
escriben los demás servicios como efecto de sus operaciones; ningún usuario, ni
siquiera el administrador, puede añadir o corregir un registro por esta vía.

### `GET /bitacora`

Grupo: `auditor` únicamente. Parámetros: `limite` (1–2000), `resultado`
(`ALLOW` | `DENY` | `ERROR`).

La consulta del auditor también deja rastro: quién revisó y cuándo.

### `GET /bitacora/verificacion`

Grupo: `auditor`. Recalcula la cadena completa.

```json
{
  "cadena_valida": false,
  "registros_verificados": 32,
  "punto_de_ruptura": {
    "tipo": "CONTENIDO_ALTERADO",
    "seq": 12,
    "descripcion": "El contenido del registro no corresponde a su hash."
  }
}
```

El criterio de aceptación tiene dos sentidos: sobre una bitácora íntegra debe
informar cadena válida, y tras una alteración controlada debe señalar dónde se
rompió. Comprobar solo lo primero no demuestra que el verificador sirva.

---

## Estado de los servicios

`GET /salud` en cada servicio devuelve nombre, versión, entorno y región.
`GET /salud` en la puerta de enlace confirma que está activa.

---

## Reparto de rutas

En local lo hace nginx por prefijo; en AWS, las rutas de API Gateway. El reparto
es el mismo, de modo que la interfaz web funciona contra cualquiera de los dos.

| Patrón | Servicio |
|---|---|
| `/auth/*`, `/usuarios*`, `/empresa`, `/equipo/*`, `/roles*` | `auth` |
| `/publico/*` | `public` |
| `/bitacora*` | `audit` |
| `/tablero` | `dashboard` |
| `/catalogos/*`, `/tiendas*`, `/clientes*`, `/transportistas*` | `masters` |
| `/envios/{id}/eventos`, `/envios/{id}/transiciones` | `tracking` |
| `/envios/{id}/evidencias*` | `evidence` |
| `/envios*` (resto, incluidos `/envios/lote`, `/envios/exportar` y `/envios/etiquetas`) | `shipments` |

**El orden de los patrones importa.** `/envios/lote` tiene que llegar a
`shipments` y no confundirse con `/envios/{id}/…`; por eso las reglas de rastreo
y evidencias son expresiones regulares ancladas al identificador y no prefijos.

**nginx resuelve el nombre del servicio en cada petición**, con
`resolver 127.0.0.11` y `proxy_pass http://$destino`. Con `proxy_pass` a un
nombre literal, nginx resuelve la dirección **al cargar la configuración** y la
conserva: al recrear un contenedor, su dirección cambia y la puerta de enlace
sigue enviando peticiones a la anterior. El síntoma es un 404 en rutas que
existen, y cuesta bastante de diagnosticar.


---

# API del programa de auditoría (Cotejo)

Base local: `http://localhost:8007`. Es un **servicio distinto** del de Rastro:
otro proyecto, otro puerto, otro almacén.

**Toda operación salvo `/salud` exige un token del grupo `auditor`.** Se valida
el mismo token que emite el proveedor de identidad de Rastro: el auditor es un
usuario de la organización auditada. Un despachador con token válido recibe 403.

El almacén de papeles de trabajo concentra información sobre las debilidades del
sistema auditado; su lectura restringida es un control, no una formalidad.

## Operaciones

### `GET /salud` — sin autenticación

```json
{
  "servicio": "cotejo-api",
  "sistema_auditado": "Rastro",
  "entorno": "local",
  "url_auditada": "http://gateway:80",
  "controles_en_catalogo": 8,
  "catalogo": "cargado"
}
```

### `GET /catalogo`

Los ocho controles con marco, tipo, procedimiento, criterio, evidencia esperada y
severidad, más los hallazgos permanentes con su nota de alcance.

El criterio se devuelve tal como está declarado en el catálogo, **antes** de
ejecutar nada: es lo que impide acomodarlo al resultado.

### `POST /ejecuciones`

Recorre el catálogo completo en una sola invocación.

```json
{ "solo": ["C-05", "C-06"] }
```

`solo` es opcional; vacío ejecuta todo. Devuelve `201` con la cobertura, el
resultado por control y los hallazgos.

Un fallo en un control no detiene el resto: queda marcado como `NO_EJECUTADA` con
su motivo.

### `GET /ejecuciones` · `GET /ejecuciones/{id}`

Listado de ejecuciones almacenadas y detalle de una, con `cobertura`,
`controles` y `hallazgos`.

La cobertura distingue tres cosas que no deben confundirse:

```json
{
  "controles_del_catalogo": 8,
  "controles_con_resultado": 5,
  "conformes": 5,
  "desviados": 0,
  "no_ejecutados": 3,
  "cobertura": "5/8"
}
```

**Un control no ejecutado no es un control conforme.**

### `GET /ejecuciones/{id}/papeles/{control}`

La evidencia literal, con la huella recalculada en el momento:

```json
{
  "contenido": { "procedimiento": "...", "observaciones": [...] },
  "huella_registrada": "3f2a...",
  "huella_recalculada": "3f2a...",
  "coincide": true
}
```

La huella se recalcula al leer, no se copia del índice: así abrir el papel sirve
además como comprobación de que nadie lo editó.

### `POST /ejecuciones/{id}/verificacion`

Recalcula todas las huellas del almacén.

```json
{
  "almacen_integro": false,
  "papeles_verificados": 8,
  "discrepancias": [
    { "control_id": "C-05", "tipo": "HUELLA_DISCORDANTE", "archivo": "evidencias/C-05.json" }
  ]
}
```

Tipos posibles: `HUELLA_DISCORDANTE` (el archivo se editó) y `ARCHIVO_AUSENTE`
(se borró).

El almacén **detecta** la manipulación; no la previene. Prometer prevención donde
solo hay detección sería una afirmación que la evidencia no sostiene.

### `GET /comparacion?a=&b=`

Compara la clasificación de dos ejecuciones.

```json
{
  "reproducible": true,
  "controles_comparados": 8,
  "coincidencias": 8,
  "diferencias": []
}
```

Se comparan las conclusiones y no las huellas: cada ejecución tiene su propia
marca de tiempo y, por lo tanto, su propia huella. Lo que debe reproducirse es el
juicio sobre cada control, no el byte.

### `GET /ejecuciones/{id}/informe.txt`

El informe completo en texto plano, con alcance, resultado por control,
hallazgos y limitaciones declaradas.

## Seguridad de las rutas

Los identificadores de ejecución y de control se validan contra recorrido de
directorios: uno con `/`, `\` o `..` se rechaza antes de tocar el sistema de
archivos.
