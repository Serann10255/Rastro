# Despliegue en AWS

Fecha: 2026-10-02 · Versión: 0.4

## Estado de verificación

> **2026-10-02 — sitio por HTTPS.** Se añadió la etapa `65-sitio-https.sh` y se
> ejecutó contra la misma cuenta: el sitio responde por HTTPS con certificado
> válido y `95-verificar.sh` confirma todos los componentes, incluidas las
> comprobaciones nuevas del sitio. Una segunda ejecución de la etapa no duplica
> nada. Detalle en la
> [bitácora del 2026-10-02](../cambios/2026-10-02-sitio-https.md).

> **Ejecutado contra la cuenta del laboratorio el 2026-09-26**, desde Windows
> con Git Bash, en una cuenta vacía. La secuencia completa (`desplegar.sh`)
> termina sin errores en unos ocho minutos y `95-verificar.sh` confirma todos
> los componentes. Una segunda ejecución sobre lo ya desplegado no duplica
> recursos ni datos.
>
> La primera ejecución destapó siete defectos que en local no se veían; están
> corregidos y descritos en la
> [bitácora del 2026-09-26](../cambios/2026-09-26-despliegue-aws.md). Dos de
> ellos habrían dejado el sistema inservible con los guiones terminando en
> verde: el validador de API Gateway habría respondido 401 a toda ruta
> protegida, y el navegador no habría podido subir evidencias por falta de CORS
> en el contenedor.
>
> Además de la verificación del guion se comprobó a mano:
>
> - la consulta pública desde el navegador, del sitio en S3 hasta DynamoDB;
> - la carga de una evidencia con el enlace prefirmado que genera el propio
>   código: el objeto queda cifrado con la llave del proyecto y una carga sin
>   cifrar se rechaza;
> - las respuestas CORS de la interfaz y del contenedor, que rechaza orígenes
>   ajenos.
>
> Lo que queda abierto:
>
> - **SU-01 — indeterminado.** API Gateway descarga el documento OpenID del
>   emisor *al crear* el validador, y el sistema no tiene uno: el emisor propio
>   no es una URL válida y la interfaz no publica `/.well-known/openid-configuration`.
>   El rechazo no es de permisos, de modo que no dice nada sobre lo que permite
>   el laboratorio. Confirmarlo exige un emisor OpenID real (un grupo de
>   usuarios de Cognito, por ejemplo). No afecta al funcionamiento: cada
>   servicio valida el token ([ADR-007](../decisiones/adr-007-identidad-propia.md)).
> - **REQ-09 — parcial.** La secuencia corregida se reproduce sin editar código
>   de la aplicación ni tocar la consola, pero la primera pasada exigió corregir
>   los guiones. Queda el simulacro de migración a otra cuenta de la fase 3.

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

## Desde Windows

Los guiones son de Bash y corren en **Git Bash**. Hacen falta tres cosas que
Linux y macOS ya traen resueltas:

1. **La CLI de AWS en el `PATH` de Git Bash.** El instalador la deja en
   `C:\Program Files\Amazon\AWSCLIV2`, pero una terminal abierta antes de
   instalarla no la ve. Se reabre la terminal o se añade a mano:

   ```bash
   export PATH="$PATH:/c/Program Files/Amazon/AWSCLIV2"
   ```

2. **Un Python con `boto3`** para sembrar los datos. En Windows `python3` suele
   ser el de la Microsoft Store, sin dependencias; `20-identidad.sh` recorre
   los intérpretes y elige el primero que importa `boto3`, o el de
   `RASTRO_PYTHON` si está fijado. Lo más sencillo es un entorno virtual:

   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install boto3 pydantic fastapi "pyjwt[crypto]" pyyaml
   export PATH="$PWD/.venv/Scripts:$PATH"
   ```

3. **Node 20 o superior** para compilar la interfaz en `60-sitios.sh`.

No hace falta `zip`, que Git Bash no trae: `30-funciones.sh` usa la biblioteca
estándar de Python cuando falta, con permisos Unix explícitos para que Lambda
pueda leer el código.

### El secreto de firma

`30-funciones.sh` lo toma de `RASTRO_JWT_SECRETO` o, si no está, de
`config/.jwt.env`. Guardarlo ahí evita que un redespliegue lo cambie sin querer
y cierre todas las sesiones.

> **`config/.jwt.env` nunca se versiona.** Estuvo versionado por error en un
> repositorio público y hubo que rotarlo
> ([H-01](../cambios/2026-09-26-h01-secreto-expuesto.md)). Si se ajusta el
> `.gitignore`, esa exclusión no se toca. Si el secreto llega a publicarse,
> sacarlo del repositorio no basta: se genera uno nuevo y se ejecuta
> `30-funciones.sh`, porque el viejo queda en el historial.

Para generarlo:

```bash
printf 'RASTRO_JWT_SECRETO=%s\n' "$(openssl rand -hex 32)" > config/.jwt.env
```

Se usa hexadecimal y no base64 porque base64 puede traer `=`, `+` y `/`, que
complican el paso por la línea de comandos.

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
| `10-datos.sh` | Tablas con sus índices, llave de cifrado con rotación, contenedores con cifrado, versionado, bloqueo público, política que rechaza cargas sin cifrar y CORS para la carga directa desde el sitio (sus dos orígenes, o los de `RASTRO_ORIGENES_WEB`) |
| `20-identidad.sh` | Aprovisiona las dos organizaciones, sus diez usuarios con las contraseñas derivadas y sus datos maestros, ejecutando **el mismo guion que prepara el entorno local** apuntado a la cuenta |
| `30-funciones.sh` | Empaqueta y despliega los ocho microservicios como funciones Lambda. **Se niega a desplegar** si `RASTRO_JWT_SECRETO` no está definido o tiene menos de 32 caracteres |
| `40-api.sh` | Interfaz HTTP con CORS, prueba del validador de tokens (SU-01), rutas e integraciones. Con el proveedor propio el validador **no se asocia** a las rutas: rechazaría todo token HS256 |
| `50-registro.sh` | CloudTrail con validación de integridad de sus archivos |
| `60-sitios.sh` | Compila las interfaces, crea el contenedor del sitio y las publica |
| `65-sitio-https.sh` | Interfaz `rastro-sitio` que sirve el sitio por HTTPS, con enlaces directos en 200, y añade su origen a la regla CORS de evidencias |
| `90-configuracion.sh` | Escribe `config/deployment.json` y comprueba que no queden identificadores literales |
| `95-verificar.sh` | Confirma que cada componente existe, que el punto público responde y que el sitio responde por HTTPS |

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

### El sitio por HTTPS

El alojamiento estático de S3 solo responde por HTTP, y CloudFront, el arreglo
habitual, está impedido en el laboratorio (RE-05). La etapa `65-sitio-https.sh`
crea una segunda interfaz de API Gateway, `rastro-sitio`, que sirve los mismos
archivos por HTTPS con el certificado de Amazon para
`*.execute-api.us-east-1.amazonaws.com`, y los lee del contenedor también por
HTTPS. Diseño y alternativas en
[ADR-012](../decisiones/adr-012-sitio-https-por-api-gateway.md).

| Dirección | Protocolo | Enlaces directos | Uso |
|---|---|---|---|
| `https://<id-sitio>.execute-api.us-east-1.amazonaws.com` | HTTPS, certificado válido | 200 | **La que se comunica** |
| `http://rastro-web-<cuenta>.s3-website-us-east-1.amazonaws.com` | Solo HTTP | 404 con el índice | Se conserva para no romper enlaces ya compartidos |

El identificador de la interfaz queda en `config/.sitio.env` y en la clave
`url_sitio` de `config/deployment.json`.

**El origen HTTPS es un origen nuevo para el contenedor de evidencias.** La
regla CORS admite los dos; sin ello la consulta funcionaría por HTTPS y la carga
de evidencias fallaría en el navegador del mensajero. La regla vive en
`comun.sh` y la aplican tanto `10-datos.sh` como `65-sitio-https.sh`.

### Limitaciones conocidas del sitio

- **Solo `GET`.** Una petición `HEAD` a la dirección HTTPS responde 404. Los
  navegadores no la usan; algún monitor de disponibilidad sí.
- **Sin compresión.** API Gateway entrega los archivos tal como están en S3. El
  sitio pesa poco y no compensa añadir otra pieza para comprimirlo.
- **La dirección HTTP sigue abierta**, con sus dos defectos de siempre: puede
  alterarse en tránsito y sus enlaces directos responden 404.

---

## Qué impone el entorno

| Restricción | Efecto en el despliegue |
|---|---|
| RE-01: no se pueden crear roles | Todas las funciones comparten `LabRole`. Se declara como hallazgo permanente ([ADR-004](../decisiones/adr-004-rol-compartido.md)) |
| RE-02: la invocación anónima de URL de función está impedida | Se usa API Gateway y no URL de función |
| RE-03: solo `us-east-1`, 50 dólares | Ningún diseño multirregión; se excluye todo recurso que facture entre sesiones |
| RE-04: el entorno se pierde al terminar el curso | Toda la configuración es reproducible por comandos versionados |
| RE-05: CloudFront está impedido (ni siquiera se pueden listar distribuciones) | El sitio se sirve por HTTPS a través de API Gateway ([ADR-012](../decisiones/adr-012-sitio-https-por-api-gateway.md)) |
| RE-06: con la sesión cerrada, una política de la organización de AWS Academy puede impedir que `LabRole` descifre o lea | Las funciones no arrancan y la API responde 5xx; el sitio carga igual. **Abrir la sesión antes de usar el sistema.** Observado el 2026-10-02 y no en el cierre anterior ([bitácora](../cambios/2026-10-02-sitio-https.md#1-la-caida)) |

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

1. Abrir la interfaz en la dirección HTTPS que imprime `65-sitio-https.sh` y
   comprobar el acceso con una de las cuentas sintéticas.
2. Ejecutar el programa de auditoría:

```bash
cd cotejo && python -m cotejo ejecutar
```

Contra AWS, los once controles del catálogo son ejecutables. Los tres de
secretos en el repositorio (C-09a a C-09c) necesitan además que Cotejo se
ejecute desde una copia del repositorio git, porque revisan su historial. En
local, tres controles de infraestructura quedan como *no ejecutados*.
