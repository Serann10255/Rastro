# Módulo `roles-y-permisos`

Ubicación: `libs/rastro_core/authz.py` · `services/auth/` (API) · `web/src/paginas/Roles.tsx` (pantalla)

## Qué hace

Decide quién puede hacer qué, y permite que cada organización lo configure sin
tocar el código.

| Pieza | Responsabilidad |
|---|---|
| `authz.py` | El **catálogo cerrado** de operaciones, los roles de fábrica y la resolución de permisos |
| `maestros.py` | Los roles de cada organización, como registros `ROL#<clave>` |
| `services/auth` | `GET /auth/roles`, `GET /roles`, `POST /roles`, `POST /roles/{clave}`, `POST /roles/{clave}/eliminar` |
| `Roles.tsx` | La pantalla: tarjetas por rol y editor de permisos agrupado por área |

## Los cinco roles de fábrica

| Rol | Para qué | Lo que **no** puede |
|---|---|---|
| **Administrador** | Responsable de la operación y de las cuentas. Tiene todas las operaciones | Leer la bitácora |
| **Coordinador** | Despacha, autoriza envíos detenidos y mantiene catálogos | Administrar cuentas ni roles |
| **Despachador** | Registra envíos, los asigna y sigue su avance | Autorizar detenidos, editar catálogos, tocar cuentas |
| **Conductor** | Ve sus envíos, sale a ruta con ellos compartiendo su ubicación, marca el avance, adjunta la prueba de entrega | Despachar, autorizar, ver evidencias ajenas, seguir a otros conductores |
| **Auditor** | Revisa: bitácora, integridad de la cadena, cuentas y roles | Escribir cualquier cosa |

El **coordinador** existe porque no había nada entre el despachador y el
administrador, y en la práctica se resolvía dándole al coordinador los dos
roles: es decir, poder de administrador. Ahora es un rol propio.

### Operaciones por rol de fábrica

| Rol | Operaciones de las 21 | Las que le faltan para tenerlas todas |
|---|---|---|
| Administrador | 19 | Leer y verificar la bitácora |
| Coordinador | 13 | Cargar evidencia, salir a ruta, cuentas (crear y editar), roles (ver y administrar), bitácora |
| Despachador | 10 | Además de las del coordinador: reanudar, editar catálogos, listar cuentas |
| Conductor | 7 | Crear, asignar y reanudar envíos; consultar evidencias; ver el equipo; seguir rutas; cuentas, roles, editar catálogos y bitácora. Lo que sí tiene —listar, marcar avance, cargar evidencia, salir a ruta— se limita a **sus** envíos |
| Auditor | 8 | Toda operación de escritura, más el listado de envíos, el de mensajeros y las dos de rutas |

Las dos operaciones de rutas (`ruta:operar`, `ruta:seguir`) se añadieron el
2026-10-16 y van en un área propia, «Rutas y ubicación»: mueven la ubicación de
una persona y tienen que poder concederse y negarse por separado
([ADR-013](../../decisiones/adr-013-ubicacion-en-vivo-por-sondeo.md)).

## Decisiones

**El catálogo de operaciones está en el código; la composición de los roles, en
la tabla.** Un rol es una *selección* de lo que el sistema ya sabe hacer, nunca
una invención. Razonamiento completo en
[ADR-010](../../decisiones/adr-010-roles-configurables.md).

**El administrador no se edita y siempre lo tiene todo.** Se resuelve en el
código y no se lee de la tabla: es el seguro contra que una edición deje a una
organización sin nadie que pueda entrar a deshacerla.

**El administrador no lee la bitácora.** Única excepción a «puede hacer todo».
El administrador opera; el auditor revisa lo operado, incluido lo que hizo el
administrador.

**Una operación nueva llega a los roles ya guardados, sin pisar lo decidido.**
Un rol escrito en la tabla manda sobre el de fábrica. Cuando el catálogo crece,
el registro no lleva la operación nueva, y el conductor de una empresa ya
aprovisionada no podría salir a ruta hasta que alguien editara su rol. Por eso
cada rol guardado anota `catalogo_conocido`, las operaciones que existían al
guardarlo, y un rol **de fábrica** recibe las que su registro no conocía
(`authz.operaciones_nuevas_para`). Si la empresa vio la operación y la quitó,
sigue quitada; un rol inventado por la empresa no hereda nada. Los registros
anteriores a la anotación se comparan con `CATALOGO_FUNDACIONAL`, las 19
operaciones originales, que no se amplía nunca. Al renombrar un rol sin tocar
sus permisos, se guardan los efectivos y no los del registro: si no, renombrar
quitaba las operaciones nuevas sin que nadie lo pidiera.

**Nadie concede un permiso que no tiene.** Hoy solo el administrador administra
roles y las tiene todas, de modo que no cambia nada. El día que se delegue
`rol:administrar`, es lo que impide que ese rol se promocione a sí mismo. El
intento se registra como `escalada_de_privilegios`.

**Ni un rol ni una cuenta pueden operar y auditar a la vez.** Se comprueba sobre
el rol que se guarda **y sobre la suma de los roles de la cuenta**: sin lo
segundo, un administrador podría añadirse el rol de auditor y ningún rol
rompería la regla por separado.

**Los permisos se resuelven una vez por petición**, de forma perezosa. Si la
tabla no responde se cae a los roles de fábrica: son más restrictivos, de modo
que el sistema falla cerrado.

**La interfaz decide por permiso, no por nombre de rol.** `puede("envio:asignar")`
y no `tieneGrupo("despachador")`. Un rol que la empresa cree mañana no aparece en
ninguna lista escrita en una pantalla, pero sus permisos sí llegan en `/auth/yo`.

**Descartado: permisos por recurso.** Que un rol alcance «solo los envíos de la
tienda X» exigiría llevar el alcance a cada consulta, y el aislamiento hoy es
por organización y por asignación. Se deja fuera hasta que exista un caso real.

**Descartado: jerarquía de roles.** Un rol que «hereda» de otro es cómodo de
declarar y difícil de leer: para saber qué concede hay que recorrer la cadena.
Cada rol declara su lista completa; la pantalla muestra cuántas operaciones tiene
por área.

## Dependencias y relaciones

- **Depende de**: `rastro_core.maestros` (almacenamiento) y `rastro_core.http`
  (resolución por petición).
- **Depende de él**: todos los servicios, en cada operación; y la interfaz, para
  decidir qué ofrecer.
- **Lo audita**: Cotejo, en el control C-05. Los cambios de configuración quedan
  en la bitácora con la lista de operaciones concedidas.
- **Lo reproducen** las diapositivas de sustentación
  ([`documentacion/sustentacion/`](../../sustentacion/README.md#matrices-de-permisos)):
  la versión corta resume los cinco roles y cuántas de las 19 operaciones tiene
  cada uno; la versión completa (PDF en `entregables/sustentacion/`) trae la
  matriz celda por celda. Si cambia `ROLES_INTEGRADOS`, hay que actualizarlas.

## Comportamiento responsive

La pantalla usa el sistema de diseño compartido
([sistema-de-diseno](../sistema-de-diseno/README.md)); no define breakpoints
propios.

| Elemento | Cómo se adapta |
|---|---|
| Tarjetas de rol | Una columna en móvil, dos desde `sm` (rejilla `rejilla--2`) |
| Editor de permisos | Hoja inferior en móvil, ventana centrada desde `sm`; el contenido tiene scroll propio |
| Grupos de permisos | `fieldset` apilados, con la operación técnica bajo su descripción |
| Casillas | Área táctil de 44 px, como el resto de controles |
| Nombres técnicos (`evento:reanudar`) | Monoespaciada con `overflow-wrap: anywhere` |

Verificado a 360 px sin scroll horizontal.
