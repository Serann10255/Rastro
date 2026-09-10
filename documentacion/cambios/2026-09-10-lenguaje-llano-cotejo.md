# 2026-09-10 · Cotejo se explica sin vocabulario técnico

Cotejo estaba escrito entero en el registro de la auditoría de sistemas. Correcto
y necesario —es lo que se evalúa y lo que un tercero espera leer— pero era lo
único que había: para saber si algo se había roto había que reconocer la palabra
`NO_EJECUTADA`, y un hallazgo empezaba por «condición» antes de decir qué pasa.

**Ahora cada cosa se dice dos veces: la frase llana delante y el término del
oficio detrás.** Ninguna sustituye a la otra. Decisión completa en
[ADR-011](../decisiones/adr-011-doble-registro-en-la-interfaz.md).

## Catálogo (`cotejo/catalogo/controles.yaml`, versión 0.1 → 0.2)

- Cada control declara `pregunta`, `en_simple` y `si_falla`. El ejecutor
  **rechaza** un catálogo al que le falte alguno, igual que rechaza uno sin
  criterio: escribir la explicación después de ver el resultado permitiría
  acomodarla al resultado.
- `que_es_esto`: qué hace el programa, en una frase.
- `glosario`: 21 términos del oficio, definidos una sola vez y en un solo sitio.
- Los dos hallazgos permanentes llevan su `en_simple`.

Vive en el catálogo, y no en cada interfaz, para que la consola, el informe y la
web digan exactamente lo mismo del mismo control.

## Informe en texto

- Sección nueva **«1. En palabras simples»**: qué es esto, qué salió —una frase
  con las tres cifras juntas— y cómo se leen las tres respuestas. El registro
  técnico sigue entero, renumerado del 2 al 5.
- Cada control abre con `[BIEN]`, `[MAL]` o `[SIN REVISAR]`, y añade *Pregunta*,
  *Qué hicimos* y *Por qué importa* antes de los campos formales.
- Cada hallazgo abre con *En simple*.
- Los campos se alinean a la columna 21; las rutas y las huellas ya no se parten
  en dos líneas, porque partidas no se pueden copiar.

## Consola

- Antes de ejecutar, lista las preguntas que va a responder.
- Resultado por control con la palabra llana y la pregunta, no con el
  identificador y un resumen truncado a 88 caracteres.
- Los tres códigos de salida se explican con palabras al terminar.
- `verificar` y `comparar` dicen primero qué significa el resultado.
- Comando nuevo: **`python -m cotejo glosario`**.
- La salida se reconfigura a UTF-8 con `errors="replace"`: las preguntas llevan
  signo de apertura y una consola de Windows con una página de códigos antigua
  lo pintaba como un rombo. Con `replace`, además, el programa nunca se detiene
  por no poder imprimir un carácter.

## Interfaz web

- Pestañas: **Revisión · Qué se revisa · Repetir · Diccionario** (esta última es
  nueva).
- Al terminar una revisión, lo primero es una frase: *«Revisamos 8 cosas que
  Rastro dice cumplir. 5 salieron bien, 0 salieron mal y 3 quedaron sin
  revisar»*, con una barra de tres colores. Las métricas siguen debajo.
- Panel de tres pasos que explica el método; se puede ocultar y se recuerda.
- Cada control se titula con su pregunta. La insignia dice **BIEN**, **MAL** o
  **SIN REVISAR** con el término técnico al lado.
- El papel de trabajo se lee como una narración —qué se hizo, qué contestó
  Rastro, por qué importa, paso a paso— y cada paso traduce el código de
  respuesta (*«Rastro dijo que ese usuario no tiene permiso (código 403)»*). La
  evidencia literal queda detrás de un desplegable: cambia de sitio, no de
  contenido.
- El registro técnico de cada tarjeta va en bloques plegados, cerrados por
  omisión.

## Tres defectos encontrados por el camino

**El archivo de evidencia no recibía los campos nuevos.** `papeles.py` escribe la
evidencia con un diccionario explícito, así que añadir un campo al modelo no
basta: la web mostraba el procedimiento técnico como respaldo porque el papel
guardado venía sin `pregunta`. Corregido, y con una prueba que lee el archivo
del disco y no solo el objeto en memoria.

**`local:desconocido` en cada papel ejecutado desde la web.** La identidad salía
de `USERNAME`, que dentro del contenedor no existe. Un papel del que no consta
quién lo obtuvo incumple el principio que el propio módulo declara. Ahora la API
pasa al contexto el correo del auditor autenticado, que para llegar ahí tuvo que
identificarse.

**Dos moradas peleando por el acento.** `cotejo.css` redefinía `--acento` con un
morado distinto del de `identidad.css` y, al importarse después, ganaba. El
color de marca que dice [ADR-008](../decisiones/adr-008-sistema-de-diseno-compartido.md)
nunca llegaba a aplicarse. `cotejo.css` ya no define color de marca.

## Pruebas

34 pruebas del programa de auditoría en verde, cinco de ellas nuevas:

- Todo control se explica sin vocabulario técnico, y su `pregunta` pregunta.
- Un catálogo sin lenguaje llano se rechaza.
- El glosario define las tres conclusiones.
- El papel conserva su versión llana, **en el archivo** y no solo en memoria.
- El informe abre en lenguaje llano y conserva el técnico entero.
