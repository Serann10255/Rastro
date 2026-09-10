# Servicio `audit` — bitácora de auditoría

Ubicación: `services/audit/` · Puerto local: 8006 · Requisitos: REQ-07, REQ-08

## Qué hace

Expone la bitácora encadenada al rol auditor y el verificador de integridad.

| Operación | Grupo |
|---|---|
| `GET /bitacora` | auditor únicamente |
| `GET /bitacora/verificacion` | auditor únicamente |

## Decisión central: ninguna ruta de escritura

**El servicio no expone ninguna operación de escritura sobre la bitácora.** Los
eslabones los escriben los demás servicios como efecto de sus propias
operaciones; ningún usuario, ni siquiera el administrador, puede añadir o
corregir un registro por esta vía.

La prueba `test_la_bitacora_no_expone_ninguna_ruta_de_escritura` comprueba el
contrato leyendo el esquema del servicio: si alguien añadiera un `POST`, falla.

## Qué conserva cada registro

La cuádrupla mínima de Kent y Souppaya (2006) —quién, qué acción, sobre qué
recurso, cuándo— más el resultado (`ALLOW` / `DENY` / `ERROR`), el detalle del
motivo, el hash previo y el hash propio.

## El verificador

Recalcula la cadena completa y señala el punto exacto de ruptura. Detecta tres
formas de manipulación:

| Manipulación | Cómo se detecta |
|---|---|
| Contenido modificado | El hash recalculado no coincide |
| Contenido modificado y hash reparado | El registro siguiente ya no enlaza |
| Registro intermedio eliminado | Salto en la secuencia |

El criterio de aceptación tiene **dos sentidos**: sobre una bitácora íntegra debe
informar cadena válida, y tras una alteración controlada debe señalar dónde se
rompió. Comprobar solo lo primero no demuestra que el verificador sirva: uno que
siempre respondiera que sí también pasaría esa prueba.

## Decisiones

**Solo el auditor la alcanza.** Cualquier otro grupo recibe 403, y el intento
queda registrado en la propia bitácora.

**La consulta del auditor también deja rastro**: quién revisó y cuándo.

**Cada organización tiene su propia cadena.** La bitácora de una no contiene
registros de otra, ni siquiera los intentos fallidos de acceso entre ellas: el
intento queda en la bitácora de quien lo hizo.

## Dependencias y relaciones

- **Depende de**: `rastro_core.audit` (verificador) y del repositorio.
- **Lo consume**: la vista de bitácora de la interfaz web y el control C-08 de
  Cotejo, que descarga la bitácora y **recalcula la cadena de forma
  independiente**, contrastando su resultado con el que informa este servicio.

## Comportamiento responsive

No aplica al servicio. La tabla de la interfaz sí: scrollea dentro de su propio
contenedor y nunca desborda la página. Véase
[`interfaz-web`](../interfaz-web/README.md).
