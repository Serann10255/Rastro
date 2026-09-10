# Servicio `shipments` — envíos

Ubicación: `services/shipments/` · Puerto local: 8002

## Qué hace

Registro, asignación y consulta autenticada de envíos dentro de una organización.

| Operación | Grupos | Requisito |
|---|---|---|
| `POST /envios` | administrador, despachador | REQ-01 |
| `POST /envios/{id}/asignacion` | administrador, despachador | — |
| `GET /envios` | administrador, despachador, conductor | — |
| `GET /envios/{id}` | los cuatro grupos | — |

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

## Dependencias y relaciones

- **Depende de**: `rastro_core` (dominio, autorización, repositorio, estados).
- **Comparte tablas** con `tracking`, `evidence`, `public` y `audit`: lo que se
  aísla no son los servicios entre sí, sino los datos de cada organización.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
