# Despliegue en AWS

Fecha: 2026-09-10 · Versión: 0.2

## Estado de verificación

> **La secuencia de despliegue está escrita y versionada, pero no se ha
> ejecutado contra la cuenta del laboratorio.** No hay credenciales de AWS en el
> entorno donde se construyó el repositorio, de modo que estos guiones no están
> verificados contra el servicio real. Lo que sí está verificado de extremo a
> extremo es la pila local equivalente.
>
> Esto es lo que queda por comprobar, y es también la primera actividad de la
> fase 1 del plan de trabajo:
>
> - **SU-01** — que el laboratorio permita crear una interfaz HTTP con validador
>   de tokens. `40-api.sh` lo intenta y continúa si no se puede: cada servicio
>   valida el token por su cuenta, de modo que el sistema funciona igual y solo
>   se pierde una capa. Con el proveedor de identidad propio el validador no
>   aplica de todas formas —solo verifica firmas de clave pública (RS256) contra
>   un JWKS, y el sistema firma con clave compartida—, pero se intenta igual para
>   dejar constancia de lo que el laboratorio permite, que es lo que el supuesto
>   pregunta. Véase [ADR-007](../decisiones/adr-007-identidad-propia.md).
> - **REQ-09** — que el despliegue se reproduzca en una cuenta vacía sin editar
>   código.

---

## Credenciales: qué hace falta y qué no

**Nada de lo local necesita credenciales de AWS.** La pila de `docker compose`
usa claves ficticias (`local` / `localsecreto`) contra DynamoDB Local y MinIO. Se
puede desarrollar y probar el sistema entero sin haber abierto nunca el
laboratorio.

**Para desplegar sí son obligatorias**, porque los guiones llaman a la interfaz
del proveedor.

### Cómo cargarlas

AWS Academy Learner Lab entrega credenciales **temporales** de tres partes. En el
laboratorio, *AWS Details → AWS CLI → Show*, y se copia el bloque en
`~/.aws/credentials`:

```ini
[default]
aws_access_key_id     = ASIA...
aws_secret_access_key = ...
aws_session_token     = ...
```

El `aws_session_token` es imprescindible: son credenciales temporales y sin él
toda llamada falla con un error de firma que no dice cuál es el problema.

Comprobar antes de desplegar:

```bash
aws sts get-caller-identity
```

Debe devolver el número de cuenta. Si falla, las credenciales caducaron.

### Caducan cada sesión

Duran lo que la sesión del laboratorio, unas cuatro horas. Al caducar hay que
volver a copiar el bloque; **el mismo `[default]` se sobrescribe**, no hay que
crear perfiles nuevos.

Por eso `comun.sh` consulta la identidad al empezar y **falla ahí** si no hay
sesión válida, en lugar de a mitad del despliegue con recursos creados a medias.
Y por eso la secuencia es idempotente: si caduca en mitad, se recargan las
credenciales y se vuelve a ejecutar sin deshacer nada.

### Si prefiere no tocar `~/.aws/credentials`

Las variables de entorno tienen precedencia y no dejan rastro en disco:

```bash
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
export AWS_REGION=us-east-1
```

Es lo recomendable en un equipo compartido. En cualquiera de los dos casos,
**las credenciales nunca se versionan**: no aparecen en el repositorio ni en
`config/deployment.json`, que solo guarda identificadores de recursos.

---

## Ejecutar el despliegue

```bash
./deploy/aws/desplegar.sh
```

Es **idempotente**: puede ejecutarse tantas veces como haga falta. No es
comodidad sino requisito, porque las credenciales del laboratorio caducan cada
cuatro horas y un despliegue interrumpido debe poder reanudarse sin dejar
recursos a medias ni duplicados.

Cada etapa deja su salida en `evidencias-despliegue/` con marca de tiempo, de
modo que un tercero pueda repetir la verificación.

### Etapas

| Etapa | Qué crea |
|---|---|
| `10-datos.sh` | Tablas con sus índices, llave de cifrado con rotación, contenedores con cifrado, versionado, bloqueo público y política que rechaza cargas sin cifrar |
| `20-identidad.sh` | Aprovisiona las dos organizaciones, sus diez usuarios con las contraseñas derivadas y sus datos maestros, ejecutando **el mismo guion que prepara el entorno local** apuntado a la cuenta |
| `30-funciones.sh` | Empaqueta y despliega los ocho microservicios como funciones Lambda. **Se niega a desplegar** si `RASTRO_JWT_SECRETO` no está definido o tiene menos de 32 caracteres |
| `40-api.sh` | Interfaz HTTP, validador de tokens (SU-01), rutas e integraciones |
| `50-registro.sh` | CloudTrail con validación de integridad de sus archivos |
| `60-sitios.sh` | Compila las interfaces, crea el contenedor del sitio y las publica |
| `90-configuracion.sh` | Escribe `config/deployment.json` y comprueba que no queden identificadores literales |
| `95-verificar.sh` | Confirma que cada componente existe y que el punto público responde |

**`auth` sí se despliega en AWS**, como una función más: el sistema tiene su
propio directorio de usuarios. La versión anterior delegaba en Amazon Cognito y
se cambió porque administrar cuentas desde la aplicación exige permisos que el
laboratorio no concede. Delegar en Cognito sigue siendo posible sin tocar nada
más, porque lo único que los demás servicios conocen es la forma del token
([ADR-007](../decisiones/adr-007-identidad-propia.md)).

**El aprovisionamiento no tiene una segunda implementación.** `20-identidad.sh`
ejecuta el mismo `deploy/local/preparar_entorno.py` con las variables apuntadas
a la cuenta. Un segundo guion de siembra divergiría del primero y el síntoma
aparecería en producción, no en local.

**Las contraseñas de la semilla son de desarrollo.** Antes de un despliegue con
datos reales deben sustituirse; se pasan por variable de entorno para no dejarlas
escritas en el repositorio.

La interfaz de **Cotejo no se publica por omisión**: el almacén de papeles de
trabajo concentra información sobre las debilidades del sistema auditado, y
publicarla en un sitio de lectura pública ampliaría la superficie sin necesidad.
Se sirve en la máquina del auditor, o se publica de forma explícita con
`RASTRO_PUBLICAR_COTEJO=si`.

### Las interfaces y REQ-09

La compilación **no hornea la dirección de la API en el bundle**. Cada sitio la
lee de su `configuracion.json` en tiempo de ejecución, que `60-sitios.sh` escribe
con los identificadores del despliegue. Un mismo `dist/` compilado sirve para
local y para AWS. Si alguien introdujera una variable de entorno de compilación
con la URL, REQ-09 dejaría de cumplirse aunque el resto siguiera igual. Véase
[ADR-005](../decisiones/adr-005-react-con-configuracion-en-ejecucion.md).

---

## Qué impone el entorno

| Restricción | Efecto en el despliegue |
|---|---|
| RE-01: no se pueden crear roles | Todas las funciones comparten `LabRole`. Se declara como hallazgo permanente ([ADR-004](../decisiones/adr-004-rol-compartido.md)) |
| RE-02: la invocación anónima de URL de función está impedida | Se usa API Gateway y no URL de función |
| RE-03: solo `us-east-1`, 50 dólares | Ningún diseño multirregión; se excluye todo recurso que facture entre sesiones |
| RE-04: el entorno se pierde al terminar el curso | Toda la configuración es reproducible por comandos versionados |

### Coste

El **único componente con cargo fijo mensual** es la llave de cifrado
administrada por el cliente. El resto opera bajo pago por uso y, con el volumen
de un entorno de pruebas, es marginal.

El riesgo presupuestal no viene del volumen de uso sino de dejar activo un
recurso que factura de forma continua. El proyecto **no emplea** motores de base
de datos administrados, balanceadores ni pasarelas de traducción de direcciones,
y esa exclusión es la principal medida de control del gasto.

Los eventos de datos de CloudTrail son el componente variable de mayor
incertidumbre y por eso están **desactivados por omisión**:

```bash
RASTRO_EVENTOS_DE_DATOS=si ./deploy/aws/50-registro.sh
```

Actívelos solo después de cuantificar su coste con la calculadora oficial.

---

## Portabilidad (REQ-09)

Si el presupuesto se agota, el docente habilita una cuenta nueva. La consecuencia
no es perder el proyecto sino el coste de reconstruirlo, y eso es lo que la
portabilidad reduce.

**Ningún identificador propio de la cuenta se escribe a mano:**

| Elemento | Cómo se referencia |
|---|---|
| Contenedor de objetos | Se deriva del número de cuenta, consultado a la propia sesión |
| Rol de ejecución | Por nombre (`LabRole`), no por ruta completa |
| Llave de cifrado | Por alias (`alias/rastro`) |
| Identificadores generados por el proveedor | En `config/deployment.json`, leído en ejecución |

`90-configuracion.sh` **busca el número de cuenta en el código y falla si lo
encuentra**. Es la mitigación del riesgo R-07, aplicada antes de necesitarla.

### Migrar a otra cuenta

```bash
./deploy/aws/migrar.sh exportar    # en la cuenta que se abandona
# cambiar de credenciales
./deploy/aws/desplegar.sh          # en la cuenta nueva
./deploy/aws/migrar.sh importar    # en la cuenta nueva
```

La bitácora se exporta tal cual, con sus hashes. **Si al importar la cadena no
verifica, la migración alteró los datos y hay que repetirla**: el propio control
de integridad sirve como control de la migración.

El simulacro completo está previsto en la fase 3 del plan, cuando todavía hay
margen para corregir, y no cuando ya sea necesario.

---

## Comprobar el despliegue

```bash
./deploy/aws/95-verificar.sh
```

Confirma tablas, llave, contenedores, funciones, interfaz y registro, y hace una
prueba de extremo a extremo del punto público: un identificador inexistente debe
responder **404**. Si responde 403, la ruta existe pero falta el permiso de
invocación de Lambda.

Esto comprueba que el despliegue quedó completo, **no** que los controles
funcionen. Eso lo evalúa Cotejo contra un criterio trazado a un marco de
referencia. La separación es deliberada: quien despliega no debería ser quien
concluye que el control está bien.

---

## Después de desplegar

1. Abrir la interfaz en la dirección que imprime `60-sitios.sh` y comprobar el
   acceso con una de las cuentas sintéticas.
2. Ejecutar el programa de auditoría:

```bash
cd cotejo && python -m cotejo ejecutar
```

Contra AWS, los ocho controles del catálogo son ejecutables. En local solo cinco
lo son, y los otros tres quedan como *no ejecutados*.
