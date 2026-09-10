# Módulo `interfaz-web` — interfaz de operación de Rastro

Ubicación: `web/` · Puerto local: 5173 · Stack: React 18 + TypeScript + Vite

## Qué hace

Interfaz de operación y consulta pública. Aplicación de una sola página que se
compila a archivos estáticos y se publica en el almacenamiento de objetos, lo
que la mantiene disponible entre sesiones del laboratorio.

| Ruta | Quién entra | Qué hace |
|---|---|---|
| `/acceso` | cualquiera | Entrar con correo y contraseña reales |
| `/panel` | los cuatro roles | Tablero de la empresa, con indicadores del servidor |
| `/envios` | admin, despachador, conductor | Órdenes: búsqueda, filtros, selección múltiple, guías y exportación |
| `/envios/nuevo` | admin, despachador | Registro individual o **masivo desde CSV** |
| `/envios/:id` | los cuatro roles | Detalle, punto de control, evidencia |
| `/envios/guias` | admin, despachador, conductor | Guías imprimibles con código de barras. Se llega con envíos seleccionados desde el listado |
| `/operaciones` | los cuatro roles | Índice de módulos **de la organización**, incluidos los no disponibles y por qué |
| `/maestros` | los cuatro roles (editar: admin) | Tiendas, clientes y transportistas |
| `/administracion` | admin (consulta: auditor) | Usuarios, roles y datos de la empresa |
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
│   ├── codigo-barras.tsx   Codificador Code 128B a SVG
│   └── notificaciones.tsx  Avisos emergentes y traducción de errores
├── paginas/            Una por ruta
├── estilos/            identidad.css (solo el color de marca)
└── tipos/              Contratos del backend
```

## El tablero

El panel muestra los indicadores de la empresa del usuario: totales, tasa de
entrega, el desglose de los nueve estados con su código, la serie de los últimos
treinta días y las tres listas sobre las que hay que actuar hoy —sin asignar, con
incidencia y estancados—.

**Los números los calcula el servidor.** La pantalla dibuja; no suma. Calcularlos
aquí obligaría a descargar todos los envíos y produciría dos versiones del mismo
indicador en cuanto una de las dos cambiara.

**El conductor ve el mismo tablero acotado a sus envíos**, y la pantalla lo dice
con esas palabras: el campo `alcance` de la respuesta se traduce en un rótulo,
para que no crea que la empresa entera mueve seis envíos.

## Decisiones

**El sistema de diseño es compartido con Cotejo** y vive en `design/`, fuera de
esta aplicación. Aquí solo queda `identidad.css` con el color de marca. La razón
está en [ADR-008](../../decisiones/adr-008-sistema-de-diseno-compartido.md) y el
detalle en [sistema-de-diseno](../sistema-de-diseno/README.md).

**La navegación y el menú de operaciones salen de la base de datos.** Cada
organización tiene sus módulos en la tabla de maestros; la interfaz los filtra
por el grupo del usuario y los pinta. Escribirlos aquí obligaba a recompilar el
sitio para dar de alta uno y hacía imposible que dos empresas vieran cosas
distintas. Véase
[ADR-009](../../decisiones/adr-009-datos-de-operacion-fuera-del-codigo.md).

**Los mensajeros a los que se puede asignar salen del directorio.** Antes había
tres escritos en la pantalla de detalle, con su identificador, incluido el de
otra empresa.

**Qué estados cierran un envío lo dice el catálogo del servidor.** Estaba escrito
en tres pantallas: al añadir `DEVUELTO` y `CANCELADO` hubo que tocar las tres, y
bastaba olvidar una para que un envío cerrado siguiera contando como abierto.

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

**La pantalla de acceso no muestra cuentas de ejemplo.** Antes listaba las
credenciales sintéticas con un botón para rellenarlas. Era cómodo y era exactamente
lo que un sistema real no debe hacer: publicar usuarios válidos en la única
pantalla abierta a cualquiera. Las credenciales de la instalación local están en
la documentación de despliegue, que es donde corresponde.

**La sesión se renueva sola, una sola vez y con un solo intento en vuelo.** Ante
un 401 con sesión activa, el cliente pide un token nuevo con el refresco y
reintenta la petición. El reintento está marcado para que no pueda encadenarse, y
un candado (`renovacionEnCurso`) hace que diez peticiones simultáneas que fallan a
la vez produzcan **una** renovación y no diez: diez renovaciones concurrentes
rotarían el refresco diez veces y todas menos una quedarían inválidas, que es
justo el fallo que la rotación pretende detectar.

**El código de barras se genera en el navegador, sin dependencia.** Code 128B son
107 patrones y una suma de control; está en `codigo-barras.tsx`, en SVG, y se
imprime nítido a cualquier tamaño. Una biblioteca de terceros para eso serían
decenas de kilobytes servidos en cada carga y una dependencia más que auditar en
un proyecto que se audita a sí mismo.

**Las guías se imprimen desde el navegador.** `@media print` oculta la navegación
y fija el salto de página entre etiquetas. Generar el PDF en el servidor
implicaría una dependencia de composición tipográfica dentro de una función de
computo bajo demanda, y el navegador ya sabe imprimir.

**El listado permite seleccionar y actuar sobre la selección.** Es la operación
diaria: marcar veinte órdenes e imprimir sus guías de una vez. Sin selección
múltiple, el operador abre veinte pestañas, y en la práctica deja de usar el
sistema.

**El CSV se interpreta en el navegador, con un lector escrito a mano.** Son unas
cuarenta líneas que entienden comillas y comas dentro de campo. El archivo del
operador no sale del navegador hasta estar validado, ve los errores por fila
antes de enviar nada, y el sistema no gana una dependencia de análisis de
archivos por algo que se resuelve en una función.

**Los módulos que no existen aparecen y dicen por qué.** `/operaciones` lista
también los que no están disponibles —rutas, facturación, aduanas— con la razón.
Ocultarlos daría a entender que se olvidaron; nombrarlos con su motivo es la
diferencia entre un alcance decidido y una carencia.

**Sin biblioteca de gráficos.** Las barras del tablero, la serie diaria y la
cadena de la bitácora son CSS. Añadir una dependencia de decenas de kilobytes
para dibujar nueve cantidades y treinta días no se justifica.

**El token vive en `sessionStorage`.** Se pierde al cerrar la pestaña, que es el
comportamiento deseado en un dispositivo compartido entre mensajeros.

**Un 401 que la renovación no resuelve cierra la sesión.** Si el refresco también
fue rechazado, no hay nada que reintentar: insistir contra un token muerto solo
produce ruido. La interfaz avisa antes de que caduque.

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

Los define el sistema de diseño compartido; la tabla completa está en
[sistema-de-diseno](../sistema-de-diseno/README.md). Lo propio de esta interfaz:

| Nombre | Ancho mínimo | Qué cambia aquí |
|---|---|---|
| base | — | Selector de estado apilado. Armazón como barra superior |
| — | 480 px | Selector de estado a dos columnas |
| `sm` | 640 px | Rejillas a dos columnas. Modal centrado en lugar de hoja inferior |
| `md` | 768 px | Rejillas a tres columnas. Filtros en línea. Guías a dos por hoja |
| `lg` | 1024 px | **Navegación lateral.** Rejillas a cuatro columnas. Detalle en dos paneles |
| `xl` | 1280 px | Solo aumenta el espaciado exterior |

### Comprobaciones verificadas

| Regla del proyecto | Cómo se cumple |
|---|---|
| Usable a 360 px | Verificado en navegador en las once pantallas |
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

- **Consume**: la puerta de enlace y, a través de ella, los ocho servicios.
- **Comparte estilos con** [`cotejo-web`](../cotejo-web/README.md), que copia las
  mismas fichas de diseño y cambia el color de acento.

## Desarrollo

```bash
cd web
npm install
npm run dev        # http://localhost:5173, reenvía la API a localhost:8080
npm run typecheck
npm run build
```

En desarrollo, Vite reenvía `/auth`, `/usuarios`, `/empresa`, `/envios`,
`/publico`, `/bitacora`, `/tablero`, `/catalogos`, `/tiendas`, `/clientes` y
`/transportistas` a la puerta de enlace, de modo que no hay diferencia de origen
entre desarrollo y el sitio publicado. **La lista debe coincidir con la que
reparte la puerta de enlace**: si falta un prefijo, esa ruta devuelve el
`index.html` de Vite en lugar de la API, y el síntoma es un error de JSON
inválido que no señala su causa.
