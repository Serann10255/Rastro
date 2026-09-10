# ADR-007 · Directorio de usuarios propio en lugar de Amazon Cognito

Fecha: 2026-09-10 · Estado: aceptada · Sustituye la identidad de [ADR-001](adr-001-arquitectura-sin-servidor.md)

## Contexto

El diseño original delegaba la identidad en un grupo de usuarios de Amazon
Cognito: emitía el token, guardaba las contraseñas y gestionaba los grupos. El
entorno local usaba un emisor de demostración que leía los usuarios de un archivo
con las claves **en texto plano**, lo cual estaba bien para arrancar y mal para
cualquier otra cosa.

Al ampliar el alcance a un sistema de gestión de transporte (ADR-006), el
sistema necesita administrar cuentas desde la propia aplicación: crear usuarios,
cambiar roles, desactivar accesos. Cognito no lo permite sin permisos de
administración que el laboratorio no concede, y depender de la consola del
proveedor para dar de alta a un mensajero no es una operación que una
microempresa vaya a hacer.

## Decisión

El sistema tiene su propio servicio de identidad.

### Contraseñas

PBKDF2-HMAC-SHA256 de la biblioteca estándar, con 600 000 iteraciones —la cifra
que OWASP recomienda para esa combinación— y sal aleatoria por contraseña. El
formato almacenado es `algoritmo$iteraciones$sal$hash`.

**Argon2id sería mejor**: resiste ataques con hardware dedicado que PBKDF2 no
resiste igual de bien. No se usa porque exige una dependencia compilada, y el
paquete de una función Lambda se construye para una plataforma distinta de la
del equipo de desarrollo. Una dependencia binaria mal compilada falla al
desplegar, en el laboratorio, con las credenciales caducando cada cuatro horas.

La limitación se declara y el formato deja la puerta abierta: como cada registro
lleva delante su algoritmo y su coste, migrar a Argon2 no invalida las
contraseñas existentes; se rederivan al iniciar sesión, que es el único momento
en que el sistema tiene la contraseña en claro.

### Sesión

Dos tokens con propósitos distintos:

| Token | Vigencia | Para qué |
|---|---|---|
| Acceso | 1 hora | Operar. Lleva sujeto, grupos, organización y sesión |
| Refresco | 12 horas | Solo pedir un token de acceso nuevo |

El de refresco **no lleva grupos**: si los llevara, un cambio de rol no surtiría
efecto hasta que caducara. Al renovar se releen del registro del usuario.

El refresco **se rota**: al usarlo, el anterior deja de valer. Así, si alguien
roba uno y lo usa, el legítimo deja de funcionar y el robo se nota, en lugar de
convivir en silencio con el atacante.

Las sesiones se registran en el usuario y se pueden **revocar**. Borrar el token
del navegador basta para el uso normal, pero no si el token ya se copió: revocar
es lo que hace que cerrar sesión signifique algo.

### Contra la enumeración de cuentas

Un fallo de credenciales responde lo mismo tanto si el usuario no existe como si
la clave es incorrecta o la cuenta está inactiva. Y cuando el usuario no existe
se verifica igualmente contra un **señuelo**, para que el tiempo de respuesta no
delate la diferencia: sin eso, medir la latencia permite enumerar las cuentas.

## Consecuencias

**A favor.** El sistema administra sus propias cuentas, que es lo que un TMS
tiene que hacer. Los intentos fallidos quedan en la bitácora, que es el registro
que permite detectar un ataque por fuerza bruta. Cambiar la contraseña cierra las
demás sesiones. Desactivar una cuenta cierra las suyas de inmediato.

**En contra.** El equipo se hace responsable del almacenamiento de credenciales,
que antes era del proveedor. Es una responsabilidad real y por eso las decisiones
de arriba están escritas: cada una tiene su razón y su límite declarado.

**Cognito sigue siendo posible.** Los demás servicios solo conocen la forma del
token, no quién lo emitió. Delegar en Cognito en un despliegue productivo no
exige tocar nada más que el servicio de identidad.

**El secreto de firma es ahora crítico.** Se firma con clave compartida (HS256).
Quien conozca el secreto puede firmar un token de administrador de cualquier
organización. Por eso `30-funciones.sh` **se niega a desplegar** si
`RASTRO_JWT_SECRETO` no está definido o tiene menos de 32 caracteres, en lugar de
caer al valor de desarrollo que está en el repositorio.

**Efecto sobre el validador de API Gateway.** Ese validador solo verifica firmas
de clave pública (RS256) contra un JWKS, de modo que no aplica a un token HS256.
No es una pérdida: la alternativa que el documento ya contemplaba —validar el
token dentro de cada función— está implementada desde el principio, y por eso el
sistema funciona igual con validador o sin él. El supuesto SU-01 se sigue
comprobando en el despliegue para dejar constancia.

**Coste de las pruebas.** Derivar con 600 000 iteraciones lleva la suite de
segundos a minutos, y una suite lenta es una suite que nadie ejecuta. El coste es
configurable por variable de entorno y las pruebas lo bajan a 1 000. Es seguro
porque lo que se verifica es el mecanismo —que la contraseña no se almacena en
claro, que la verificación funciona, que el formato permite migrar— y no el
coste, que es un parámetro. En cualquier entorno con datos reales se queda en el
valor por omisión.
