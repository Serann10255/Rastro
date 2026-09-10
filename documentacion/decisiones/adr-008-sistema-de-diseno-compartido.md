# ADR-008 · Un solo sistema de diseño para las dos interfaces

Fecha: 2026-09-10 · Estado: aceptada · Complementa a [ADR-005](adr-005-react-con-configuracion-en-ejecucion.md)

## Contexto

Rastro y Cotejo son dos proyectos distintos, de dos asignaturas distintas, con
dos interfaces distintas. Empezaron compartiendo el aspecto por el camino más
frágil posible: **copiar los archivos de estilo**. `tokens.css` y `base.css`
eran idénticos byte a byte en las dos aplicaciones y `componentes.css` ya había
empezado a divergir.

Una copia no es compartir. Al corregir un color en una de las dos, la otra se
queda atrás y nadie lo nota hasta ver las dos pantallas seguidas.

Además, el resultado era genérico: sin marca, sin iconografía propia, con
emojis del sistema operativo como iconos y un punto de color por logotipo. Para
un proyecto que aspira a presentarse como producto, la interfaz decía
«prototipo».

## Decisión

**Un único sistema de diseño en `design/`, fuera de las dos aplicaciones**, que
ambas importan: fichas, estilos base, componentes, iconografía y los dos
logotipos.

### Qué comparten y qué no

| Compartido en `design/` | Propio de cada aplicación |
|---|---|
| Espacio, tipografía, radios, sombras, área táctil | El color de marca (`identidad.css`) |
| Tema claro y oscuro completo | El logotipo |
| Todos los componentes y el armazón | Las pantallas |
| La iconografía | — |

**Un acento distinto por aplicación, no un diseño distinto.** Rastro usa el azul
y el cian del recorrido; Cotejo, el índigo del examen. Que parezcan productos
sin relación sería un problema de producto —el mismo usuario abre los dos el
mismo día—, y que fueran indistinguibles sería peor, porque **uno audita al
otro** y el auditor tiene que saber en cuál está.

### El armazón cambia de forma, no de código

En pantalla estrecha es una barra superior con la navegación deslizable; a
partir de 1024 px es una columna lateral fija. Es el mismo bloque con otra
rejilla (`grid-template-areas`), no dos componentes: dos componentes se
desincronizan, uno con dos rejillas no puede.

En escritorio sobra sitio a los lados y una barra superior obliga a subir la
vista cada vez que se cambia de sección. En un teléfono no cabe ninguna columna,
y por eso allí vuelve a ser una barra.

### Iconografía propia en lugar de emoji

Los emoji del sistema operativo se dibujan distinto en cada plataforma —el mismo
📦 es marrón en Windows y beige en Android—, no heredan el color del texto y en
tema oscuro conservan su propio fondo. Los iconos del sistema son trazados sobre
una retícula de 24 con `currentColor`, con los mismos parámetros que los
logotipos, y por eso funcionan en los dos temas sin variantes.

### Los logotipos dicen lo que hace cada sistema

**Rastro** es un trayecto de tres nodos —registrado, en camino, entregado—
dentro de las esquinas de una caja. No lleva camión: el sistema no transporta
nada, registra lo que ocurre con lo transportado, y esa diferencia es lo que lo
separa de un TMS cualquiera.

**Cotejo** son dos hojas superpuestas —lo declarado y lo observado— con la marca
de verificación que solo aparece cuando ambas coinciden, y tres eslabones de la
cadena de huellas. No lleva lupa: una lupa dice «buscar», y auditar no es
buscar, es comparar contra un criterio declarado de antemano.

## Consecuencias

**El contexto de construcción de las imágenes cambia.** `design/` está fuera de
`web/` y de `cotejo/web/`, de modo que las dos imágenes se construyen desde la
raíz del repositorio. Se añadió un `.dockerignore`: sin él, cada construcción
enviaría al demonio el entorno virtual, los `node_modules` y el historial de
git por un cambio de una línea de CSS.

**Los archivos fuera de la raíz necesitan permiso explícito.** Vite solo sirve
lo que está dentro del proyecto: cada configuración declara `fs.allow` y el
alias `@design`. Y como el compilador de tipos resuelve `react` desde el
directorio del archivo, los dos `tsconfig.json` mapean `react` y
`react/jsx-runtime` a sus tipos; sin eso, cualquier componente de `design/`
falla al comprobar tipos aunque compile.

**Cotejo carga algo de CSS que no usa.** El archivo de componentes es el
conjunto completo. Son unos pocos kilobytes comprimidos, y el precio de la
alternativa —dos archivos que hay que mantener sincronizados— ya se pagó una vez.

**Cambiar un color afecta a las dos aplicaciones.** Es exactamente lo que se
buscaba, y también significa que un cambio descuidado se ve en dos sitios. Las
fichas están documentadas y ningún componente escribe un color literal.
