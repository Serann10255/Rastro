# Servicio `masters` — datos maestros y catálogos

Ubicación: `services/masters/` · Puerto local: 8008

## Qué hace

Los catálogos sobre los que se apoya la operación. Un envío no se registra en el
vacío: sale de una tienda, lo despacha un cliente y lo mueve un transportista, y
esos tres deben existir antes.

| Recurso | Operaciones | Quién |
|---|---|---|
| `GET /catalogos/estados` | listar | **abierta** |
| `GET /catalogos/modulos` | listar | los cuatro grupos |
| `POST /catalogos/modulos/{clave}` | encender o apagar | administrador |
| `/tiendas` | listar, crear, actualizar, eliminar | consultar: los cuatro grupos · editar: administrador |
| `/clientes` | listar, crear, actualizar, eliminar | ídem |
| `/transportistas` | listar, crear, actualizar, eliminar | ídem |

Las escrituras usan `POST` también para actualizar y eliminar
(`POST /tiendas/{id}/eliminar`). Es una decisión heredada del reparto de rutas:
API Gateway y nginx enrutan las mismas rutas en ambos entornos, y limitar los
verbos a `GET` y `POST` mantiene una sola definición de ruta por operación en
lugar de cuatro configuraciones que pueden divergir.

## Decisiones

**Leer y escribir tienen permisos distintos.** El despachador necesita consultar
las tiendas para registrar un envío, pero cambiar la dirección de una tienda
afecta a toda la operación y corresponde al administrador.

**El catálogo de estados se sirve desde el servidor y es abierto.** Duplicarlo en
el cliente lo desincroniza en cuanto se añade un estado, y el síntoma es una
pantalla que muestra un estado en blanco sin decir por qué. Es abierto porque no
contiene datos de ninguna organización: es la definición del proceso, la misma
que un transportista externo necesita para interpretar un archivo de intercambio.

**Cada estado lleva un código numérico** (10, 20, … 90). Un TMS intercambia
archivos con transportistas y clientes; el nombre en texto es frágil ante
tildes, mayúsculas y traducciones, el código no. Los saltos de diez dejan hueco
para estados intermedios sin renumerar lo existente, que es lo que rompería a
todos los integradores a la vez.

**Los módulos de la organización son datos, no código.** Qué módulos ve una
empresa —y cuáles no, con su motivo— vive en la tabla. Escribirlo en la interfaz
obligaba a recompilar el sitio para dar de alta uno y hacía imposible que dos
organizaciones vieran cosas distintas. Véase
[ADR-009](../../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md).

**Apagar un módulo exige decir por qué.** El repositorio lo rechaza si no hay
motivo, de modo que la regla la encuentra cualquier vía de escritura, incluida
una que se escriba mañana. Un módulo ausente sin motivo parece un olvido; con
motivo es una decisión que se puede discutir.

**El administrador solo cambia si está encendido y por qué.** El nombre, la ruta
y los grupos describen el sistema, no la decisión de la empresa, y por eso no se
editan desde la API.

**Eliminar es desactivar, no borrar.** Un envío registrado guarda a qué tienda y
a qué cliente pertenece; borrar el maestro dejaría envíos históricos apuntando a
nada y falsearía la trazabilidad, que es justamente lo que el sistema promete.

**La organización sale del token, nunca del cuerpo.** Igual que en envíos:
aceptarla del cliente permitiría escribir en el catálogo de otra empresa.

## Dependencias y relaciones

- **Depende de**: `rastro_core.maestros` (tabla única de maestros),
  `rastro_core.state_machine` (catálogo público de estados) y
  `rastro_core.authz`.
- **Depende de él**: la interfaz web (pantallas de Tiendas, Clientes y
  Transportistas, y el registro de envíos, que usa las tiendas como origen) y
  cualquier integración que necesite el catálogo de estados.
- **Comparte tabla** con el servicio de identidad: usuarios, empresa y maestros
  viven en la misma tabla con prefijos de clave distintos. La razón está en
  [ADR-002](../../decisiones/adr-002-capa-comun-de-acceso-a-datos.md) y en
  [modelo-de-datos](../../base-de-datos/modelo-de-datos.md).

## Comportamiento responsive

No aplica: el servicio no tiene interfaz. La pantalla que lo consume es
`web/src/paginas/Maestros.tsx`, documentada en
[interfaz-web](../interfaz-web/README.md).
