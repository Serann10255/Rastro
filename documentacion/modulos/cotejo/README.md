# Módulo `cotejo` — programa de auditoría

Ubicación: `cotejo/` · Proyecto de la asignatura Auditoría de Sistemas (ISD39)

## Qué hace

Ejecuta de forma automatizada un catálogo de controles sobre Rastro y produce
**papeles de trabajo reproducibles**: cada prueba conserva el procedimiento
exacto, su salida literal, la marca de tiempo, la identidad bajo la que se
ejecutó y la huella criptográfica del archivo de evidencia.

El problema que resuelve: *un control declarado no es un control verificado*. Un
diagrama puede afirmar que el acceso está restringido por rol sin que nadie haya
comprobado qué ocurre cuando un usuario del rol equivocado invoca la operación.

## El vacío que ocupa

| Enfoque | Cubre la infraestructura | Cubre la lógica de la aplicación | Evidencia reproducible |
|---|---|---|---|
| Revisión manual con capturas | Parcial | Sí, según quien la ejecute | **No** |
| Lista de verificación documental | No | No | No acredita el estado real |
| Servicio gestionado de evaluación | Sí | **No** | Sí, dentro de su plataforma |
| **Cotejo** | Sí | **Sí** | **Sí** |

Los servicios gestionados no pueden saber si un usuario del rol conductor logra
crear un envío ni si un usuario de una organización alcanza los datos de otra:
esas reglas viven en el código. Las revisiones manuales sí llegan hasta ahí, pero
producen evidencia que nadie puede repetir. Ese cruce es lo que ocupa Cotejo.

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `catalogo/controles.yaml` | Matriz de once controles con marco, criterio, evidencia esperada y su versión en lenguaje llano; más el diccionario |
| `cotejo/contexto.py` | Contra qué sistema se ejecuta y con qué usuarios de prueba |
| `cotejo/ejecutor.py` | Recorre el catálogo, produce un papel por control |
| `cotejo/papeles.py` | Almacén: índice, evidencia y huellas |
| `cotejo/pruebas/cumplimiento.py` | C-01 a C-04: configuración, en modo lectura |
| `cotejo/pruebas/sustantiva.py` | C-05 a C-07: ejercitan la aplicación |
| `cotejo/pruebas/integridad.py` | C-08: recalcula la cadena de la bitácora |
| `cotejo/pruebas/secretos.py` | C-09a a C-09c: secretos en el árbol, en el historial y su vigencia |
| `cotejo/informe.py` | Hallazgos con condición, criterio, causa y efecto |
| `cotejo/cli.py` | `ejecutar`, `verificar`, `comparar`, `catalogo`, `glosario` |

## El catálogo

Se deriva de marcos de referencia reconocidos y no de la apreciación del equipo,
de modo que un control ausente pueda atribuirse a una decisión de alcance y no a
un olvido.

| Id | Control | Marco | Tipo |
|---|---|---|---|
| C-01 | Registro de actividad activo con validación de integridad | CIS; NIST SP 800-92 | cumplimiento |
| C-02 | Evidencias cifradas con llave propia y rotación | ISO/IEC 27001 A.8.24 | cumplimiento |
| C-03 | Contenedor sin acceso público | CIS | cumplimiento |
| C-04 | Contenedor con versionado | ISO/IEC 27001 A.8.13 | cumplimiento |
| C-05 | Autorización por rol, con registro del rechazo | COBIT 2019; OWASP A01 | sustantiva |
| C-06 | Aislamiento entre organizaciones | COBIT 2019; OWASP A01 | sustantiva |
| C-07 | Transiciones de estado inválidas rechazadas | COBIT 2019 | sustantiva |
| C-08 | Bitácora detecta su propia alteración | Schneier y Kelsey (1999) | integridad |
| C-09a | Ningún secreto versionado en el árbol actual | ISO/IEC 27001 A.5.17 y A.8.4; CWE-798 | cumplimiento |
| C-09b | Ningún secreto en el historial de commits | ISO/IEC 27001 A.5.17 y A.8.4; CWE-798 | cumplimiento |
| C-09c | Ningún secreto hallado sigue siendo aceptado por el sistema | ISO/IEC 27001 A.5.17; NIST SP 800-57 | sustantiva |

### C-09: secretos en el repositorio

Se agregó (catálogo 0.3, 2026-09-26) después de un incidente real: el secreto de
firma de los tokens quedó versionado en el repositorio público y hubo que
rotarlo ([H-01](../../cambios/2026-09-26-h01-secreto-expuesto.md)). Ninguno de
los ocho controles originales lo habría detectado.

**Son tres comprobaciones, no una ni dos.** «Hay un secreto en el repositorio»
mezcla condiciones de riesgo muy distinto. Separar árbol (C-09a) e historial
(C-09b) localiza la desviación, pero no distingue un secreto vivo de uno
invalidado: uno que se borró del árbol **sin rotarse** sale bien en C-09a y mal
en C-09b, y sigue abriendo el sistema. Lo que decide el riesgo residual es
C-09c, que prueba cada secreto hallado: firma con él un token sin roles, a
nombre de un usuario inexistente, y comprueba que el sistema lo rechace por
firma inválida. Cada uno tiene su severidad declarada de antemano: alta, media
y alta.

**Ningún papel contiene el valor hallado.** Se reporta tipo, ruta, línea o
commit y los primeros 16 caracteres de la huella SHA-256, que bastan para
cruzarlo con otra evidencia sin revelarlo. Los papeles circulan hacia el
docente, y un papel que cita el secreto lo vuelve a exponer. El token de C-09c
tampoco llega al papel. Hay una prueba que lo verifica sobre los tres
controles.

**Qué no cuenta como secreto** está declarado en la prueba: referencias a
variables (`${...}`, `\$(...)`), marcadores (`%s`), valores más cortos que el
mínimo de su tipo y las claves de ejemplo que publica AWS. El secreto de
desarrollo de la pila local es **público por diseño** y no es hallazgo en C-09a
ni C-09b, pero C-09c lo prueba fuera del entorno local: un valor publicado solo
es aceptable mientras ningún despliegue real lo acepte.

**Necesita el repositorio git.** El contenedor de la API no lo lleva; ahí los
tres quedan *sin ejecutar* con ese motivo, en lugar de concluir sin mirar. Para
evaluarlos, Cotejo se ejecuta desde una copia del repositorio.

### Cada control se declara dos veces

Además del enunciado técnico, cada control declara su versión en lenguaje llano,
y el ejecutor **rechaza el catálogo si falta**:

| Campo | Ejemplo (C-06) |
|---|---|
| `pregunta` | ¿Una empresa puede ver los envíos de otra empresa? |
| `en_simple` | Creamos un envío con la empresa A. Luego entramos como la empresa B y pedimos ese mismo envío por todas las puertas del sistema… |
| `si_falla` | Una empresa vería los clientes, las direcciones y los movimientos de su competencia. Eso es una fuga de información, no un defecto de uso. |

Se exige igual que el criterio y por la misma razón: escribir la explicación
después de ver el resultado permitiría acomodarla al resultado. Un control que
solo sabe decirse en vocabulario técnico no se puede discutir con quien decide,
y un hallazgo que nadie entiende no se corrige. Véase
[ADR-011](../../decisiones/adr-011-doble-registro-en-la-interfaz.md).

Las tres respuestas se muestran como **BIEN**, **MAL** y **SIN REVISAR**, con el
término técnico al lado. Siguen siendo tres: llamar «sin revisar» a lo no
ejecutado lo separa de «bien» tanto como `NO_EJECUTADA` lo separa de `CONFORME`.

## Decisiones

**El catálogo nombra pruebas; no importa código.** Un mapa resuelve el nombre a
una función. Así un catálogo mal formado no puede ejecutar nada arbitrario, y el
ejecutor falla al cargarlo en vez de a mitad de la ejecución.

**El criterio se declara antes de ejecutar.** El catálogo se valida por completo
antes de la primera prueba. Declarar el criterio después permitiría acomodarlo al
resultado, que es justamente lo que el programa existe para evitar.

**Un control no ejecutado no es un control conforme.** La conclusión
`NO_EJECUTADA` es una tercera categoría, no un matiz de conformidad. En el
entorno local, tres controles de infraestructura no pueden comprobarse; el
informe lo declara y la cobertura lo refleja (`5/8` con el catálogo original de
ocho controles). Presentar la ausencia de
una capacidad como conformidad sería el peor resultado posible.

**Cada prueba se valida en los dos sentidos.** Comprobar que una prueba informa
conformidad no demuestra que sirva; hay que comprobar que detecta la desviación
cuando existe. Es el indicador más exigente del proyecto y el que encontró un
defecto real (véase abajo).

**El lenguaje llano vive en el catálogo, no en cada interfaz.** La consola, el
informe en texto y la web leen las mismas frases. Si cada pantalla escribiera la
suya, acabarían diciendo cosas distintas del mismo control, y la del informe es
la que vale.

**El informe abre en lenguaje llano y sigue en el técnico.** Sección 1, «En
palabras simples»: qué es esto, qué salió en una frase con las tres cifras
juntas, y cómo se leen las tres respuestas. Después, el registro completo del 2
al 5. El orden no es cosmético: quien decide sobre un hallazgo no suele ser
quien lo escribió, y un informe que exige vocabulario para llegar a la primera
conclusión se queda sin leer.

**El programa nunca modifica lo que audita.** La alteración controlada de C-08 se
hace sobre una copia descargada, jamás sobre la bitácora del sistema.

**Un fallo en un control no detiene la ejecución.** El control queda marcado como
`NO_EJECUTADA` con su motivo. Una ejecución interrumpida produciría papeles
incompletos que podrían confundirse con pruebas fallidas (riesgo R-05).

**El código de salida distingue tres situaciones**: `0` conforme, `1`
desviaciones, `3` algo no pudo comprobarse. Una integración automática no debería
tratar igual un control que falló y uno que no se probó.

## El primer defecto: el que encontró la validación en doble sentido

En la primera ejecución real, Cotejo reportó C-08 como **desviado**: *el
verificador NO detectó la alteración con hash recalculado*.

El defecto estaba en la propia prueba: alteraba el campo `resultado` poniéndole
`"ALLOW"` sobre un registro que ya era `ALLOW`. La copia quedaba idéntica al
original, el verificador informaba cadena válida —correctamente— y la prueba lo
interpretaba como fallo de detección.

Se corrigió con valores que ningún registro real puede tener y una guarda que
comprueba que la copia difiere del original antes de evaluarla. Sin la validación
en doble sentido, esta prueba habría podido producir el resultado contrario —un
falso conforme— sin que nadie lo notara.

## El segundo defecto: el contrato con el sistema auditado

Cuando Rastro sustituyó su emisor de tokens por un servicio de identidad, el
campo del inicio de sesión pasó de `usuario` a `correo` y `/auth/yo` pasó a
devolver el usuario anidado. **Cotejo siguió compilando y siguió pasando sus 23
pruebas.** Lo que dejó de funcionar fue su autenticación contra el sistema
auditado: C-05 y C-06 se reportaron como *no ejecutados*.

Es la peor forma de fallar para un programa de auditoría, porque **se parece a
un resultado**. La tercera categoría existe para las capacidades que el entorno
no ofrece, no para los defectos del propio programa; confundir una cosa con la
otra vacía de sentido la distinción.

Ahora hay cuatro pruebas —`cotejo/tests/test_contrato_con_rastro.py`— que
levantan el servicio de identidad real y le hablan con el propio código de
Cotejo. No copian la forma esperada del contrato: la ejercitan. Una copia se
quedaría atrás igual que se quedó el código.

**Las cuentas de prueba ya no están escritas en el programa.** Antes eran cinco
correos con su clave, su organización y su rol, versionados en `contexto.py`.
Ahora las **identidades salen del directorio del sistema auditado** —Cotejo lee
la tabla de maestros y elige, por organización y por rol, contra quién ejecutar—
y solo las claves llegan por configuración.

Las claves no pueden salir de la base de datos: están derivadas con PBKDF2 y no
hay forma de recuperarlas, que es justamente lo que se quiere de un sistema que
guarda contraseñas. Llegan por `COTEJO_CLAVES` (un JSON de correo a clave) y, en
el entorno local, del **mismo archivo de semilla que creó esas cuentas**, montado
en solo lectura: copiarlas en la configuración de Cotejo significaría que al
cambiar una, el programa de auditoría dejaría de entrar sin que nadie supiera por
qué.

Si falta la clave de un rol necesario, esa prueba se reporta **no ejecutada** con
su motivo. Es la conducta correcta: una prueba que no se pudo hacer no es una
prueba conforme. Véase
[ADR-009](../../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md).

## Limitaciones declaradas

**Independencia.** El equipo audita un sistema que él mismo construyó, lo que
constituye una amenaza de autorrevisión. Se atiende con rotación interna, con un
programa determinista cuyo resultado no depende del criterio de quien lo ejecuta,
y con la reejecución por un integrante distinto. Aun así, **no alcanza el grado
de independencia de una revisión externa**, y el informe lo hace constar.

**Cobertura.** Solo se verifica lo que está en el catálogo. Un control ausente no
fue evaluado.

**Permisos.** El programa se ejecuta con el rol compartido del laboratorio y
dispone de permisos de escritura sobre lo que audita. Se declara como hallazgo
permanente H-PERM-02, no como condición aceptable de diseño.

**El almacén detecta la manipulación, no la previene.** Prometer prevención donde
solo hay detección sería una afirmación que la evidencia no sostiene.

**El sellado es por huella, no por firma.** Cada papel lleva la huella SHA-256
de su evidencia, y `python -m cotejo verificar` la recalcula. Eso permite a
quien recibe los papeles confirmar que son los mismos que cita el documento,
pero exige tenerlos. No hay un par de llaves ni una llave pública: verificar sin
acceder a los papeles requeriría firmar el índice con una llave asimétrica y
anclarlo en un registro externo. Queda como trabajo futuro.

**La numeración de hallazgos es por ejecución.** El informe llama H-01, H-02…
a las desviaciones de cada ejecución, en orden de catálogo. No coincide con los
identificadores de hallazgo del documento de auditoría, que son estables entre
ejecuciones: al integrar un informe hay que cruzarlos por control y por huella,
no por número.

## Dependencias y relaciones

- **Depende de**: `rastro_core.audit` (reutiliza el mismo verificador de cadena),
  `httpx`, `boto3`, `pyyaml`.
- **Audita a**: Rastro, a través de su interfaz HTTP y de la interfaz de
  configuración del proveedor.
- La reutilización del verificador es deliberada y se declara: no es una
  implementación independiente. Lo que sí es independiente es el **recálculo**,
  hecho sobre una copia descargada y contrastado con lo que informa el servicio.

## Comportamiento responsive

No aplica: el programa se ejecuta por línea de comandos y produce archivos. El
informe en texto plano usa un ancho fijo de 78 columnas para que sea legible en
cualquier terminal y versionable junto al código.
