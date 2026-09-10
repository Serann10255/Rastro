# Servicio `auth` — identidad, sesiones y cuentas

Ubicación: `services/auth/` · Puerto local: 8001

## Qué hace

Es el proveedor de identidad del sistema. Autentica contra un directorio propio
—contraseñas derivadas, nunca en claro—, emite la sesión y administra las
cuentas de la organización.

| Operación | Quién | Para qué |
|---|---|---|
| `POST /auth/token` | abierta | Autentica y emite token de acceso + refresco |
| `POST /auth/refrescar` | abierta | Renueva el acceso y **rota** el refresco |
| `POST /auth/salir` | autenticado | Revoca la sesión en el servidor |
| `GET /auth/yo` | autenticado | Identidad, permisos y empresa de la sesión |
| `POST /auth/clave` | autenticado | Cambia la propia contraseña y cierra las demás sesiones |
| `GET /auth/roles` | abierta | Catálogo de operaciones del sistema y roles de fábrica |
| `GET /roles` | `rol:consultar` | Roles de la organización, con lo que concede cada uno |
| `POST /roles` · `POST /roles/{clave}` | `rol:administrar` | Crear un rol o cambiar sus permisos |
| `POST /roles/{clave}/eliminar` | `rol:administrar` | Eliminar un rol propio que nadie use |
| `GET /usuarios` | administrador | Usuarios de la organización |
| `POST /usuarios` | administrador | Crea un usuario |
| `POST /usuarios/{correo}` | administrador | Cambia rol, nombre, estado o contraseña |
| `GET /empresa` | autenticado | Datos de la organización y su resumen de cuentas |
| `GET /equipo/mensajeros` | administrador, despachador | Conductores activos, para asignarles un envío |

## Por qué existe

El diseño original delegaba la identidad en Amazon Cognito y aquí solo había un
emisor de demostración que leía las claves **en texto plano** de un archivo. Eso
servía para arrancar y para nada más.

Al pasar el sistema a un TMS utilizable, las cuentas tienen que administrarse
desde la propia aplicación: dar de alta un mensajero no puede exigir entrar a la
consola del proveedor. Cognito no lo permite sin permisos de administración que
el laboratorio no concede. El razonamiento completo, con lo que se gana y lo que
se pierde, está en
[ADR-007](../../decisiones/adr-007-identidad-propia.md).

**Cognito sigue siendo sustituible.** Los demás servicios solo conocen la forma
del token, no quién lo firmó.

## Decisiones

**Contraseñas con PBKDF2-HMAC-SHA256, 600 000 iteraciones y sal por contraseña.**
Argon2id sería mejor pero exige una dependencia compilada para una plataforma
distinta de la del equipo. El formato almacenado lleva delante su algoritmo y su
coste, de modo que migrar no invalida las contraseñas: se rederivan al iniciar
sesión. Véase `libs/rastro_core/passwords.py`.

**Dos tokens.** El de acceso vive una hora y lleva grupos; el de refresco vive
doce y **no los lleva**, para que un cambio de rol surta efecto en la siguiente
renovación en lugar de esperar a que caduque.

**El refresco se rota.** Usarlo invalida el anterior. Si alguien roba uno y lo
usa, el legítimo deja de funcionar y el robo se nota.

**Las sesiones se revocan en el servidor.** Se registran en el usuario, con tope
de `MAX_SESIONES = 5`; sin tope, la lista crecería sin límite. Cerrar sesión
borra el identificador: sin eso, un token copiado seguiría sirviendo hasta
caducar.

**Credenciales inválidas responden lo mismo** tanto si el usuario no existe como
si la clave es incorrecta o la cuenta está inactiva. Y cuando el usuario no
existe se verifica contra un **señuelo**, para que el tiempo de respuesta no
delate la diferencia: sin eso, medir la latencia enumera las cuentas.

**No se puede quedar la organización sin administradores.** La comprobación
(`_exigir_que_quede_un_administrador`) cubre a la vez el cambio de rol y la
desactivación, porque ambos caminos llevan al mismo bloqueo irreversible.

**Un administrador no puede desactivarse a sí mismo.** Es el error de
configuración más fácil de cometer y el más caro de deshacer.

**La vista del equipo es reducida a propósito.** `GET /equipo/mensajeros`
devuelve sujeto, nombre y teléfono de los conductores activos, y por eso la
puede pedir un despachador, que no administra cuentas pero sí asigna. Existe
porque la pantalla de asignación llevaba tres mensajeros escritos con su
identificador: el día que entrara uno nuevo, nadie iba a recompilar el sitio
para que apareciera. Véase
[ADR-009](../../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md).

**Un mensajero desactivado deja de aparecer.** Asignarle un envío a una cuenta
desactivada produce un envío que nadie puede mover, y el error solo se ve cuando
ya lleva un día parado.

**Los roles son de la organización y se configuran desde el sistema.** El
catálogo de operaciones sigue en el código y es cerrado; lo que vive en la tabla
es qué operaciones agrupa cada rol. Cuatro barreras lo sostienen —catálogo
cerrado, nadie concede lo que no tiene, el administrador se resuelve en código y
separación de funciones estructural— y están detalladas en
[roles-y-permisos](../roles-y-permisos/README.md) y
[ADR-010](../../decisiones/adr-010-roles-configurables.md).

**`/auth/yo` devuelve los permisos efectivos.** La interfaz los necesita para
decidir qué ofrecer: con roles personalizables, preguntar por el nombre del rol
dejó de servir. No son un control; el servidor decide en cada operación.

**Los intentos fallidos quedan en la bitácora**, con el correo solicitado. Es lo
que permite distinguir un usuario que olvidó su clave de un ataque por fuerza
bruta.

**Descartado: registro autónomo de organizaciones.** Sigue excluido del alcance
—véase [ADR-006](../../decisiones/adr-006-ampliacion-de-alcance-a-tms.md)—: las
empresas se aprovisionan con el despliegue.

## Dependencias y relaciones

- **Depende de**: `rastro_core.maestros` (directorio de usuarios y empresa),
  `rastro_core.passwords`, `rastro_core.security` (emisión y validación),
  `rastro_core.authz` (matriz de permisos) y `rastro_core.audit`.
- **Depende de él**: toda la interfaz web y todos los demás servicios, que
  validan el token que este emite. También las pruebas sustantivas de Cotejo,
  que necesitan autenticarse como distintos roles y organizaciones.
- **Escribe** en la tabla de maestros y en la bitácora. No toca envíos.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz. La pantalla que lo consume es
`web/src/paginas/Administracion.tsx`, documentada en
[interfaz-web](../interfaz-web/README.md).
