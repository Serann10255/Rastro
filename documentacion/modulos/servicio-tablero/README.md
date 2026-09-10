# Servicio `dashboard` — tablero de operación

Ubicación: `services/dashboard/` · Puerto local: 8009

## Qué hace

Un solo punto: `GET /tablero?dias=N` (1 a 365, 30 por omisión). Devuelve los
indicadores de la organización del token: totales, tasa de entrega, desglose por
estado y por fase, lo que requiere atención hoy, la serie diaria de la ventana y
el resumen del equipo.

## Decisiones

**Los cálculos se hacen en el servicio, no en la interfaz.** Un tablero
calculado en el cliente obliga a enviarle todos los envíos: es a la vez lento y
una entrega de datos que la pantalla no necesita mostrar.

**Ningún indicador cruza la frontera de organización.** Ni siquiera un total,
porque un total también es información: saber cuántos envíos mueve la competencia
es un dato de negocio.

**El conductor ve el mismo tablero acotado a sus envíos.** No es un tablero
distinto —eso serían dos cosas que mantener— sino el mismo con el filtro que ya
aplica el resto del sistema. La respuesta lo declara en `alcance`, para que la
pantalla pueda decirlo en lugar de que el conductor crea que la empresa entera
mueve seis envíos. Y `equipo` va en nulo: quién más trabaja en la empresa no es
asunto suyo.

**La tasa de entrega se calcula sobre los envíos cerrados, no sobre el total.**
Incluir los que siguen en curso la hunde artificialmente a primera hora de la
mañana y no dice nada útil. Con cero cerrados la tasa es nula, no cero: no es lo
mismo «no ha entregado nada» que «todavía no hay nada que medir».

**El desglose por estado incluye los estados en cero.** Mostrar solo los que
tienen envíos haría que el tablero cambiara de forma entre una carga y otra, y
que un estado vacío —que es información— pasara inadvertido.

**La serie diaria incluye los días sin envíos.** Por lo mismo: una serie con
huecos se dibuja mal y miente sobre la tendencia.

**«Estancados» mira la fecha de actualización, no el estado.** Un envío abierto
sin movimiento en más de dos días está detenido aunque su estado no lo diga. Es
justamente el caso que se pierde de vista, y por eso el tablero lo nombra.

**Límite de 2000 envíos por consulta.** Es un tope explícito, no un descuido: por
encima de ese volumen los indicadores deberían mantenerse incrementalmente en
vez de recalcularse en cada carga. Está dicho para que quien lo alcance sepa qué
cambiar.

## Dependencias y relaciones

- **Depende de**: `rastro_core.repository` (listado con filtro de organización
  obligatorio), `rastro_core.state_machine` (catálogo y fases),
  `rastro_core.maestros` (empresa y usuarios) y `rastro_core.authz`.
- **Solo lee.** No escribe envíos; sí deja constancia de la consulta en la
  bitácora, como cualquier otra operación.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz. La pantalla que lo consume es
`web/src/paginas/Panel.tsx`, documentada en
[interfaz-web](../interfaz-web/README.md).
