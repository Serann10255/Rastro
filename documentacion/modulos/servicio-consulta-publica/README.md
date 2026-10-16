# Servicio `public` — consulta pública

Ubicación: `services/public/` · Puerto local: 8005 · Requisito: REQ-04

## Qué hace

Devuelve el avance de un envío a partir de su identificador, **sin
autenticación**. Es el único punto del sistema que responde sin token, y por eso
es el más expuesto.

`GET /publico/envios/{envio_id}` — el avance.

`GET /publico/envios/{envio_id}/ubicacion` — dónde va el vehículo mientras el
envío está en reparto ([rutas de entrega](../rutas-de-entrega/README.md)).

## Los dos controles que lo protegen

**El identificador aleatorio.** Con numeración secuencial, cualquiera podría
recorrer identificadores contiguos y obtener los envíos de toda la empresa. El
UUID v4 lo impide. Véase
[ADR-003](../../decisiones/adr-003-identificador-aleatorio.md).

**La vista reducida.** Ni siquiera con un identificador válido se obtiene:

| Sí devuelve | No devuelve |
|---|---|
| Estado y fechas | Identificador de organización |
| Ciudad de destino | Identidad del mensajero |
| Nombre enmascarado (`Laura M. R.`) | Dirección de origen |
| Estados del histórico con su fecha | Coordenadas de los puntos de control |
| Si un evento tiene evidencia | La evidencia misma |
| Posición del vehículo en reparto, redondeada a ~11 m y de menos de 10 min (solo en `/ubicacion`) | Quién conduce, la ruta, sus otras paradas, el recorrido |

## Decisiones

**El formato se valida antes de consultar el almacenamiento.** Un identificador
que no sea un UUID canónico responde 422 sin producir una lectura: el sondeo no
cuesta ni una operación.

**El nombre del destinatario se enmascara.** Es minimización de datos: se
conserva lo suficiente para que el destinatario se reconozca y no lo suficiente
para construir un directorio de clientes de la empresa.

**Este servicio no escribe en la bitácora.** Sin sesión no hay actor al que
atribuir el evento, y un registro sin actor no cumple la cuádrupla mínima de
Kent y Souppaya (2006). La actividad del punto público se observa en la capa de
infraestructura. Cubierto por `test_la_consulta_publica_no_escribe_en_la_bitacora`.

**La ubicación va en una ruta aparte y no en el histórico.** La pantalla la
pregunta cada veinte segundos y el histórico no cambia a ese ritmo; y la vista
del histórico tiene un contrato que Cotejo lee: añadirle la posición de una
persona cambiaría lo que promete no mostrar. Qué se entrega lo decide
`rutas.ubicacion_publica`: solo con el envío `EN_REPARTO`, en una ruta abierta y
con una posición reciente. Cubierto por las pruebas `test_el_destinatario_*` y
`test_tras_la_entrega_o_el_cierre_la_posicion_deja_de_verse` de
`tests/e2e/test_rutas.py`.

## Dependencias y relaciones

- **Depende de**: `rastro_core.repository.historico_publico` y `maestro_publico`,
  que consultan el índice `gsi_publico`, y de `obtener_ruta` para la ubicación.
- Ese índice existe porque el destinatario solo tiene el identificador y no
  conoce la organización. Permite resolverlo sin abrir las particiones
  autenticadas.

## Comportamiento responsive

El servicio no tiene interfaz; su pantalla es `web/rastreo.html`, descrita en
[`interfaz-web`](../interfaz-web/README.md).
