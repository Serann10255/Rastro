# ADR-010 · Roles configurables por organización

Fecha: 2026-09-10 · Estado: aceptada · Matiza a [ADR-009](adr-009-datos-de-operacion-fuera-del-codigo.md)

## Contexto

El sistema tenía cuatro roles fijos escritos en el código. Eso obligaba a que
toda empresa repartiera el trabajo igual, y en la práctica no lo hace: la
organización de prueba tenía a su coordinadora con los roles
`despachador + administrador`, es decir, **poder de administrador porque no
había nada intermedio**. Un coordinador acabó pudiendo crear cuentas y borrar
catálogos porque el sistema no sabía expresar «más que un despachador y menos
que un administrador».

[ADR-009](adr-009-datos-de-operacion-fuera-del-codigo.md) dejó explícitamente la
matriz de autorización en el código, con este argumento: *«Es un control de
seguridad. En una tabla, quien escriba en la tabla se concede permisos.»* Esta
decisión no lo contradice: lo acota.

## Decisión

**El catálogo de operaciones sigue en el código. La composición de los roles
pasa a la tabla de la organización.**

Un rol no es un permiso: es una **selección** de permisos que ya existen. Nadie
puede inventar una operación, solo combinar las que el sistema sabe ejecutar.
Esa distinción es la que hace que abrir la configuración no sea abrir la puerta.

### Las cuatro barreras

| Barrera | Qué impide |
|---|---|
| El catálogo es cerrado y vive en `authz.py` | Escribir `sistema:todo` en la tabla no concede nada; la API lo rechaza por su nombre |
| Nadie concede lo que no tiene | Un rol con `rol:administrar` no puede promocionarse a sí mismo. El intento se registra como `escalada_de_privilegios` |
| El administrador se resuelve en el código | Ninguna edición —ni un error— deja a una organización sin nadie que pueda entrar a deshacerla |
| Separación de funciones estructural | Ningún rol, y ninguna cuenta, puede a la vez operar y leer la bitácora |

La última merece detalle. **No es un aviso, es un rechazo**, y se comprueba
sobre dos cosas distintas: sobre el rol que se guarda, y sobre la **suma de los
roles de una cuenta**. Sin lo segundo, un administrador podría añadirse el rol
de auditor —ningún rol rompería la regla por separado— y quedarse revisando su
propio rastro. Es el control C-05 que el programa de auditoría verifica, y un
control que se puede desactivar desde un formulario no es un control.

### Cómo se resuelve una autorización

`Contexto` lee los roles de la organización **una vez por petición**, de forma
perezosa. Si la tabla no responde, se cae a los roles de fábrica en lugar de
fallar: son más restrictivos que cualquier personalización razonable, de modo
que el sistema falla cerrado.

### Reparto de fábrica, revisado

| Rol | Qué cambia |
|---|---|
| **Administrador** | Ahora tiene **todas** las operaciones salvo la bitácora. Antes no podía cambiar el estado de un envío, y es el responsable de la operación |
| **Coordinador** (nuevo) | Todo lo del despachador, más autorizar detenidos y mantener catálogos. No administra cuentas ni roles |
| **Despachador** | Deja de autorizar reanudaciones. Despachar es registrar y asignar; levantar un envío parado es una decisión sobre el trabajo de otro |
| **Conductor** | Sin cambios: ve lo suyo, marca el avance, adjunta la prueba |
| **Auditor** | Gana `rol:consultar`. El mapa de quién puede qué es objeto de la auditoría |

**Por qué el administrador no lee la bitácora.** Es la única excepción a «puede
hacer todo», y es deliberada: el administrador opera y el auditor revisa lo
operado, incluido lo que hizo el administrador.

## Consecuencias

**La interfaz decide por permiso, no por nombre de rol.** `/auth/yo` devuelve
los permisos efectivos y las pantallas preguntan `puede("envio:asignar")` en
lugar de `tieneGrupo("despachador")`. Sin esto, un rol que la empresa cree
mañana no vería nada: no aparece en ninguna lista escrita en una pantalla. No es
un control —el servidor decide en cada operación— sino la diferencia entre
ofrecer un botón útil y ofrecer uno que responderá 403.

**Asignar un rol inexistente se rechaza.** Antes los nombres desconocidos se
descartaban en silencio; ahora se conservan, porque pueden ser roles propios.
Un nombre mal escrito crearía una cuenta sin poder hacer nada y nadie sabría por
qué esa persona no puede trabajar.

**Un rol en uso no se elimina**, y los de fábrica no se eliminan nunca. Pueden
ajustarse o dejar de asignarse.

**El aprovisionamiento no pisa lo personalizado.** Los roles de fábrica se
escriben en la tabla al preparar el entorno solo si no existen: si un
administrador ajustó el despachador, una actualización posterior no lo devuelve
a los valores de fábrica a sus espaldas.

**Cotejo sigue midiendo lo mismo.** El control C-05 comprueba que una operación
no autorizada se rechaza y queda registrada, y eso no depende de cómo se
compongan los roles. Lo que sí cambia es que ahora hay una superficie más que
auditar: la configuración de roles de cada organización, cuyos cambios quedan en
la bitácora con la lista de operaciones concedidas.
