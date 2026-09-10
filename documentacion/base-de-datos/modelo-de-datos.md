# Modelo de datos

Fecha: 2026-09-10 · Versión: 0.2

Tres tablas en DynamoDB. La primera guarda envíos y eventos juntos; la segunda,
la bitácora de auditoría; la tercera, los datos maestros de cada organización
—empresa, usuarios, tiendas, clientes y transportistas—. Las tres son de tabla
única: en envíos porque el acceso dominante es *dame un envío con todo su
histórico en orden*, y en maestros porque el acceso dominante es *dame todo lo
que define a esta organización*. Ambas cosas se resuelven con una sola consulta.

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
| `estado` | texto | Uno de los nueve estados de la máquina |
| `codigo_estado` | número | Código del catálogo (10…90). Se guarda **además** del nombre (véase abajo) |
| `estado_previo_incidencia` | texto \| ausente | Desde dónde se entró en INCIDENCIA, para poder reanudar |
| `creado_en`, `actualizado_en` | texto | ISO-8601 UTC del servidor |
| `creado_por` | texto | Sujeto del token del despachador |
| `conductor_sub`, `conductor_nombre` | texto | Mensajero asignado |
| `origen`, `destino` | mapa | `linea`, `ciudad`, `referencia` |
| `destinatario` | mapa | `nombre`, `telefono` |
| `evidencias` | lista | Identificadores de evidencia confirmados |
| `orden_compra` | texto | Referencia del cliente. **No es identificador**: la genera él y puede repetirse |
| `tienda_id`, `tienda_nombre` | texto | De dónde sale. El nombre se copia al registrar (véase abajo) |
| `cliente_id`, `cliente_nombre` | texto | Quién despacha |
| `transportista_id`, `transportista_nombre` | texto | Quién lo mueve |
| `peso_kg`, `bultos` | número | `peso_kg` se almacena como `Decimal` (véase abajo) |
| `valor_declarado` | número | Se guarda; **no se imprime en la etiqueta** |
| `fecha_estimada` | texto | Fecha comprometida. El sistema no la calcula: la fija quien vende el servicio |
| `observaciones` | texto | Libre, para la operación |
| `estacion_actual` | texto | Última estación por la que pasó, si la operación las usa |

**El código del estado se guarda además del nombre.** Es duplicación
controlada: el nombre es para leer y el código es lo que viaja en los archivos de
intercambio con transportistas y clientes, donde un texto con tildes es frágil.
Ambos se escriben en la misma operación, siempre desde el catálogo
(`state_machine.codigo_de`), nunca a mano; ningún camino permite escribir uno sin
el otro.

**El nombre del maestro se copia en el envío.** Es duplicación deliberada: si la
tienda cambia de nombre el año que viene, un envío del año pasado tiene que
seguir diciendo desde dónde salió *entonces*. Guardar solo el identificador haría
que la historia se reescribiera sola cada vez que se corrige un maestro, y eso
contradice lo que el sistema promete. El identificador se guarda igualmente, para
poder llegar al maestro actual cuando lo que se quiere es el dato de hoy.

**Las referencias se validan al registrar.** Un `tienda_id` inventado produciría
un envío que apunta a una tienda inexistente, y el problema solo aparece meses
después, al intentar reconstruir de dónde salió.

**DynamoDB no acepta `float`.** Peso, valor y coordenadas llegan como decimales
desde la interfaz y se convierten a `Decimal` al escribir y de vuelta al leer, en
`repository.py`. La conversión pasa por texto (`Decimal(str(valor))`) y no por el
binario del flotante: `Decimal(0.1)` guardaría los diecisiete dígitos del error
de representación.

### Atributos de un evento

| Campo | Tipo | Notas |
|---|---|---|
| `evento_id` | texto | Sufijo corto que desempata eventos con la misma marca |
| `estado`, `estado_anterior` | texto | La transición efectiva |
| `codigo_estado` | número \| ausente | Código del catálogo, para los archivos de intercambio |
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

## Tabla `rastro-maestros`

Todo lo que define a una organización vive en una sola partición: la empresa,
sus usuarios y sus catálogos. El acceso dominante es *dame todo lo de esta
organización*, y con este diseño es una consulta.

### Claves

| Clave | `pk` | `sk` | Contenido |
|---|---|---|---|
| Empresa | `ORG#<org_id>` | `PERFIL` | Razón social, NIT, ciudad, contacto |
| Usuario | `ORG#<org_id>` | `USR#<correo>` | Cuenta, grupos, hash de contraseña, sesiones |
| Tienda | `ORG#<org_id>` | `TIENDA#<id>` | Tienda, almacén o estación de origen |
| Cliente | `ORG#<org_id>` | `CLIENTE#<id>` | Cliente remitente |
| Transportista | `ORG#<org_id>` | `TRANSP#<id>` | Propio o tercero |
| Módulo | `ORG#<org_id>` | `MODULO#<clave>` | Qué módulos tiene la empresa y cuáles no, con el motivo |
| Rol | `ORG#<org_id>` | `ROL#<clave>` | Qué operaciones concede cada rol de la empresa |

**El correo forma parte de la clave del usuario**, no un identificador
generado. Es lo que hace imposible tener dos cuentas con el mismo correo en una
organización sin necesidad de una comprobación aparte que alguien pueda olvidar.
El `sub` del token es un identificador propio y estable, porque el correo puede
corregirse y los envíos ya registrados apuntan al `sub`.

### Índice secundario

| Índice | Partición | Para qué |
|---|---|---|
| `gsi_email` | `EMAIL#<correo>` | Encontrar al usuario por correo **sin conocer su organización** |

**Por qué existe.** En el inicio de sesión el usuario escribe su correo y no
sabe —ni tiene por qué saber— a qué organización pertenece. Sin este índice, la
pantalla de acceso tendría que pedir la empresa, que es exactamente el dato que
un atacante querría confirmar.

Es **la única consulta del sistema sin filtro por organización**, y está acotada
a un punto: devuelve el registro, del registro sale el `org_id`, y desde ahí todo
vuelve a filtrarse por organización como el resto del sistema.

### Atributos del usuario

| Campo | Notas |
|---|---|
| `sub` | Identificador estable. Es lo que va en el token y en los envíos |
| `correo`, `nombre`, `telefono` | El correo se normaliza a minúsculas antes de usarse como clave |
| `org_id` | Organización a la que pertenece |
| `grupos` | Lista ordenada y en minúsculas. Al menos uno |
| `hash_clave` | `pbkdf2_sha256$<iteraciones>$<sal>$<hash>`. **Nunca la contraseña** |
| `activo` | Desactivar cierra sus sesiones de inmediato |
| `sesiones` | Sesiones abiertas, cada una con identificador y caducidad |
| `creado_en`, `actualizado_en`, `ultimo_acceso` | ISO-8601 UTC |
| `gsi_email_pk` | Clave del índice de arriba |

**El hash lleva delante su algoritmo y su coste.** Por eso migrar a otro
algoritmo no invalida las contraseñas existentes: se rederivan al iniciar
sesión, que es el único momento en que el sistema la tiene en claro.

**El registro nunca sale entero del servicio.** `vista_usuario` retira
`hash_clave` y `gsi_email_pk` antes de responder. La omisión se hace en el
repositorio y no en cada punto de la API, para que añadir un punto nuevo no sea
una oportunidad de filtrarlo.

### Atributos de un módulo

| Campo | Notas |
|---|---|
| `clave` | Identificador estable en minúsculas: `ordenes`, `rutas`, `facturacion` |
| `nombre`, `descripcion` | Lo que se lee en la pantalla |
| `icono` | **El nombre** del icono, no el dibujo. La interfaz lo resuelve contra su juego de trazados |
| `ruta` | A dónde lleva. Obligatoria si el módulo está disponible |
| `grupos` | Quién lo ve. No es un control: el servidor decide en cada operación |
| `orden`, `destacado` | Posición, y si sube a la navegación principal o se queda en el menú de operaciones |
| `disponible`, `motivo` | Si está encendido y, cuando no lo está, **por qué** |

**Los módulos son datos de la organización, no una constante del programa.** Una
empresa puede tener contratada la operación y no la auditoría, y la interfaz
tiene que reflejarlo sin recompilarse. La decisión completa está en
[ADR-009](../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md).

**Apagar exige motivo y encender exige ruta.** Las dos reglas viven en el
repositorio y no en la pantalla, de modo que las encuentra cualquier vía de
escritura. Un módulo apagado sin motivo parece un olvido; uno encendido sin ruta
es una tarjeta que no hace nada al pulsarla, y eso se lee como un fallo.

**El aprovisionamiento respeta lo que la organización decidió.** Al volver a
sembrar, `disponible` y `motivo` se conservan: volver a encender en cada
despliegue un módulo que un administrador apagó convertiría una decisión de la
empresa en algo que el sistema deshace a sus espaldas.

### Atributos de un rol

| Campo | Notas |
|---|---|
| `clave` | Identificador estable en minúsculas. **No se cambia**: es lo que guardan las cuentas |
| `nombre`, `descripcion` | Lo que se lee al asignar el rol a alguien |
| `operaciones` | Lista de operaciones del catálogo del código. Nada más se acepta |
| `integrado` | Si es uno de los cinco de fábrica. No se elimina, aunque sí se ajusta |
| `editable` | Falso solo en `administrador` |

**El catálogo de operaciones no está aquí: está en el código.** Un rol es una
*selección* de lo que el sistema ya sabe hacer, nunca una invención. Escribir
`sistema:todo` en este registro no concede nada, y la API lo rechaza por su
nombre. Razonamiento en
[ADR-010](../decisiones/adr-010-roles-configurables.md).

**El registro de `administrador` se ignora.** Aunque exista en la tabla —por un
error o a propósito—, el sistema aplica la definición del código: todas las
operaciones salvo la bitácora. Es el seguro contra que una edición deje a una
organización sin nadie que pueda entrar a deshacerla.

**Ningún rol puede combinar `bitacora:*` con operaciones de escritura**, y
ninguna cuenta puede sumar dos roles que juntos lo hagan. Quien revisa el
registro no puede ser quien lo produce.

**Eliminar un maestro es desactivarlo.** Los envíos históricos apuntan a tiendas
y clientes; borrarlos dejaría registros apuntando a nada y falsearía la
trazabilidad, que es justamente lo que el sistema promete.

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
