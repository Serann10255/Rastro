# Visión general de la arquitectura

Fecha: 2026-09-10 · Versión: 0.1

## Qué resuelve el sistema

Una empresa de mensajería pequeña registra el avance de sus envíos por teléfono,
chat y hojas de cálculo. Ese esquema no conserva quién cambió el estado de un
envío, cuándo lo hizo ni con qué evidencia, de modo que resolver una reclamación
depende de la memoria de los participantes.

Rastro traslada ese registro a un sistema que obliga a que **cada cambio quede
atribuido, fechado y validado contra un conjunto de transiciones permitidas**, y
que conserva un rastro verificable de todo lo ocurrido.

Lo que diferencia la propuesta de un registro convencional son dos controles:

1. Una **máquina de estados** que rechaza transiciones inválidas.
2. Una **bitácora encadenada por funciones hash** que permite detectar
   alteraciones posteriores.

## Por qué microservicios sin servidor

El entorno de trabajo es AWS Academy Learner Lab, y dos de sus condiciones
determinaron la arquitectura antes que cualquier preferencia técnica:

- **Las instancias de cómputo se detienen al cerrar cada sesión.** Un punto de
  consulta público montado sobre una instancia dejaría de responder entre
  jornadas. El cómputo bajo demanda no tiene ese problema.
- **Otros recursos siguen facturando entre sesiones.** Un motor de base de datos
  administrado olvidado consumiría el presupuesto completo. El proyecto excluye
  deliberadamente ese grupo de recursos.

Se compararon tres alternativas (arquitectura sin servidor, monolito en una
instancia, plataforma comercial). La decisión y su justificación están en
[`decisiones/adr-001-arquitectura-sin-servidor.md`](../decisiones/adr-001-arquitectura-sin-servidor.md).

## Componentes

```
                      ┌──────────────────────────────┐
   Despachador ─┐     │  Interfaz web (sitio estático)│
   Conductor  ──┼────▶│  mobile-first, sin compilación│
   Auditor    ──┘     └──────────────┬───────────────┘
                                     │ token de sesión
                                     ▼
                      ┌──────────────────────────────┐
   Destinatario ─────▶│  Puerta de enlace HTTP        │
   (sin cuenta)       │  API Gateway · nginx en local │
                      └──────────────┬───────────────┘
                                     │
      ┌────────────┬─────────────┬───┴────────┬─────────────┬────────────┐
      ▼            ▼             ▼            ▼             ▼            ▼
   ┌──────┐   ┌─────────┐   ┌─────────┐  ┌──────────┐  ┌────────┐  ┌─────────┐
   │ auth │   │shipments│   │tracking │  │ evidence │  │ public │  │  audit  │
   └──────┘   └────┬────┘   └────┬────┘  └────┬─────┘  └───┬────┘  └────┬────┘
                   └─────────────┴────────────┴────────────┴───────────┘
                                     │
                        ┌────────────▼─────────────┐
                        │   libs/rastro_core        │
                        │   capa común de control   │
                        └────────────┬─────────────┘
                                     │
              ┌──────────────┬───────┴────────┬──────────────────┐
              ▼              ▼                ▼                  ▼
      ┌──────────────┐ ┌──────────┐  ┌────────────────┐  ┌──────────────┐
      │ tabla envíos │ │ bitácora │  │ evidencias S3  │  │  CloudTrail  │
      │  + eventos   │ │encadenada│  │  cifradas KMS  │  │  (actividad) │
      └──────────────┘ └──────────┘  └────────────────┘  └──────────────┘
```

Las cinco funciones comparten un mismo rol de ejecución (`LabRole`), condición
impuesta por el entorno y declarada como limitación conocida: véase
[`decisiones/adr-004-rol-compartido.md`](../decisiones/adr-004-rol-compartido.md).

## Por qué una capa común y no un servicio por completo aislado

Los microservicios de Rastro no son independientes en su acceso a datos, y eso
es deliberado. Todos pasan por `libs/rastro_core`, que concentra cuatro cosas:

| Módulo | Control que implementa | Requisito |
|---|---|---|
| `claves.py` + `repository.py` | Filtro obligatorio por organización | REQ-06 |
| `state_machine.py` | Transiciones válidas del ciclo de vida | REQ-03 |
| `authz.py` + `http.py` | Matriz de autorización y registro del rechazo | REQ-07 |
| `audit.py` | Encadenamiento por funciones hash | REQ-08 |

La razón es el riesgo R-05: *una sola consulta sin filtrar por organización
basta para exponer los datos de una empresa a otra*. Si cada servicio
construyera sus propias consultas, el aislamiento habría que verificarlo seis
veces y bastaría un descuido en una de ellas. Con una única capa, el control se
implementa una vez y se prueba una vez.

Lo que sí está separado es la **responsabilidad**: cada servicio despliega,
escala y falla por su cuenta, y en AWS cada uno es una función Lambda distinta.

## Recorrido de una solicitud

1. El usuario se autentica y recibe un token con sus grupos y su organización.
2. La interfaz envía ese token a la puerta de enlace, que valida firma, vigencia
   y emisor antes de invocar el servicio.
3. El servicio **vuelve a validar el token** —no depende de un único control— y
   consulta la matriz de autorización.
4. La operación se resuelve siempre a través de la capa común, que aplica el
   identificador de organización del token como filtro obligatorio.
5. El resultado se registra en la bitácora, **tanto si se autorizó como si se
   rechazó**.

Las evidencias de entrega no atraviesan los servicios: el servicio emite un
enlace prefirmado de vigencia limitada y el dispositivo carga el archivo
directamente contra el almacenamiento cifrado.

## Trazabilidad en dos capas independientes

| Capa | Qué registra | Quién la escribe |
|---|---|---|
| Aplicativa | Cada operación con actor, acción, recurso, resultado y hash encadenado | Los propios servicios |
| Infraestructura | Cada llamada a la interfaz de programación de AWS | CloudTrail |

La independencia es lo que da valor al esquema: una modificación hecha
directamente sobre la tabla, sin pasar por la aplicación, quedaría registrada en
la capa de infraestructura **aunque el atacante recalculara la cadena**.

## Portabilidad

El presupuesto del laboratorio puede agotarse, y en ese caso se habilita una
cuenta nueva. Por eso ningún identificador propio de la cuenta se escribe a mano:

- el nombre del contenedor se deriva del número de cuenta,
- el rol de ejecución se referencia por nombre,
- la llave de cifrado se invoca por alias,
- los identificadores que genera el proveedor se escriben en
  `config/deployment.json`, que los servicios y la interfaz leen en ejecución.

La etapa `deploy/aws/90-configuracion.sh` **comprueba** que el número de cuenta
no aparezca literal en el código y falla si lo encuentra. Es la mitigación del
riesgo R-07, aplicada antes de necesitarla.

## Documentos relacionados

- [Modelo de datos](../base-de-datos/modelo-de-datos.md)
- [Contratos de la interfaz](../api/contratos.md)
- [Plan de pruebas y trazabilidad de requisitos](../pruebas/plan-y-trazabilidad.md)
- [Despliegue en AWS](../despliegue/entorno-aws.md)
- [Decisiones técnicas](../decisiones/)
