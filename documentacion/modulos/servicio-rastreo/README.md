# Servicio `tracking` — puntos de control

Ubicación: `services/tracking/` · Puerto local: 8003

## Qué hace

Registra los puntos de control del envío y aplica la máquina de estados.

| Operación | Requisito |
|---|---|
| `GET /envios/{id}/transiciones` | — |
| `POST /envios/{id}/eventos` | REQ-02, REQ-03 |

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

## Dependencias y relaciones

- **Depende de**: `rastro_core` (estados, dominio, autorización, repositorio).
- **Coopera con** `evidence`: la entrega solo se acepta si la evidencia quedó
  confirmada allí.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
