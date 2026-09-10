# Estructura de la documentación

Fecha: 2026-09-10

Toda la documentación vive en `documentacion/`, nunca suelta en la raíz ni
mezclada con el código. Los nombres van en kebab-case sin tildes y las fechas en
formato ISO.

| Carpeta | Qué contiene |
|---|---|
| `arquitectura/` | [Visión general](../arquitectura/vision-general.md): componentes, recorrido de una solicitud, trazabilidad en dos capas |
| `modulos/` | Un subdirectorio por módulo, con qué hace, dependencias, decisiones y comportamiento responsive |
| `base-de-datos/` | [Modelo de datos](../base-de-datos/modelo-de-datos.md): claves, índices, atributos y encadenamiento |
| `api/` | [Contratos](../api/contratos.md): operaciones, códigos de respuesta y reparto de rutas |
| `guias/` | [Instalación y uso](instalacion-y-uso.md) y este índice |
| `decisiones/` | Registros de decisión (ADR) con contexto, alternativas y consecuencias |
| `pruebas/` | [Plan y trazabilidad](../pruebas/plan-y-trazabilidad.md): cada requisito con la prueba que lo comprueba |
| `despliegue/` | [Entorno AWS](../despliegue/entorno-aws.md): etapas, restricciones, coste y migración |
| `cambios/` | Bitácora por fecha |

## Módulos documentados

| Módulo | Documento |
|---|---|
| Capa común | [`rastro-core`](../modulos/rastro-core/README.md) |
| Emisor de tokens | [`servicio-auth`](../modulos/servicio-auth/README.md) |
| Envíos | [`servicio-envios`](../modulos/servicio-envios/README.md) |
| Puntos de control | [`servicio-rastreo`](../modulos/servicio-rastreo/README.md) |
| Evidencias | [`servicio-evidencias`](../modulos/servicio-evidencias/README.md) |
| Consulta pública | [`servicio-consulta-publica`](../modulos/servicio-consulta-publica/README.md) |
| Bitácora | [`servicio-bitacora`](../modulos/servicio-bitacora/README.md) |
| Interfaz web | [`interfaz-web`](../modulos/interfaz-web/README.md) |
| Programa de auditoría | [`cotejo`](../modulos/cotejo/README.md) |

## Decisiones registradas

| ADR | Asunto |
|---|---|
| [001](../decisiones/adr-001-arquitectura-sin-servidor.md) | Arquitectura sin servidor sobre servicios gestionados |
| [002](../decisiones/adr-002-capa-comun-de-acceso-a-datos.md) | Una única capa de acceso a datos |
| [003](../decisiones/adr-003-identificador-aleatorio.md) | Identificador de rastreo aleatorio |
| [004](../decisiones/adr-004-rol-compartido.md) | Rol de ejecución compartido |

## Al añadir o modificar un módulo

1. Revisar si ya existe su documento en `modulos/`.
2. Actualizarlo en la misma entrega: código sin documentar se considera
   incompleto.
3. Registrar el cambio en `cambios/<fecha>.md`.
4. Si el módulo tiene interfaz, documentar sus breakpoints y cómo cambia el
   layout.
