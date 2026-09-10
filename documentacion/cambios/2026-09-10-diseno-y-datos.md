# Cambios · 2026-09-10 (cuarta entrega del día)

Dos cosas, relacionadas entre sí: las interfaces pasan a compartir un sistema de
diseño de verdad —con marca propia— y todo lo que describe a una organización
sale del código y entra en la base de datos.

- Diseño e identidad: [ADR-008](../decisiones/adr-008-sistema-de-diseno-compartido.md)
- Datos fuera del código: [ADR-009](../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md)

---

## Un solo sistema de diseño

Antes las dos interfaces compartían el aspecto **copiando los archivos**:
`tokens.css` y `base.css` eran idénticos byte a byte y `componentes.css` ya había
empezado a divergir. Una copia no es compartir: al corregir un color en una, la
otra se queda atrás y nadie lo nota hasta ver las dos pantallas seguidas.

Ahora hay un módulo nuevo, [`design/`](../modulos/sistema-de-diseno/README.md),
que las dos importan. Cada aplicación conserva **solo** su `identidad.css` con el
color de marca.

| Antes | Ahora |
|---|---|
| Tres archivos CSS duplicados en cada aplicación | Uno solo en `design/`, importado por las dos |
| Un punto de color por logotipo | Dos logotipos propios, en SVG y con el degradado de marca |
| Emoji del sistema operativo como iconos | 21 iconos propios sobre retícula de 24, con `currentColor` |
| Barra superior en todas las anchuras | Barra en móvil, **columna lateral desde 1024 px** |
| Acento azul en las dos | Azul y cian en Rastro, índigo en Cotejo |

**El armazón es el mismo bloque con dos rejillas**, no dos componentes: dos
componentes se desincronizan, uno con dos rejillas no puede.

### Los logotipos

**Rastro** es un trayecto de tres nodos —registrado, en camino, entregado— dentro
de las esquinas de una caja. Sin camión: el sistema no transporta nada, registra
lo que ocurre con lo transportado.

**Cotejo** son dos hojas superpuestas —lo declarado y lo observado— con la marca
de verificación que solo aparece cuando ambas coinciden, más tres eslabones de la
cadena de huellas. Sin lupa: auditar no es buscar, es comparar contra un criterio
declarado de antemano.

Los dos usan el mismo lienzo, el mismo grosor de trazo y el mismo degradado por
variable, de modo que funcionan en tema claro y oscuro sin variantes. Los
favicones repiten el trazado con el color escrito, porque un favicon se sirve
suelto y no tiene acceso a las fichas.

## Nada de operación escrito en el código

| Dónde estaba | A dónde fue |
|---|---|
| Tres mensajeros con su identificador, en la pantalla de detalle | `GET /equipo/mensajeros`, desde el directorio de la empresa |
| Catorce módulos con icono y motivo, en la pantalla de operaciones | Registros `MODULO#<clave>` en la tabla de maestros |
| Las secciones de la navegación, en el armazón | El campo `destacado` de cada módulo |
| Qué estados cierran un envío, en tres pantallas | El campo `final` del catálogo del servidor |
| Cinco cuentas con su contraseña, en el programa de auditoría | Identidades desde el directorio; claves por configuración |

### Módulos por organización

Cada empresa tiene los suyos, con nombre, icono, ruta, grupos, orden, si va en la
navegación principal, si está disponible y —cuando no— **por qué**. Un
administrador los enciende y apaga desde `POST /catalogos/modulos/{clave}`.

- **Apagar exige motivo.** La regla vive en el repositorio, no en la pantalla:
  la encuentra cualquier vía de escritura, incluida una que se escriba mañana.
- **Encender exige ruta.** Un módulo encendido que no lleva a ninguna parte es
  una tarjeta que no hace nada al pulsarla, y eso se lee como un fallo.
- **Apagarlo en una empresa no lo apaga en la otra.** Hay una prueba que lo fija.
- **El aprovisionamiento respeta lo decidido:** al volver a sembrar, `disponible`
  y `motivo` se conservan. Volver a encender en cada despliegue un módulo que un
  administrador apagó sería deshacer una decisión de la empresa a sus espaldas.

### Equipo

`GET /equipo/mensajeros` devuelve los conductores **activos** de la organización
del token, con tres campos: sujeto, nombre y teléfono. Es una vista reducida a
propósito y por eso la puede pedir un despachador, que no administra cuentas pero
sí asigna. Un mensajero desactivado deja de aparecer: asignarle un envío a una
cuenta desactivada produce un envío que nadie puede mover.

### Cotejo

Las identidades de prueba salen ahora del directorio del sistema auditado: el
programa lee la tabla de maestros y elige, por organización y por rol, contra
quién ejecutar. Las claves no pueden salir de ahí —están derivadas— y llegan por
`COTEJO_CLAVES` o, en local, del **mismo archivo de semilla que creó esas
cuentas**, montado en solo lectura.

Si falta la clave de un rol necesario, esa prueba se reporta *no ejecutada* con
su motivo. Auditar otro despliegue ya no exige editar el programa de auditoría.

## Defectos corregidos por el camino

| Defecto | Causa | Corrección |
|---|---|---|
| El módulo de guías llevaba a una página inexistente | La semilla declaraba `/guias` y el enrutador define `/envios/guias`. Al pasar el catálogo a la base de datos aparecieron dos fuentes que podían discrepar en silencio; antes, una ruta mal escrita no compilaba | Ruta corregida y **cinco pruebas nuevas** que comparan la semilla con el enrutador, los iconos y los contadores que la pantalla sabe resolver |
| Guías aparecía en la navegación principal y siempre caía en «no hay envíos seleccionados» | Es un paso de un flujo, no una sección: se llega con envíos marcados desde el listado | `destacado: false`; sigue en el menú de operaciones, donde su estado vacío explica qué hacer |
| Dos módulos dibujaban el icono genérico | El repositorio truncaba el nombre del icono a 8 caracteres: `recoleccion` quedaba en `recolecc` | Límite a 40, con el motivo escrito |
| La navegación quedaba flotando en mitad de la columna lateral | El armazón heredaba `align-items: center` de la barra móvil | `align-items: start` en el bloque de escritorio |
| El enlace de salto y el del pie medían menos de 44 px | Eran texto, no controles | Área táctil completa en los dos |

## Consecuencias en la construcción

**Las dos imágenes de interfaz se construyen desde la raíz del repositorio**,
porque `design/` está fuera de cada aplicación. Se añadió `.dockerignore`: sin
él, cada construcción enviaría al demonio el entorno virtual, los `node_modules`
y el historial de git por un cambio de una línea de CSS.

**Vite necesita permiso** para servir archivos fuera de la raíz (`fs.allow`) y los
`tsconfig.json` mapean `react` a sus tipos: sin eso, un componente de `design/`
compila pero no comprueba tipos.

## Pruebas

**203 en verde**, más 4 omitidas (los módulos apagados, que por definición no llevan a ninguna parte). Las 43 nuevas cubren los módulos por organización —que no
cruzan la frontera, que apagar exige motivo, que encender exige ruta, que solo el
administrador los toca— y la vista del equipo —que solo trae conductores, que no
expone la ficha de la cuenta, que un conductor no puede consultarla y que un
mensajero desactivado desaparece—, más la coherencia entre la semilla y la interfaz: que cada módulo apunte a una ruta que el enrutador define, pida un icono que existe y un contador que la pantalla sabe resolver.

Verificado además contra la pila levantada: las dos interfaces en 1280 px y en
360 px sin scroll horizontal, y Cotejo sigue dando 5 de 8 controles con
resultado, cinco conformes y ninguno desviado.

## Documentación actualizada

Módulo nuevo [sistema-de-diseno](../modulos/sistema-de-diseno/README.md) ·
[interfaz-web](../modulos/interfaz-web/README.md) ·
[cotejo-web](../modulos/cotejo-web/README.md) ·
[cotejo](../modulos/cotejo/README.md) ·
[servicio-maestros](../modulos/servicio-maestros/README.md) ·
[servicio-auth](../modulos/servicio-auth/README.md) ·
[modelo-de-datos](../base-de-datos/modelo-de-datos.md) ·
[contratos](../api/contratos.md) ·
[plan y trazabilidad](../pruebas/plan-y-trazabilidad.md) · ADR-008 y ADR-009.
