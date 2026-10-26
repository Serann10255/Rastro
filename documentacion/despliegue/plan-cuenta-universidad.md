# Plan para la cuenta de AWS de la universidad

Fecha: 2026-10-23 · Estado: **preparado, a la espera de la cuenta**

El proyecto fue seleccionado para presentarse a toda la universidad, y la
universidad va a asignar una cuenta de AWS para dejar la aplicación completa.
Este documento dice qué hacer el día que llegue, en orden, y qué decisión hay
que tomar antes: si se usa o no una base de datos relacional (RDS).

Nada de lo de aquí se ha ejecutado todavía: no hay cuenta. Lo que sí está
comprobado es lo que ya existe en el repositorio y en qué punto depende del
laboratorio.

---

## 1. Lo primero: qué tipo de cuenta es

Todo el plan depende de esto, y se sabe en dos minutos con la cuenta en la mano.

| Si es… | Cómo se reconoce | Qué cambia |
|---|---|---|
| **Otro AWS Academy Learner Lab** | Se entra por *AWS Academy → Learner Lab → Start Lab*; las credenciales traen `aws_session_token` y caducan a las cuatro horas; existe el rol `LabRole` | Casi nada: siguen RE-01 a RE-06 de [entorno-aws](entorno-aws.md). Es una migración de cuenta (sección 3) y nada más |
| **Una cuenta completa** (de la universidad, de una organización o propia) | Se entra por la consola normal o por IAM Identity Center; no existe `LabRole`; se pueden crear roles | Desaparecen las restricciones del laboratorio. Hay que crear el rol de ejecución antes de desplegar (sección 4) |

Comprobación con la CLI, ya con las credenciales cargadas:

```bash
aws sts get-caller-identity                      # número de cuenta y quién es usted
aws iam get-role --role-name LabRole             # existe → Learner Lab
aws iam create-role --role-name rastro-prueba-permisos \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam delete-role --role-name rastro-prueba-permisos   # si la creación funcionó, se borra en seguida
```

Si `create-role` responde `AccessDenied`, RE-01 sigue vigente aunque la cuenta no
sea un laboratorio.

---

## 2. Lo que una cuenta completa permite cerrar

Lo que hoy figura como limitación declarada lo es por el laboratorio, no por
diseño. Con una cuenta completa, cada fila deja de ser una restricción y pasa a
ser trabajo pendiente:

| Hoy (laboratorio) | Con cuenta completa | Qué cierra |
|---|---|---|
| RE-01: las ocho funciones comparten `LabRole` | **Un rol de ejecución por función**, con solo los permisos de su servicio | El hallazgo de mínimo privilegio (AWS Well-Architected, [ADR-004](../decisiones/adr-004-rol-compartido.md)); la acción prioritaria de Sergio en las conclusiones |
| RE-06: con la sesión cerrada, la API responde 500 | Responde a cualquier hora | La consulta pública disponible siempre; la demostración sin «abrir el laboratorio diez minutos antes» |
| RE-04: el entorno se pierde al terminar el curso | La cuenta sigue | Que la aplicación viva después de la materia |
| Retención inmutable del almacén, declarada como no lograda | Bloqueo de objetos (S3 Object Lock) en un almacén nuevo | El único objetivo declarado como no logrado en la Entrega 2 |
| Integridad de la bitácora por detección, no por prevención | Copiar la huella de cada cierre de la cadena a un almacén con bloqueo, fuera del alcance de quien opera | La segunda limitación de las conclusiones |
| RE-05: sin CloudFront | Dominio propio y CloudFront, **opcional** | Una dirección legible en lugar de `…execute-api…`; el HTTPS ya funciona ([ADR-012](../decisiones/adr-012-sitio-https-por-api-gateway.md)) |
| SU-01 indeterminado | Probar el validador de API Gateway con un emisor OpenID real | Resolver SU-01; no cambia el funcionamiento ([ADR-007](../decisiones/adr-007-identidad-propia.md)) |
| REQ-09 parcial | La migración a esta cuenta **es** el simulacro que faltaba | REQ-09 completo, con evidencia |

Ninguna de estas filas exige tocar la lógica de negocio. Las tres primeras son
de despliegue; las de almacén y bitácora, de despliegue más una función pequeña.

---

## 3. La migración, paso a paso

El repositorio ya trae lo necesario: `deploy/aws/desplegar.sh` levanta todo en
una cuenta vacía en unos ocho minutos, y `deploy/aws/migrar.sh` exporta e
importa los datos con la bitácora y sus huellas. Este es el orden.

**Antes de que cierre el laboratorio actual** (después ya no se puede exportar):

1. Abrir el laboratorio actual y exportar:
   ```bash
   ./deploy/aws/migrar.sh exportar        # envíos, bitácora y evidencias a migracion/
   ```
   `migracion/` no se versiona: tiene datos de la operación.

**Con la cuenta nueva:**

2. Credenciales. En una cuenta completa, **nunca** las del usuario raíz: un
   usuario de IAM Identity Center o, si no hay, un usuario de IAM con MFA.
   Mismo método de carga que en [entorno-aws](entorno-aws.md#credenciales-qué-hace-falta-y-qué-no);
   en una cuenta completa no hay `aws_session_token` si las claves son de un
   usuario de IAM.
3. **Alarma de presupuesto** antes de crear nada (AWS Budgets, aviso al 50 % y
   al 80 % de lo que asigne la universidad). En el laboratorio el tope lo ponía
   AWS Academy; en una cuenta completa no hay tope si nadie lo pone.
4. **Un secreto de firma nuevo** en `config/.jwt.env`. No se reutiliza el del
   laboratorio: la cuenta nueva es la ocasión de no arrastrar nada que haya
   estado expuesto (H-01).
5. Si es cuenta completa, **el rol de ejecución** (sección 4) y
   `export RASTRO_ROL=<nombre>`; `comun.sh` ya lo lee, con `LabRole` por omisión.
6. Desplegar y verificar:
   ```bash
   RASTRO_PUBLICAR_COTEJO=si ./deploy/aws/desplegar.sh
   ./deploy/aws/95-verificar.sh
   ./deploy/aws/migrar.sh importar
   ```
7. Verificar la bitácora importada desde la sesión del auditor: si la cadena
   no verifica, la migración alteró los datos y se repite.
8. Ejecutar Cotejo contra la cuenta nueva y guardar la ejecución de referencia.
9. Actualizar las configuraciones versionadas que apuntan a AWS
   (`web/public/configuracion.json` y la de Cotejo) con las direcciones nuevas.
10. Dejar constancia: salida de cada paso en `evidencias-despliegue/`, bitácora
    en `documentacion/cambios/`, direcciones nuevas en
    [entorno-aws](entorno-aws.md) y REQ-09 cerrado en
    [plan-y-trazabilidad](../pruebas/plan-y-trazabilidad.md).

**No borrar el laboratorio viejo** hasta haber hecho la presentación con la
cuenta nueva: es el respaldo.

---

## 4. El rol de ejecución en una cuenta completa

Hoy `deploy/aws/comun.sh` usa `LabRole` salvo que `RASTRO_ROL` diga otro
nombre. En una cuenta completa `LabRole` no existe y el despliegue se detiene en
`30-funciones.sh`. Hay dos caminos:

| | Qué es | Esfuerzo | Cierra el hallazgo de mínimo privilegio |
|---|---|---|---|
| **A. Un rol compartido** `rastro-ejecucion` | Equivalente a `LabRole`, pero con permisos acotados a los recursos del proyecto | Una tarde, con `RASTRO_ROL` | No del todo: las ocho funciones siguen compartiéndolo |
| **B. Un rol por función** | Cada servicio con solo sus tablas, su llave y su prefijo del almacén | Una semana, como estaba previsto | Sí |

Recomendación: **A para migrar** (desbloquea el despliegue el mismo día) y **B
como siguiente paso**, ya con la aplicación funcionando en la cuenta nueva. B
necesita una etapa nueva en `deploy/aws/` y un ADR que reemplace a ADR-004.

---

## 5. RDS: en espera

> **2026-10-26 — se deja para después.** El equipo decidió no hacer nada con
> RDS hasta que el docente entregue una cuenta que permita configurarlo, y
> mientras tanto comprobar que el resto funciona. Cuando llegue la cuenta se
> retoma desde aquí; mientras, nada en el código ni en el despliegue depende de
> esta decisión.

Se pidió «configurar las RDS». Antes de hacerlo conviene decir lo que implica,
porque **Rastro ya tiene base de datos**: tres tablas en DynamoDB, que es la
base de datos gestionada de AWS. La aplicación está completa sin RDS.

RDS se descartó en [ADR-001](../decisiones/adr-001-arquitectura-sin-servidor.md)
por el laboratorio (factura continuamente aunque nadie lo use), pero el motivo
de fondo sigue en una cuenta completa:

- **Cobra por hora**, encendido o no se use, más el almacenamiento. Lo que hoy
  cuesta casi cero sin uso pasa a tener un cargo fijo mensual.
- **Exige red privada (VPC).** Las funciones que lo consulten tienen que entrar
  en ella, y entonces necesitan puntos de enlace o una pasarela NAT —otro cargo
  fijo— para seguir alcanzando DynamoDB, S3 y KMS.
- **Reescribir la capa de datos.** `libs/rastro_core/repository.py` y sus
  pruebas están hechos para DynamoDB, incluida la clave `ORG#…` que impide por
  diseño leer datos de otra empresa (control C-06 de Cotejo).

Tres opciones:

| | Qué es | Esfuerzo | Riesgo antes de la presentación |
|---|---|---|---|
| **1. Sin RDS** (recomendada si no es un requisito) | Seguir con DynamoDB y dedicar la cuenta a la sección 2 | Ninguno | Ninguno |
| **2. RDS solo para informes** | DynamoDB sigue siendo la base de la operación; cada cambio se copia a una base PostgreSQL de solo lectura para consultas e informes en SQL | Una a dos semanas: VPC, base pequeña, una función que copie los cambios y un ADR | Bajo: si falla, la operación no se entera |
| **3. Migrar todo a RDS** | Sustituir DynamoDB | Varias semanas: capa de datos, pruebas, controles de Cotejo, despliegue | Alto |

Si la universidad o el docente **exigen** RDS, la opción 2 lo cumple sin poner
en riesgo lo que ya funciona y tiene una razón propia: los informes de una
empresa de mensajería se escriben mejor en SQL. La 3 no se recomienda antes de
la presentación.

---

## 6. El cliente en Flet

Otra sesión de trabajo está construyendo una aplicación con Flet para celular y
escritorio (`cliente-flet/`). Lo que importa para la cuenta nueva:

- **Ya cumple la regla de portabilidad.** Lee la dirección de la API en tiempo
  de ejecución: primero la que el usuario fije en la pantalla de conexión,
  luego la de las variables `RASTRO_CONFIGURACION` y `COTEJO_CONFIGURACION`, y
  por último el `configuracion-*.json` empaquetado en `assets/`
  (`cliente-flet/src/comun/configuracion.py`). Cambiar de cuenta no exige
  recompilar el APK.
- **Al migrar** hay que regenerar los `assets/configuracion-*.json` con las
  direcciones nuevas (o apuntar cada dispositivo desde la pantalla de
  conexión), igual que el paso 9 hace con la interfaz web.
- **Con una cuenta completa**, la regla CORS de la API tiene que admitir el
  origen del cliente si se usa en su modo web; en escritorio y en el APK no
  aplica.

Coordinar con esa sesión antes de tocar `deploy/aws/90-configuracion.sh`: es el
lugar natural para que el despliegue escriba también esos archivos.

---

## 7. Qué hace falta del equipo

| Pregunta | Por qué importa |
|---|---|
| ¿Qué tipo de cuenta es? (sección 1) | Decide si hay que crear el rol y si la sección 2 aplica |
| ¿RDS es un requisito o una sugerencia? | Decide entre las opciones 1 y 2 de la sección 5. **En espera** hasta tener la cuenta |
| ¿Cuánto presupuesto asigna la universidad y quién recibe las alarmas? | La alarma del paso 3 |
| ¿Cuándo es la presentación? | Lo que no esté probado en la cuenta nueva una semana antes, se presenta desde el laboratorio actual |
