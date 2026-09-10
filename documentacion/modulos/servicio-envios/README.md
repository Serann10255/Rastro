# Servicio `shipments` — envíos

Ubicación: `services/shipments/` · Puerto local: 8002

## Qué hace

Registro, asignación y consulta autenticada de envíos dentro de una organización.

| Operación | Grupos | Requisito |
|---|---|---|
| `POST /envios` | administrador, despachador | REQ-01 |
| `POST /envios/lote` | administrador, despachador | REQ-01 |
| `POST /envios/{id}/asignacion` | administrador, despachador | — |
| `GET /envios` | administrador, despachador, conductor | — |
| `GET /envios/{id}` | los cuatro grupos | — |
| `GET /envios/exportar` | administrador, despachador, conductor | — |
| `POST /envios/etiquetas` | los cuatro grupos | — |

## Decisiones

**El identificador es un UUID v4, no un consecutivo.** Es un control de
seguridad: véase [ADR-003](../../decisiones/adr-003-identificador-aleatorio.md).

**La organización nunca llega en el cuerpo de la petición**, siempre del token.
Aceptarla del cliente permitiría que un usuario escribiera en otra organización.

**El servicio no decide qué transiciones son válidas**: se lo pregunta a
`state_machine`. La asignación es la transición `CREADO → ASIGNADO` y se valida
igual que cualquier otra.

**El conductor ve solo sus envíos.** El filtro se aplica en el servidor
(`exige_envio_propio`), no en la interfaz.

**El registro masivo acepta éxitos parciales.** Una fila inválida no aborta el
lote: se rechaza esa y las demás se registran, y la respuesta devuelve las dos
listas. Abortar el lote entero por un teléfono mal escrito obligaría a corregir
y reenviar cien envíos por culpa de uno, y en la práctica lleva a que el operador
divida el archivo en lotes de uno.

**El lote deja una sola entrada en la bitácora**, con el recuento de aceptados y
rechazados, no una por envío. Cada envío ya tiene su propio registro de creación;
duplicarlo por el hecho de venir en lote llenaría la bitácora de ruido que
esconde lo que importa.

**Las etiquetas se cargan una por una aunque se pidan en bloque.** Cada envío
pasa por `cargar_envio`, que aplica el filtro de organización y de conductor. Si
el punto de etiquetas leyera directamente de la tabla, sería una puerta trasera
para leer envíos ajenos pidiéndolos «para imprimir». El tope de 200 por petición
está para que tampoco sea una forma de vaciar la tabla en una sola llamada.

**La etiqueta no lleva el valor declarado.** Va pegada a la caja y la ve
cualquiera que la manipule; imprimir cuánto vale el contenido es señalar qué
paquete robar. La decisión vive en `dominio.datos_de_etiqueta`, no en la
pantalla, para que ninguna interfaz futura pueda saltársela.

**La exportación incluye el código de estado además del nombre.** Es lo que hace
que el archivo sirva para integrarse: el nombre es para leer, el código es para
procesar.

## Dependencias y relaciones

- **Depende de**: `rastro_core` (dominio, autorización, repositorio, estados).
- **Comparte tablas** con `tracking`, `evidence`, `public` y `audit`: lo que se
  aísla no son los servicios entre sí, sino los datos de cada organización.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
