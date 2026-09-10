# Contratos de la interfaz de programación

Fecha: 2026-09-10 · Versión: 0.2

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

## Autenticación — servicio `auth`

> En AWS este servicio no se despliega: lo sustituye Amazon Cognito. El contrato
> del token es el mismo, y por eso es sustituible.

### `POST /auth/token`

```json
{ "usuario": "despacho@andes.test", "clave": "Andes.2026" }
```

```json
{
  "token": "eyJhbGciOi...",
  "tipo": "Bearer",
  "vigencia_segundos": 3600,
  "usuario": {
    "sub": "u-andes-desp", "nombre": "Diego Rojas",
    "email": "despacho@andes.test", "org_id": "org-andes",
    "grupos": ["despachador"]
  }
}
```

Ante credenciales inválidas responde 401 con **el mismo mensaje** tanto si el
usuario no existe como si la clave es incorrecta: distinguirlos permitiría
enumerar las cuentas del sistema.

### `GET /auth/yo`

Devuelve la identidad que transporta el token en uso.

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

Devuelve el registro maestro y sus eventos en orden cronológico.

---

## Rastreo — servicio `tracking`

### `GET /envios/{envio_id}/transiciones`

Estados alcanzables desde el estado actual. La interfaz solo ofrece esos, pero
el servidor los vuelve a comprobar: lo primero reduce errores, lo segundo es el
control.

```json
{
  "estado_actual": "ASIGNADO",
  "transiciones": ["INCIDENCIA", "RECOLECTADO"],
  "exige_autorizacion_despachador": false
}
```

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
| `/auth/*` | `auth` |
| `/publico/*` | `public` |
| `/bitacora*` | `audit` |
| `/envios/{id}/eventos`, `/envios/{id}/transiciones` | `tracking` |
| `/envios/{id}/evidencias*` | `evidence` |
| `/envios*` (resto) | `shipments` |


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
