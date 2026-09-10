# ADR-011 · Doble registro: lenguaje llano delante, término del oficio detrás

Fecha: 2026-09-10 · Estado: aceptada · Afecta a Cotejo (catálogo, consola, informe e interfaz)

## Contexto

Cotejo estaba escrito enteramente en el vocabulario de la auditoría de sistemas.
Una pantalla decía:

> **Cobertura 5/8** · Controles con resultado · `[NO_EJECUTADA] C-01` · Papel de
> trabajo · Huella de evidencia · Condición / criterio / causa / efecto

Todo eso es correcto y es, literalmente, lo que se evalúa en la asignatura: son
los términos de ITAF, COBIT e ISO que un tercero espera encontrar en un informe.
El problema no es que estén: es que **eran lo único que había**.

Consecuencias concretas:

- Para saber si algo se había roto había que saberse de memoria la diferencia
  entre `CONFORME`, `DESVIADO` y `NO_EJECUTADA`. La distinción más importante
  del programa —que lo no revisado no está aprobado— dependía de reconocer una
  palabra en mayúsculas.
- Un hallazgo se presentaba en cinco campos formales antes de decir qué pasa. Un
  hallazgo que no se entiende no se corrige, y quien decide sobre él no suele
  ser quien lo escribió.
- El papel de trabajo mostraba un volcado JSON. La evidencia literal es
  irrenunciable, pero como *primera* cosa que se ve no comunica nada.

## Decisión

**Cada cosa que Cotejo muestra se dice dos veces: primero en la frase que se
entiende sin haber estudiado auditoría, y pegado a ella el término del oficio.**

Ni una cosa ni la otra sobra:

- El término técnico es lo que espera leer quien reciba el informe y lo que se
  evalúa; quitarlo destruiría el entregable.
- La frase llana es lo que permite discutir un hallazgo con quien tiene que
  decidir sobre él; sin ella el entregable no se lee.

### Dónde vive el lenguaje llano

**En el catálogo (`cotejo/catalogo/controles.yaml`), no en cada interfaz.** Cada
control declara tres campos nuevos, exigidos igual que el criterio:

| Campo | Qué es |
|---|---|
| `pregunta` | Lo que el control responde, en forma de pregunta: *¿Un conductor puede crear envíos, que es trabajo de otra persona?* |
| `en_simple` | Qué se hace exactamente para comprobarlo |
| `si_falla` | Qué pasaría si eso no se cumpliera |

Más un `que_es_esto` para todo el programa y un `glosario` de 21 términos.

Que vivan en el catálogo es la parte que importa: si la web escribiera su propia
explicación de cada control, la pantalla y el informe acabarían diciendo cosas
distintas del mismo control, y la del informe es la que vale. Ahora la consola,
el informe en texto y la interfaz web leen las mismas frases.

### Se exige, no se sugiere

`cargar_catalogo` rechaza un catálogo cuyo control no declare los tres campos,
igual que rechaza uno sin criterio y por la misma razón: **escribir la
explicación después de ver el resultado permitiría acomodarla al resultado.** Un
control que solo sabe decirse en vocabulario técnico no se puede discutir, y eso
es un defecto del control, no del lector.

### Las tres respuestas

| Se muestra | Término técnico | Qué significa |
|---|---|---|
| **BIEN** | `CONFORME` | Se probó y cumplió la regla escrita de antemano |
| **MAL** | `DESVIADO` | Se probó y no cumplió; se convierte en hallazgo |
| **SIN REVISAR** | `NO_EJECUTADA` | Ni bien ni mal: no se pudo probar aquí |

Siguen siendo tres. Llamar «sin revisar» a lo no ejecutado lo separa de «bien»
tanto como `NO_EJECUTADA` lo separa de `CONFORME`, que es justamente el riesgo
R-04 del documento: transmitir más cobertura de la real.

## Alternativas descartadas

**Sustituir el vocabulario técnico por palabras fáciles.** Habría dejado el
entregable sin los términos por los que se evalúa, y a Cotejo sin el registro
que un tercero espera. Se rechazó sin discusión.

**Poner las definiciones en un tooltip.** En un móvil no existe el hover. El
término va escrito, en menor jerarquía, siempre visible.

**Un glosario aparte, en la documentación.** Una explicación que exige cambiar
de pantalla no se lee. El diccionario existe como pestaña, pero además cada
término aparece explicado donde se usa.

**Escribir las frases llanas en el frontend.** Es lo más rápido y lo que rompe
la coherencia entre la web y el informe en la primera corrección de estilo.

## Consecuencias

- El informe en texto abre con una sección **«1. En palabras simples»** —qué es
  esto, qué salió, cómo se leen las tres respuestas— y sigue con el registro
  técnico completo, ahora numerado del 2 al 5.
- La consola dice `[BIEN] C-05 ¿Un conductor puede crear envíos?` y explica sus
  códigos de salida con palabras.
- `python -m cotejo glosario` es un comando nuevo.
- El papel de trabajo, en la web, se lee como una narración —qué se hizo, qué
  contestó Rastro, por qué importa— con la evidencia literal detrás de un
  `<details>`. La evidencia no se toca: cambia de sitio, no de contenido.
- Añadir un control cuesta tres frases más. Es deliberado: si un control nuevo
  no se puede explicar, probablemente tampoco está claro qué comprueba.
