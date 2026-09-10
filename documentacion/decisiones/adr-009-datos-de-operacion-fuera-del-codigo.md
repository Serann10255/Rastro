# ADR-009 · Ningún dato de operación escrito en el código

Fecha: 2026-09-10 · Estado: aceptada

## Contexto

Quedaban en el código listas que describen la operación de una empresa y no el
funcionamiento del sistema:

| Dónde | Qué había | Por qué era un problema |
|---|---|---|
| `web/src/paginas/EnvioDetalle.tsx` | Tres mensajeros con su identificador y su nombre | El día que entrara uno nuevo, nadie iba a recompilar el sitio para que apareciera. Además incluía al de la otra organización |
| `web/src/paginas/Operaciones.tsx` | Catorce módulos con su nombre, su icono y el motivo de los que faltan | Dar de alta un módulo exigía recompilar, y dos empresas no podían ver cosas distintas |
| `web/src/componentes/Estructura.tsx` | Las secciones de la navegación | Lo mismo, en la barra |
| `web/src/paginas/Envios.tsx` | Qué estados cierran un envío | Al añadir `DEVUELTO` y `CANCELADO` hubo que tocar tres pantallas; olvidar una dejaba envíos cerrados contando como abiertos |
| `cotejo/cotejo/contexto.py` | Cinco cuentas con su contraseña | Auditar otro despliegue exigía editar el programa de auditoría, y las claves quedaban versionadas |

Todas tenían la misma forma: un dato que pertenece a una organización, escrito
en un archivo que se compila.

## Decisión

**Lo que describe a una organización vive en su tabla. Lo que describe al
sistema vive en el código.** La frontera es esa y se aplica sin excepciones.

### Lo que se movió a la base de datos

**Los módulos**, como registros `MODULO#<clave>` en la tabla de maestros, uno
por organización. Cada uno lleva nombre, descripción, icono, ruta, grupos que lo
ven, orden, si va en la navegación principal, si está disponible y —cuando no lo
está— **por qué**. Un administrador puede encender y apagar los de su empresa
desde `POST /catalogos/modulos/{clave}`, y apagar exige motivo: un módulo
ausente sin motivo parece un olvido.

**Los mensajeros**, a través de `GET /equipo/mensajeros`, que devuelve los
conductores activos de la organización del token. Es una vista reducida —sujeto,
nombre y teléfono— y por eso la puede pedir un despachador, que no administra
cuentas pero sí asigna.

### Lo que se movió al catálogo del servidor

**Qué estados cierran un envío** ya lo dice `GET /catalogos/estados` en su campo
`final`. La interfaz lo consulta en lugar de repetirlo.

### Lo que sigue en el código, y por qué

| Sigue en el código | Razón |
|---|---|
| La máquina de estados y sus códigos | Es el proceso, no el dato: cambiarlo es cambiar el sistema, y hay pruebas que lo fijan |
| La matriz de autorización | Era un control de seguridad. **Matizado en [ADR-010](adr-010-roles-configurables.md)**: el catálogo de operaciones sigue en el código y es cerrado; lo que pasó a la tabla es qué operaciones agrupa cada rol |
| Las columnas del archivo de lote | Es un contrato de formato |
| La tabla de patrones de Code 128 | Es un estándar |
| El juego de iconos | Es el sistema de diseño; la base de datos guarda el **nombre** del icono, no el dibujo |

### El caso de las contraseñas

De la base de datos no pueden salir: están derivadas con PBKDF2 y no hay forma
de recuperarlas, que es justamente lo que se quiere. De modo que las de los
usuarios de prueba de Cotejo son lo único que llega por configuración
(`COTEJO_CLAVES`) y no por descubrimiento.

**Las identidades sí salen de la base de datos.** Cotejo lee el directorio del
sistema auditado para saber quién existe y con qué rol, y elige a quién probar.
En el entorno local toma las claves del mismo archivo de semilla que creó esas
cuentas, montado en solo lectura: copiarlas en su configuración significaría que
al cambiar una, el programa de auditoría dejaría de entrar sin que nadie supiera
por qué.

Si falta la clave de un rol necesario, esa prueba se reporta **no ejecutada** con
su motivo, que es la conducta correcta para una prueba que no se pudo hacer.

## Consecuencias

**Dos organizaciones pueden ver cosas distintas**, que es lo que un producto
multiempresa tiene que permitir. Apagar un módulo en una no lo apaga en la otra;
hay pruebas que lo fijan.

**Una instalación existente recibe los módulos nuevos.** El aprovisionamiento se
ejecuta siempre, también sobre una base ya sembrada, y **respeta lo que la
organización decidió**: si un administrador apagó un módulo, la actualización
conserva su estado y su motivo. Volver a encenderlo en cada despliegue
convertiría una decisión de la empresa en algo que el sistema deshace a sus
espaldas.

**Una consulta más al arrancar la interfaz.** Los módulos se piden una vez y se
consideran frescos cinco minutos: cambian cuando un administrador toca algo, no
con cada pantalla.

**Un defecto que esto ya destapó.** Al guardar el módulo, el nombre del icono se
truncaba a ocho caracteres: `recoleccion` quedaba en `recolecc` y la pantalla
dibujaba el icono genérico. Con la lista escrita en el código no habría existido
ese límite —ni el módulo, ni la posibilidad de darlo de alta sin recompilar—.
Es el coste de mover un dato a la base de datos: aparece la validación, y con
ella sus errores.
