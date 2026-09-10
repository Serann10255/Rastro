# Módulo `interfaz-web`

Ubicación: `web/` · Puerto local: 5173

## Qué hace

Interfaz de operación y consulta pública. Aplicación de página única en
JavaScript sin dependencias ni paso de compilación: se sirve como sitio estático
desde el almacenamiento de objetos, que es lo que la mantiene disponible entre
sesiones del laboratorio.

| Archivo | Para qué |
|---|---|
| `index.html` | Operación: acceso, listado, registro, detalle y bitácora |
| `rastreo.html` | Consulta pública por identificador, sin cuenta |
| `assets/api.js` | Cliente de la API y manejo de sesión |
| `assets/app.js` | Lógica de la interfaz de operación |
| `assets/estilos.css` | Estilos, mobile-first |
| `configuracion.json` | Dirección de la API, leída en ejecución (REQ-09) |

## Decisiones

**Sin framework ni compilación.** Un sitio estático se publica copiando
archivos, sobrevive al cierre de la sesión del laboratorio y no añade una cadena
de herramientas que mantener durante un semestre.

**La dirección de la API no está en el código.** Se lee de `configuracion.json`;
al migrar de cuenta cambia ese archivo y nada más.

**El token vive en `sessionStorage`, no en una cookie.** Se pierde al cerrar la
pestaña, que es el comportamiento deseado en un dispositivo compartido.

**La interfaz oculta lo que un rol no puede hacer, pero eso es comodidad y no
control.** La autorización la decide el servidor en cada operación. Cualquiera
puede editar esta página; nadie puede editar la matriz de autorización.

**Un 401 cierra la sesión en lugar de reintentar.** Las credenciales del
laboratorio duran cuatro horas: un token caducado a media jornada es normal, y
reintentar contra él solo produce ruido.

**Todo texto de origen externo se escapa antes de insertarse en el documento.**

**Descartado: aplicación móvil nativa.** Está fuera del alcance del proyecto.
Se atiende con una interfaz web adaptable.

---

## Comportamiento responsive

Enfoque **mobile-first**: los estilos base son los de pantalla pequeña y se
amplían hacia arriba con `min-width`. El ancho de referencia es **360 px**,
porque la condición real del usuario principal es un teléfono de gama baja con
conectividad intermitente en vía.

### Breakpoints

| Nombre | Ancho mínimo | Qué cambia |
|---|---|---|
| base | — | Una columna. Navegación en fila deslizable horizontal |
| `sm` | 640 px | Formularios a dos columnas (`.campos--pareja`). Estado del envío a la derecha del dato |
| `md` | 768 px | Más espaciado. Navegación deja de deslizarse y se envuelve. Listado de envíos a dos columnas |
| `lg` | 1024 px | Detalle en dos paneles: histórico a la izquierda, acciones a la derecha. El listado vuelve a una columna, ya ancha |
| `xl` | 1280 px | Solo aumenta el espaciado exterior |

### Comprobaciones verificadas a 360 px

| Regla del proyecto | Cómo se cumple |
|---|---|
| Usable a 360 px | Verificado en navegador |
| Sin scroll horizontal en el documento | `overflow-x: hidden` en `body` y `min-width: 0` en los contenedores de rejilla |
| Tablas anchas scrollean en su contenedor | `.tabla-contenedor` con `overflow-x: auto` y `max-width: 100%` |
| Imágenes con `max-width: 100%` | Regla global |
| Áreas táctiles de 44×44 px | Variable `--tactil`, aplicada a botones, campos y elementos de lista |
| El texto no se desborda ni se corta | `overflow-wrap: anywhere` en identificadores UUID y datos largos |
| Navegación colapsada en móvil | Fila deslizable con `overflow-x: auto` y elementos que no se encogen |

### Un defecto encontrado y corregido

La tabla de bitácora declara `min-width: 40rem` para que sus columnas sean
legibles. En un viewport de 360 px, **estiraba su contenedor y trasladaba el
desbordamiento a la página**: el documento medía 869 px.

La causa es que un elemento de rejilla o de caja flexible no baja por omisión de
su ancho de contenido. Se corrigió con `min-width: 0` en los contenedores y
`max-width: 100%` en el contenedor de tabla. Tras la corrección el documento
mide 360 px y la tabla scrollea dentro de su propio bloque.

### Otras consideraciones

- **Contraste y tema.** Paleta de tokens con variante para `prefers-color-scheme: dark`.
- **Tipografía de formulario a 1 rem.** Evita el zoom automático de iOS al enfocar un campo.
- **`prefers-reduced-motion`.** Las transiciones se anulan.
- **Foco visible.** `outline` de 3 px en todo elemento interactivo.
- **Captura de evidencia.** `capture="environment"` abre la cámara trasera en móvil.
- **Semántica.** `aria-current="page"` en la navegación, `role="status"` en el
  progreso de carga, `<caption>` para lectores de pantalla en la tabla.

## Dependencias y relaciones

- **Depende de**: la puerta de enlace (`gateway`) y, a través de ella, de todos
  los servicios. Ninguna biblioteca de terceros.
- **Sirve a**: despachador, conductor y auditor en `index.html`; destinatario en
  `rastreo.html`.
