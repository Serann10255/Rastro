# Módulo `design` — sistema de diseño compartido

Ubicación: `design/` · Lo usan: [`interfaz-web`](../interfaz-web/README.md) y [`cotejo-web`](../cotejo-web/README.md)

## Qué hace

Un único sitio donde viven el color, el espacio, la tipografía, los componentes,
la iconografía y los logotipos de las dos interfaces del repositorio.

```
design/
├── tokens.css        Fichas: espacio, tipografía, radios, color, tema claro y oscuro
├── base.css          Reinicio, utilidades y estructura de la aplicación
├── componentes.css   Armazón, tarjetas, tablas, formularios, avisos, módulos…
└── marca/
    ├── rastro.tsx    Logotipo de Rastro
    ├── cotejo.tsx    Logotipo de Cotejo
    └── iconos.tsx    Juego de iconos, trazados sobre una retícula de 24
```

Cada aplicación añade **solo su identidad** en `src/estilos/identidad.css`: el
degradado de marca y, en el caso de Cotejo, el acento. Nada más.

## Por qué existe

Antes las dos aplicaciones compartían el aspecto copiando los archivos:
`tokens.css` y `base.css` eran idénticos byte a byte y `componentes.css` ya
había empezado a divergir. **Una copia no es compartir**: al corregir un color en
una, la otra se queda atrás y nadie lo nota hasta ver las dos pantallas seguidas.

El razonamiento completo —qué se comparte, qué no, y por qué cada aplicación
conserva su acento— está en
[ADR-008](../../decisiones/adr-008-sistema-de-diseno-compartido.md).

## Decisiones

**Un acento distinto por aplicación, no un diseño distinto.** Rastro usa el azul
y el cian del recorrido; Cotejo, el índigo del examen. Que parezcan productos sin
relación sería un problema de producto; que fueran indistinguibles sería peor,
porque uno audita al otro.

**Ningún componente escribe un color literal.** Si lo hiciera, el tema oscuro
dejaría de funcionar en ese punto y nadie lo notaría hasta verlo.

**Iconos propios en lugar de emoji.** Un emoji se dibuja distinto en cada sistema
operativo, no hereda el color del texto y en tema oscuro conserva su propio
fondo. Los iconos usan `currentColor` y los mismos parámetros de trazo que los
logotipos.

**Un icono desconocido dibuja el genérico, no un hueco.** El nombre del icono
llega desde la base de datos; una pantalla con un agujero parece rota cuando el
problema real es solo que falta un dibujo.

**Los logotipos usan el degradado de marca por variable**, no colores escritos.
El mismo componente sirve en tema claro y oscuro. Los favicones sí llevan el
color literal: un favicon se sirve suelto y no tiene acceso a las fichas.

**Descartada una biblioteca de componentes de terceros.** El proyecto se audita a
sí mismo; conviene que lo que se sirve sea código propio y revisable.

**Descartado un paquete npm compartido.** Habría que publicarlo o enlazarlo, y
las dos aplicaciones se construyen desde el mismo repositorio: un alias de rutas
resuelve lo mismo sin un artefacto más que versionar.

## Dependencias y relaciones

- **No depende de nada**: CSS y dos componentes de React sin más importaciones
  que las de la propia biblioteca.
- **Depende de él**: las dos interfaces, en tiempo de compilación.
- Vite necesita permiso para servir archivos fuera de la raíz del proyecto
  (`server.fs.allow`) y los `tsconfig.json` mapean `react` a sus tipos: sin eso,
  un componente de `design/` compila pero no comprueba tipos.
- Las imágenes de las dos interfaces se construyen desde la raíz del
  repositorio, con `.dockerignore` para no enviar el repositorio entero.

## Comportamiento responsive

Enfoque **mobile-first**: los estilos base son los de pantalla pequeña y se
amplían hacia arriba con `min-width`. El ancho de referencia es **360 px**.

### Breakpoints

| Nombre | Ancho mínimo | Qué cambia |
|---|---|---|
| base | — | Armazón como barra superior. Navegación en fila deslizable. Una columna |
| — | 480 px | Aparece el lema de la marca. Selector de estado a dos columnas |
| `sm` | 640 px | Aparece el nombre del usuario en la barra. Rejillas a dos columnas. Módulos desde 19 rem |
| `md` | 768 px | Más espaciado. Rejillas a tres columnas. Filtros en línea |
| `lg` | 1024 px | **El armazón pasa a columna lateral.** Rejillas a cuatro columnas. Detalle en dos paneles |
| `xl` | 1280 px | Solo aumenta el espaciado exterior |

### El armazón

Es el único componente que cambia de forma con el ancho, y lo hace con
`grid-template-areas` sobre el mismo marcado:

| | Móvil | Escritorio (≥1024 px) |
|---|---|---|
| Disposición | Barra superior pegada | Columna lateral de 15 rem, alto completo |
| Navegación | Fila deslizable con `scroll-snap` | Lista vertical con el contador alineado a la derecha |
| Identidad | Insignia de empresa y nombre a la derecha | Tarjeta al pie de la columna |
| Lema de la marca | Oculto bajo 480 px | Visible |

No son dos componentes: **dos componentes se desincronizan, uno con dos rejillas
no puede**.

### Comprobaciones verificadas

| Regla del proyecto | Cómo se cumple |
|---|---|
| Usable a 360 px | Verificado en navegador en las dos aplicaciones |
| Sin scroll horizontal en el documento | `overflow-x: hidden` en `body` y `min-width: 0` en los contenedores de rejilla |
| Tablas anchas scrollean en su contenedor | `.tabla-contenedor` con `overflow-x: auto` y `max-width: 100%` |
| Imágenes con `max-width: 100%` | Regla global |
| Áreas táctiles de 44×44 px | Ficha `--tactil` en botones, campos, casillas, enlaces de navegación, enlace de salto y enlaces del pie |
| El texto no se desborda | `overflow-wrap: anywhere` en identificadores, direcciones y hashes |
| Navegación colapsada en móvil | Fila deslizable; la columna lateral solo existe a partir de 1024 px |

### Otras consideraciones

- **Tema.** Claro, oscuro y automático, con el mismo selector en las dos
  aplicaciones. Se guarda la elección.
- **`prefers-reduced-motion`.** Transiciones y animaciones se anulan.
- **Foco visible** de 2 px en todo elemento interactivo.
- **El color nunca es la única señal**: cada estado lleva su texto y su código.
