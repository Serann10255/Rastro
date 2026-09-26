# Cambios · 2026-09-26 · H-01: secreto de firma expuesto en el repositorio público

Incidente de seguridad encontrado por el equipo durante el primer despliegue en
AWS, corregido y verificado el mismo día, **antes de la ejecución del programa
de auditoría**. Se registra como hallazgo con su ciclo completo porque es
material de auditoría y no solo una incidencia: es exactamente el tipo de
defecto que Cotejo debería detectar, y su catálogo no lo cubre.

---

## H-01 · Secreto de firma de tokens expuesto en repositorio público

| Atributo | Contenido |
|---|---|
| **Condición** | El archivo `config/.jwt.env`, con el secreto de firma de los tokens de sesión, quedó versionado en el repositorio `Serann10255/Rastro`, de acceso público. |
| **Criterio** | La rúbrica institucional detiene para revisión cualquier entrega con secretos expuestos. ISO/IEC 27001 exige proteger la información de autenticación. |
| **Causa** | La exclusión del archivo existía en `.gitignore`: se agregó en `40ddca6`. Se retiró junto con las de los demás archivos generados para poder versionar las evidencias del despliegue; el retiro quedó registrado en `51da2c1`. Con la exclusión retirada, el archivo se versionó en `be75812`. La causa de fondo es haber retirado las exclusiones en bloque y no una por una. |
| **Efecto** | Cualquier persona con acceso al repositorio podía firmar un token con rol de administrador de cualquier organización sobre el sistema desplegado: leer, crear y modificar envíos, usuarios y roles. |
| **Corrección** | Rotación del secreto, redespliegue de las ocho funciones con el secreto nuevo y exclusión del archivo en `.gitignore` con una advertencia para que no vuelva a retirarse. |
| **Verificación** | Las ocho funciones tienen el secreto nuevo y ninguna el expuesto (comparación de huellas). Un token firmado con el secreto expuesto recibe **401, firma inválida**, en seis rutas protegidas. |
| **Explotación** | Sin indicios. Durante la ventana de exposición ninguna función con rutas protegidas recibió invocaciones distintas de las de la verificación del despliegue. |
| **Estado** | **Corregido** antes de la ejecución del programa de auditoría. |
| **Evidencia** | `evidencias-despliegue/20260926T232257Z-rotacion-secreto.txt` |

---

## Línea de tiempo (UTC)

| Hora | Hecho | Fuente |
|---|---|---|
| 22:54:19 | Se agrega la exclusión de `config/.jwt.env` | commit `40ddca6` |
| 22:54:38 | Se versiona `config/.jwt.env` | commit `be75812` |
| **22:54:43** | **Push a `main`: el secreto queda público** | API pública de GitHub, `PushEvent` |
| 23:00:20 | Se retiran del `.gitignore` las exclusiones de archivos generados | commit `51da2c1` |
| ≈23:03 | Detección durante la revisión del despliegue | esta sesión de trabajo |
| 23:17:39 | Inicio del redespliegue con el secreto nuevo | `30-funciones.sh` |
| 23:18:21 – 23:21:32 | Cada función pasa al secreto nuevo, de `auth` a `dashboard` | `LastModified` de cada función |
| 23:22:59 | Verificación: el secreto expuesto ya no valida | archivo de evidencia, secciones 1 y 2 |
| 23:24:33 | `95-verificar.sh` posterior a la rotación: todo verificado | `20260926T232402Z-verificacion.txt` |
| después | El archivo deja de versionarse | commit `13d33fc` |

**Ventana de exposición: unos 27 minutos**, de las 22:54:43 a las 23:21:32.

---

## Por qué se rotó antes de sacar el archivo del repositorio

Borrar el archivo y hacer commit lo quita de la rama, pero **queda en el
historial**, y el historial de un repositorio público lo puede leer cualquiera
con `git log -p`. El secreto se considera comprometido desde el momento en que
tocó el repositorio público, hagan lo que hagan después con el historial. Lo que
de verdad cierra el agujero es que deje de ser válido.

Por eso el orden fue: rotar y redesplegar, verificar que el secreto expuesto no
valida, y solo después dejar de versionar el archivo. **El historial no se
reescribió**: el valor que queda ahí ya no sirve, y reescribir la rama principal
de un repositorio compartido obligaría a cada integrante a rehacer su copia. Es
cosmético y queda a decisión del equipo.

## Cómo se descartó la explotación

Un token falsificado solo sirve en las rutas protegidas. Se consultó en
CloudWatch cuántas veces se invocó cada función durante la ventana:

| Función | Invocaciones | Explicación |
|---|---|---|
| `rastro-public` | 4 | Las cuatro ejecuciones de `95-verificar.sh` (22:59, 23:00, 23:04 y 23:05) |
| `rastro-masters` | 4 | Las mismas: la verificación llama a la ruta abierta `/catalogos/estados` |
| Las otras seis | 0 | — |

Todo lo invocado se explica por la verificación del despliegue. La conclusión
tiene un límite que conviene declarar: la métrica cuenta invocaciones, no
peticiones individuales, y la interfaz HTTP no tiene configurado un registro
de acceso que permita ver cada petición. Con cero invocaciones en las funciones
protegidas, sin embargo, no hay por dónde haber usado el token. Activar ese
registro de acceso queda como recomendación.

## La verificación no expone nada nuevo

El archivo de evidencia no contiene ningún secreto ni token: solo los primeros
16 caracteres de la huella SHA-256 de cada secreto, suficientes para distinguir
el nuevo del expuesto sin revelar ninguno. El token de prueba se firmó con el
secreto ya invalidado, con un usuario ficticio y **sin roles**, de modo que ni
siquiera un fallo de la rotación le habría dado permisos. Y se envió solo
después de comprobar que ninguna función conservaba el secreto expuesto.

---

## Lo que el hallazgo deja para el programa de auditoría

**Un control nuevo: C-09, secretos en el repositorio.** Ya está en el catálogo
(versión 0.3), con tres comprobaciones y no una:
[C-09a, C-09b y C-09c](2026-09-26-c09-secretos-en-el-repositorio.md). Su
primera ejecución contra el repositorio y el despliegue da lo que este hallazgo
anticipa:

| Control | Resultado | Qué dice |
|---|---|---|
| C-09a · árbol actual | BIEN | Ningún secreto versionado en `eca3475` |
| C-09b · historial | MAL | `config/.jwt.env` en `be75812`, huella `984383820f91ddde`, ya fuera del árbol |
| C-09c · vigencia | BIEN | Ese secreto y el de desarrollo se rechazan con 401 por firma inválida |

La huella que reporta C-09b es la misma de la evidencia de rotación: el papel de
Cotejo y este hallazgo se cruzan sin que ninguno contenga el secreto. La
corrección pendiente es reescribir el historial, y C-09b seguirá saliendo MAL
hasta que se haga.

**Los papeles de trabajo no van al repositorio.** Enumeran las debilidades del
sistema auditado, y publicarlos sería el mismo error que el secreto. El
apartado 12.4 del documento de Cotejo ya limita la circulación del informe a
los destinatarios definidos. En el documento se cita cada papel por su
identificador y su huella, no por su contenido.

**Cotejo sella con huellas, no con firmas.** Cada papel lleva la huella SHA-256
de su evidencia (`cotejo/cotejo/papeles.py`), y `python -m cotejo verificar`
las recalcula. No hay un par de llaves, de modo que **no existe una llave
pública que publicar**. Con huellas, el docente puede comprobar que los papeles
que recibe por el canal restringido son los mismos que cita el documento, pero
necesita tenerlos. Si se quiere que verifique sin acceder a ellos, hace falta
firmar el índice con un par de llaves y publicar la pública; eso sería una
funcionalidad nueva de Cotejo.
