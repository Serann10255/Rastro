# Módulo `interfaz-web` — interfaz de operación de Rastro

Ubicación: `web/` · Puerto local: 5173 · Stack: React 18 + TypeScript + Vite

## Qué hace

Interfaz de operación y consulta pública. Aplicación de una sola página que se
compila a archivos estáticos y se publica en el almacenamiento de objetos, lo
que la mantiene disponible entre sesiones del laboratorio.

| Ruta | Quién entra | Qué hace |
|---|---|---|
| `/acceso` | cualquiera | Entrar. Muestra las cuentas sintéticas |
| `/panel` | los cuatro roles | Panel distinto según el rol |
| `/envios` | admin, despachador, conductor | Listado con búsqueda y filtros |
| `/envios/nuevo` | admin, despachador | Registro de envío |
| `/envios/:id` | los cuatro roles | Detalle, punto de control, evidencia |
| `/bitacora` | auditor | Bitácora y verificación de integridad |
| `/rastreo` | **sin cuenta** | Consulta pública del avance |

## Estructura

```
src/
├── api/
│   ├── cliente.ts      Cliente HTTP, configuración en ejecución, errores tipados
│   ├── sesion.tsx      Contexto de sesión y aviso de caducidad
│   └── consultas.ts    Hooks de React Query: lecturas, escrituras, invalidación
├── componentes/
│   ├── ui.tsx          Botones, campos, tarjetas, avisos, modal, esqueletos
│   ├── Estructura.tsx  Barra, navegación por rol, selector de tema, pie
│   └── notificaciones.tsx  Avisos emergentes y traducción de errores
├── paginas/            Una por ruta
├── estilos/            tokens.css · base.css · componentes.css
└── tipos/              Contratos del backend
```

## Un panel distinto por rol

Cada rol llega buscando algo diferente. Una pantalla común obligaría a los tres a
buscar lo suyo entre lo de los demás.

| Rol | Qué ve primero |
|---|---|
| Despachador | Envíos en curso, sin asignar, con incidencia y entregados; distribución del proceso; pendientes de asignar |
| Conductor | Su siguiente parada, con acción directa; el resto de su ruta |
| Auditor | Registros en bitácora, intentos rechazados y estado de la cadena, con verificación en un botón |

## Decisiones

**React con configuración en tiempo de ejecución.** Justificada en
[ADR-005](../../decisiones/adr-005-react-con-configuracion-en-ejecucion.md). La
condición crítica es que la dirección de la API **no se hornea en el bundle**: se
lee de `configuracion.json`, porque REQ-09 exige que trasladar el sistema a otra
cuenta no obligue a recompilar.

**Las acciones salen del servidor, no de una copia de la máquina de estados.** El
detalle pregunta a `/transiciones` qué estados son alcanzables. Duplicar esa
lógica en el cliente crearía dos fuentes de verdad, y la del cliente se quedaría
atrás sin que nadie lo notara hasta ver un rechazo inexplicable.

**El selector de estado son botones, no un desplegable.** Un desplegable exige
tres toques: abrir, buscar, elegir. Registrar el avance debe costar menos que
enviar un mensaje de chat; si cuesta más, el mensajero vuelve al chat y el
sistema deja de tener datos. Es la decisión de interfaz con más efecto sobre la
viabilidad operativa del proyecto.

**La carga de evidencia muestra sus tres pasos.** Solicitar el enlace, cargar el
archivo y confirmar son operaciones distintas contra servicios distintos.
Mostrarlas por separado hace que un fallo señale dónde ocurrió, en lugar de
producir un «no se pudo cargar» que no dice nada.

**Sin biblioteca de componentes de terceros.** El proyecto se audita a sí mismo;
conviene que lo que se sirve sea código propio y revisable.

**Sin biblioteca de gráficos.** Las barras del panel y la cadena de la bitácora
son CSS. Añadir una dependencia de decenas de kilobytes para dibujar siete
cantidades no se justifica.

**El token vive en `sessionStorage`.** Se pierde al cerrar la pestaña, que es el
comportamiento deseado en un dispositivo compartido entre mensajeros.

**Un 401 cierra la sesión en lugar de reintentar.** Las credenciales del
laboratorio duran cuatro horas: caducar a media jornada es normal, y reintentar
contra un token muerto solo produce ruido. La interfaz avisa cinco minutos antes.

**Sin conexión no es un error del sistema.** El cliente distingue el fallo de red
y lo dice con esas palabras, porque la condición real del mensajero es
conectividad intermitente en vía.

**Descartado: aplicación móvil nativa.** Está fuera del alcance del proyecto. Se
atiende con una interfaz web adaptable.

## Comportamiento responsive

Enfoque **mobile-first**: los estilos base son los de pantalla pequeña y se
amplían hacia arriba con `min-width`. El ancho de referencia es **360 px**,
porque la condición real del usuario principal es un teléfono de gama baja con
conectividad intermitente en vía.

### Breakpoints

| Nombre | Ancho mínimo | Qué cambia |
|---|---|---|
| base | — | Una columna. Navegación en fila deslizable. Selector de estado apilado |
| — | 480 px | Selector de estado a dos columnas |
| `sm` | 640 px | Rejillas a dos columnas. Modal centrado en lugar de hoja inferior |
| `md` | 768 px | Más espaciado. Rejillas a tres columnas. Filtros en línea |
| `lg` | 1024 px | Rejillas a cuatro columnas. Detalle en dos paneles: histórico a la izquierda, acciones a la derecha |
| `xl` | 1280 px | Solo aumenta el espaciado exterior |

### Comprobaciones verificadas

| Regla del proyecto | Cómo se cumple |
|---|---|
| Usable a 360 px | Verificado en navegador en las cinco pantallas |
| Sin scroll horizontal en el documento | `overflow-x: hidden` en `body` y `min-width: 0` en los contenedores de rejilla |
| Tablas anchas scrollean en su contenedor | `.tabla-contenedor` con `overflow-x: auto` y `max-width: 100%` |
| Imágenes con `max-width: 100%` | Regla global |
| Áreas táctiles de 44×44 px | Ficha `--tactil` aplicada a botones, campos, casillas y elementos de lista |
| El texto no se desborda ni se corta | `overflow-wrap: anywhere` en identificadores, direcciones y hashes |
| Navegación colapsada en móvil | Fila deslizable con `scroll-snap` y elementos que no se encogen |

### Otras consideraciones

- **Tema.** Claro, oscuro y automático. El selector rota entre los tres y
  recuerda la elección. El mensajero a veces necesita fijar el modo claro con sol
  directo.
- **Tipografía de formulario a 1 rem.** Evita el zoom automático de iOS al
  enfocar un campo.
- **`prefers-reduced-motion`.** Transiciones y animaciones se anulan.
- **Enlace de salto al contenido.** Primera parada del tabulador, visible solo al
  recibir el foco.
- **Foco visible** de 2 px en todo elemento interactivo.
- **Semántica.** `aria-current` en navegación, `aria-pressed` en el selector de
  estado, `aria-live="polite"` en las notificaciones, `role="alert"` en errores,
  `<caption>` para lectores de pantalla en la tabla de bitácora.
- **Captura de evidencia.** `capture="environment"` abre la cámara trasera.
- **Límite de error.** Un fallo de renderizado muestra un mensaje con opción de
  recargar. En un dispositivo en vía, una pantalla en blanco es indistinguible de
  una caída del sistema.

## Dependencias y relaciones

| Dependencia | Para qué |
|---|---|
| `react`, `react-dom` | Interfaz |
| `react-router-dom` | Enrutamiento y rutas protegidas |
| `@tanstack/react-query` | Estado del servidor, reintento e invalidación |
| `vite`, `typescript` | Compilación y tipos |

- **Consume**: la puerta de enlace y, a través de ella, los seis servicios.
- **Comparte estilos con** [`cotejo-web`](../cotejo/README.md), que copia las
  mismas fichas de diseño y cambia el color de acento.

## Desarrollo

```bash
cd web
npm install
npm run dev        # http://localhost:5173, reenvía la API a localhost:8080
npm run typecheck
npm run build
```

En desarrollo, Vite reenvía `/auth`, `/envios`, `/publico` y `/bitacora` a la
puerta de enlace, de modo que no hay diferencia de origen entre desarrollo y el
sitio publicado.
