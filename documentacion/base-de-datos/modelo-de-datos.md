# Modelo de datos

Fecha: 2026-09-10 · Versión: 0.1

Dos tablas en DynamoDB. La primera guarda envíos y eventos juntos; la segunda,
la bitácora de auditoría. El modelo es de tabla única en la primera porque el
acceso dominante es *dame un envío con todo su histórico en orden*, y eso se
resuelve con una sola consulta.

---

## Tabla `rastro-envios`

Guarda el registro maestro del envío y sus eventos bajo la misma clave de
partición.

### Claves

| Clave | Composición | Ejemplo |
|---|---|---|
| Partición (`pk`) | `ORG#<org_id>#ENV#<envio_id>` | `ORG#org-andes#ENV#9a757182-0d1a-...` |
| Ordenamiento (`sk`) — maestro | `META` | `META` |
| Ordenamiento (`sk`) — evento | `EVT#<ts>#<evento_id>` | `EVT#2026-09-10T17:31:50.427Z#a1b2c3d4` |

La organización forma parte de la clave de partición. No es una convención de
nombres: es el mecanismo de aislamiento. Los datos de cada empresa quedan en
particiones distintas y **no existe forma de construir una clave sin
organización** — `claves.py` lanza un error si falta.

La marca de tiempo va en formato ISO-8601 UTC, que es ordenable
lexicográficamente. Por eso el histórico completo sale en orden cronológico sin
ordenar en memoria.

### Índices secundarios

| Índice | Partición | Ordenamiento | Para qué |
|---|---|---|---|
| `gsi_org` | `ORG#<org_id>` | `ENV#<creado_en>#<envio_id>` | Listar los envíos de una organización, del más reciente al más antiguo |
| `gsi_publico` | `ENV#<envio_id>` | igual que `sk` | Consulta pública por identificador (REQ-04) |

**Por qué existe `gsi_publico`.** El destinatario solo tiene el identificador del
envío; no conoce la organización, y no debería. Sin este índice, la consulta
pública tendría que recorrer particiones o exigir que el enlace incluyera el
identificador de la empresa. El índice lo resuelve sin abrir las particiones
autenticadas, y el servicio público devuelve una **vista reducida**: el avance
del envío, no la operación de la empresa.

### Atributos del registro maestro

| Campo | Tipo | Notas |
|---|---|---|
| `envio_id` | texto | UUID v4. Es un control, no una convención (véase abajo) |
| `org_id` | texto | Viaja en el token; nunca en el cuerpo de la petición |
| `estado` | texto | Uno de los siete estados de la máquina |
| `estado_previo_incidencia` | texto \| ausente | Desde dónde se entró en INCIDENCIA, para poder reanudar |
| `creado_en`, `actualizado_en` | texto | ISO-8601 UTC del servidor |
| `creado_por` | texto | Sujeto del token del despachador |
| `conductor_sub`, `conductor_nombre` | texto | Mensajero asignado |
| `origen`, `destino` | mapa | `linea`, `ciudad`, `referencia` |
| `destinatario` | mapa | `nombre`, `telefono` |
| `evidencias` | lista | Identificadores de evidencia confirmados |

### Atributos de un evento

| Campo | Tipo | Notas |
|---|---|---|
| `evento_id` | texto | Sufijo corto que desempata eventos con la misma marca |
| `estado`, `estado_anterior` | texto | La transición efectiva |
| `ts` | texto | **Marca del servidor.** La del dispositivo es manipulable |
| `actor_sub`, `actor_email`, `actor_grupos` | texto / lista | Quién lo produjo |
| `ubicacion` | mapa \| ausente | `lat`, `lon` |
| `nota` | texto | Opcional |
| `evidencia_id` | texto \| ausente | Enlaza el evento con su prueba de entrega |

### Por qué el identificador es un UUID y no un consecutivo

Con numeración secuencial, cualquiera podría recorrer los identificadores
contiguos desde el punto de consulta público y obtener los envíos de toda la
empresa. Es la *referencia directa insegura a objetos* incluida en A01:2021 de
OWASP. El identificador aleatorio es un control de seguridad.

El servicio público refuerza esa decisión validando el formato antes de
consultar: un identificador que no sea un UUID canónico se rechaza con 422 y no
llega a producir una lectura del almacenamiento.

---

## Tabla `rastro-bitacora`

Una cadena independiente por organización.

### Claves

| Clave | Composición | Ejemplo |
|---|---|---|
| Partición (`pk`) | `ORG#<org_id>` | `ORG#org-andes` |
| Ordenamiento (`sk`) | `SEQ#<seq con 12 dígitos>` | `SEQ#000000000042` |

El ancho fijo de la secuencia conserva el orden lexicográfico: sin él,
`SEQ#10` iría antes que `SEQ#9`.

### Atributos

| Campo | Firmado | Notas |
|---|---|---|
| `org_id`, `seq`, `ts` | sí | Identidad y posición del registro en la cadena |
| `actor_sub`, `actor_email`, `actor_grupos` | sí | **Quién** |
| `accion` | sí | **Qué acción** |
| `recurso` | sí | **Sobre qué recurso** |
| `resultado` | sí | `ALLOW`, `DENY` o `ERROR` |
| `detalle` | sí | Motivo del rechazo, estado anterior, contadores |
| `hash_previo` | no | Hash del registro anterior; el primero usa 64 ceros |
| `hash` | no | `SHA-256(hash_previo ‖ contenido_canónico)` |

Los cuatro campos marcados en negrita son la cuádrupla que Kent y Souppaya
(2006) fijan como mínimo de un registro de auditoría útil.

### Contenido canónico

El hash se calcula sobre una serialización determinista: JSON con claves
ordenadas, separadores sin espacios, sin escapar caracteres no ASCII y con
`actor_grupos` ordenado. Dos implementaciones distintas del verificador obtienen
la misma cadena, que es lo que permite que un tercero repita la verificación.

**El orden de los campos firmados es parte del procedimiento.** Cambiarlo
invalida todas las cadenas existentes.

### Qué detecta el verificador

| Manipulación | Cómo se detecta |
|---|---|
| Contenido modificado | El hash recalculado no coincide con el almacenado → `CONTENIDO_ALTERADO` |
| Contenido modificado y hash reparado | El registro siguiente ya no enlaza → `ENCADENAMIENTO_ROTO` |
| Registro intermedio eliminado | Salto en la secuencia → `SECUENCIA_INCOMPLETA` |

El segundo caso es el que da valor al encadenamiento: reparar un eslabón obliga
a recalcular todos los posteriores.

### Escrituras concurrentes

Dos operaciones simultáneas pueden leer el mismo hash previo. El documento del
proyecto declara esa limitación como aceptada para el volumen previsto. La
implementación la acota con una escritura condicional sobre la unicidad de la
secuencia (`attribute_not_exists`) y un reintento limitado: la segunda escritura
no sobrescribe a la primera, recalcula su eslabón. Es una mejora sobre lo
declarado, no una garantía de serialización total.

---

## Almacenamiento de evidencias

| Elemento | Valor |
|---|---|
| Contenedor | `rastro-evidencias-<número de cuenta>` |
| Clave del objeto | `<org_id>/<envio_id>/<evidencia_id>.<ext>` |
| Cifrado | `aws:kms` con la llave del proyecto, referenciada por alias |
| Versionado | Activo |
| Acceso público | Bloqueado en los cuatro indicadores |

El prefijo por organización no es organizativo: los enlaces prefirmados se
emiten acotados a él, de modo que un enlace no puede apuntar a los datos de otra
empresa. `storage.py` comprueba el prefijo en cada lectura y responde *no
encontrado* —nunca *no autorizado*— si no coincide.

Una política del contenedor rechaza toda carga sin cabecera de cifrado. El
cifrado por omisión cubre al cliente distraído; la política cubre al deliberado.

---

## Diferencias del entorno local

| Control | En AWS | En local (MinIO / DynamoDB Local) |
|---|---|---|
| Cifrado con llave administrada | Sí | **No existe KMS** |
| Versionado del contenedor | Sí | Sí |
| Bloqueo de acceso público | Sí | **Operación no implementada** |
| Registro de actividad | CloudTrail | **No existe** |

Estas diferencias se declaran en lugar de simularse. Cotejo marca los controles
correspondientes como *no ejecutados* cuando corre en local, nunca como
conformes: presentar la ausencia de una capacidad como conformidad sería el peor
resultado posible de un trabajo de aseguramiento.
