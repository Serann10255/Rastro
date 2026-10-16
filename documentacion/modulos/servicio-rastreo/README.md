# Servicio `tracking` — puntos de control y rutas de entrega

Ubicación: `services/tracking/` · Puerto local: 8003

## Qué hace

Registra los puntos de control del envío y aplica la máquina de estados.

| Operación | Requisito |
|---|---|
| `GET /envios/{id}/transiciones` | — |
| `POST /envios/{id}/eventos` | REQ-02, REQ-03 |
| `POST /rutas`, `GET /rutas`, `GET /rutas/activa`, `GET /rutas/{id}` | Rutas de entrega |
| `POST /rutas/{id}/posiciones`, `POST /rutas/{id}/finalizacion` | Rutas de entrega |

Las rutas de entrega —el conductor sale con sus guías y comparte su ubicación—
están documentadas en su propio módulo:
[rutas de entrega](../rutas-de-entrega/README.md). Viven en este servicio porque
mueven envíos por la máquina de estados igual que un punto de control; separarlas
obligaría a dos servicios a escribir el mismo estado de un envío.

## La máquina de estados

```
CREADO → ASIGNADO → RECOLECTADO → EN_TRANSITO → EN_REPARTO → ENTREGADO
   │         │            │             │            │
   └─────────┴────────────┴─────────────┴────────────┴──→ INCIDENCIA
                                                              │
                        reanudación autorizada por despachador ┘
```

`ENTREGADO` es final. `INCIDENCIA` conserva el estado desde el que se entró, para
poder reanudar hacia él o hacia el siguiente del flujo.

## Decisiones

**La marca de tiempo es la del servidor.** La del dispositivo del mensajero es
manipulable y por lo tanto no sirve como evidencia.

**Reanudar tras una incidencia exige grupo despachador.** El conductor reporta el
incidente, otro rol autoriza continuar: es una separación de funciones deliberada
sobre la operación más sensible del proceso.

**`ENTREGADO` exige una evidencia cargada y confirmada.** No basta con que el
cliente envíe un identificador: debe estar en la lista de evidencias confirmadas
del envío. Cubierto por
`test_una_evidencia_declarada_pero_no_cargada_no_acredita_la_entrega`.

**Un solo formulario, sin campos obligatorios más allá del estado.** La
viabilidad operativa depende de que registrar el avance sea más rápido que
enviar un mensaje de chat. Si exige más pasos, el mensajero vuelve al chat y el
sistema deja de tener datos.

**La interfaz solo ofrece los estados alcanzables, y el servidor los vuelve a
comprobar.** Lo primero reduce errores; lo segundo es el control. Lo primero no
sustituye a lo segundo.

**Salir a ruta no abre atajos en la máquina de estados.** Cada guía llega a
`EN_REPARTO` registrando cada paso del flujo principal como su propio evento.
Los eventos encadenados de una misma salida se separan un milisegundo: con la
misma marca de tiempo, el histórico podía mostrar el reparto antes que el
tránsito ([ADR-013](../../decisiones/adr-013-ubicacion-en-vivo-por-sondeo.md)).

**Un punto de control de un envío en ruta actualiza su parada.** Es una copia
para el mapa de seguimiento; si falla, el registro del punto de control no se
revierte, porque el estado que vale es el del envío.

## Dependencias y relaciones

- **Depende de**: `rastro_core` (estados, dominio, autorización, repositorio).
- **Coopera con** `evidence`: la entrega solo se acepta si la evidencia quedó
  confirmada allí.
- **Coopera con** `public`: la consulta pública lee la última posición de la
  ruta que lleva el envío.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
