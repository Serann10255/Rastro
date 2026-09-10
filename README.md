# Rastro y Cotejo

Dos proyectos académicos que comparten repositorio porque comparten objeto:
**Rastro** es un sistema de trazabilidad verificable de envíos sobre servicios
gestionados en la nube, y **Cotejo** es el programa de auditoría que verifica de
forma automatizada los controles de Rastro y produce papeles de trabajo
reproducibles.

| | Rastro | Cotejo |
|---|---|---|
| Asignatura | Cloud Computing (ISD38) | Auditoría de Sistemas (ISD39) |
| Grupo | 30112 — Periodo 2026B | 30112 — Periodo 2026B |
| Qué es | Sistema de gestión y rastreo de envíos | Programa de auditoría del anterior |
| Dónde vive | `libs/`, `services/`, `web/`, `deploy/` | `cotejo/` |

> Toda la documentación está en [`documentacion/`](documentacion/). Empiece por
> [la visión general de arquitectura](documentacion/arquitectura/vision-general.md)
> o por [la guía de instalación y uso](documentacion/guias/instalacion-y-uso.md).

---

## Arrancar el sistema completo

```bash
docker compose up -d
```

Levanta la pila entera: DynamoDB Local, MinIO, los seis microservicios, la
puerta de enlace y la interfaz web, y siembra datos sintéticos.

| Componente | Dirección |
|---|---|
| Rastro — interfaz de operación | http://localhost:5173 |
| Rastro — consulta pública | http://localhost:5173/rastreo |
| Rastro — API | http://localhost:8080 |
| Cotejo — interfaz de auditoría | http://localhost:5175 |
| Cotejo — API | http://localhost:8007 |
| Consola del almacenamiento | http://localhost:9001 |

Cómo se usa cada una:
[guía de aplicaciones](documentacion/despliegue/como-usar-cada-app.md).

Usuarios sintéticos (definidos en [`seed/usuarios.json`](seed/usuarios.json)):

| Correo | Clave | Organización | Grupo |
|---|---|---|---|
| `admin@andes.test` | `Andes.2026` | org-andes | administrador |
| `despacho@andes.test` | `Andes.2026` | org-andes | despachador |
| `carlos@andes.test` | `Andes.2026` | org-andes | conductor |
| `auditor@andes.test` | `Andes.2026` | org-andes | auditor |
| `despacho@sabana.test` | `Sabana.2026` | org-sabana | despachador |

Las dos organizaciones existen para poder comprobar el aislamiento: comparten
infraestructura y no deben verse entre sí.

## Ejecutar las pruebas

```bash
python -m pytest -q
```

98 pruebas: unitarias de los controles críticos y de extremo a extremo sobre la
pila de microservicios. No requieren Docker ni credenciales de AWS.

## Ejecutar la auditoría

Desde la interfaz en http://localhost:5175, o desde la línea de comandos:

```bash
cd cotejo && python -m cotejo ejecutar
```

Recorre el catálogo de ocho controles contra el sistema desplegado y escribe los
papeles de trabajo y el informe en `cotejo/papeles/<ejecución>/`.

---

## Estructura del repositorio

```
libs/rastro_core/     Capa común: los controles críticos viven aquí, una sola vez
services/             Seis microservicios, uno por responsabilidad
web/                  Interfaz de Rastro (React + TypeScript), mobile-first
gateway/              Puerta de enlace local (equivalente de API Gateway)
deploy/aws/           Secuencia de despliegue versionada
deploy/local/         Preparación del entorno local
tests/                Pruebas de Rastro
seed/                 Datos sintéticos
cotejo/               Programa de auditoría (proyecto de Auditoría de Sistemas)
  cotejo/cotejo/      Ejecutor, papeles de trabajo, informe
  cotejo/api/         Interfaz HTTP, restringida al rol auditor
  cotejo/web/         Interfaz de auditoría (React + TypeScript)
documentacion/        Toda la documentación del repositorio
```

### Los seis microservicios

| Servicio | Puerto local | Responsabilidad |
|---|---|---|
| `auth` | 8001 | Emisor de tokens. En AWS lo sustituye Amazon Cognito |
| `shipments` | 8002 | Registro, asignación y consulta de envíos |
| `tracking` | 8003 | Puntos de control y máquina de estados |
| `evidence` | 8004 | Enlaces prefirmados y evidencias cifradas |
| `public` | 8005 | Consulta pública sin autenticación |
| `audit` | 8006 | Bitácora encadenada y verificador de integridad |

## Dos entornos, un mismo código

El sistema corre igual en local y en AWS; lo que cambia es dónde está cada pieza.

| En AWS | Equivalente local |
|---|---|
| API Gateway | nginx (`gateway/`) |
| AWS Lambda | Un contenedor por microservicio |
| DynamoDB | DynamoDB Local |
| S3 + KMS | MinIO (sin KMS) |
| Cognito | Microservicio `auth` |
| Sitio estático en S3 | Contenedor nginx con el sitio compilado |

Las diferencias no se disimulan. El cifrado con llave administrada, el registro
de actividad y el bloqueo de acceso público **no existen** en el entorno local:
son controles de infraestructura, y Cotejo los marca como *no ejecutados* en
lugar de darlos por conformes.

## Datos sintéticos

El sistema se puebla únicamente con datos sintéticos. Es una decisión explícita
del proyecto: así no se generan obligaciones de tratamiento sobre titulares
reales bajo la Ley 1581 de 2012, mientras el diseño conserva los controles que
un tratamiento real exigiría.

## Equipo

- Sergio Alejandro Montoya Granados — sergio.montoya@cun.edu.co
- Nicolás Torres Perdomo — nicolas.perdomot@cun.edu.co
- Óscar Julián Rincón Bejarano — oscar.rinconbbe@cun.edu.co

Corporación Unificada Nacional de Educación Superior — CUN
Programa de Ingeniería de Sistemas · Bogotá, D. C.
