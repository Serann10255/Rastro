# Cambios · 2026-10-16 · Sustentación corta, para cinco minutos

Cada sustentación dura **cinco minutos** y enseguida sigue otro grupo. Los dos
decks tenían 28 diapositivas más 7 portadillas y un guion de ≈ 15 minutos. Se
reescribieron a **una o dos diapositivas por cada uno de los siete bloques**,
sin perder contenido: lo que salió de las láminas pasó a las respuestas
preparadas («Si preguntan»).

---

## Resultado

| Deck | Antes | Ahora | Guion hablado |
|---|---|---|---|
| Rastro | 28 + 7 portadillas (35 páginas) | 9 diapositivas | ≈ 4 min 10 s (547 palabras) |
| Cotejo | 28 + 7 portadillas (35 páginas) | 10 diapositivas | ≈ 4 min 10 s (547 palabras) |

Estimado a 130 palabras por minuto, el ritmo tranquilo que usa el índice: deja
unos 50 segundos para pasar diapositivas y respirar. Hay que cronometrarse en
voz alta antes de presentar.

| Integrante | Rastro | Cotejo |
|---|---|---|
| Sergio | 1–3 · ≈ 1 min 20 s | 7–9 · ≈ 1 min 15 s |
| Nicolás | 4–6 · ≈ 1 min 30 s | 1–3 y 10 · ≈ 1 min 35 s |
| Oscar | 7–9 · ≈ 1 min 25 s | 4–6 · ≈ 1 min 20 s |

El reparto por bloque está en el
[README de sustentación](../sustentacion/README.md#versión-corta-para-cinco-minutos).

## Qué se fusionó y adónde fue lo que salió

**Rastro**

| Ahora | Reúne (versión completa) | Pasó a «Si preguntan» |
|---|---|---|
| 2 · El problema y el sistema | 2, 3 y 4 | Por qué importa; evidencia no sistemática; cuenta |
| 3 · Objetivo, alcance y plan | 5, 6, 7 y 8 | Objetivos específicos; lista «dentro»; actividades; riesgo del presupuesto |
| 4 · Metodología y técnicas | 9 y 10 | Por qué no un marco ágil completo |
| 5 · Riesgos y controles | 11, 12, 13 y 14 | Activos; datos sintéticos; 404 y no 403; detalle de los controles faltantes; riesgo de identificador literal |
| 6 · Roles y separación de funciones | 15, 16, 17 y 18 | Recuento de las 19 operaciones por rol; reglas no configurables; archivos de prueba |
| 7 · Normativas y cumplimiento | 19 y 20 | Cláusulas ISO; qué control se desvió |
| 8 · Evidencias y hallazgo principal | 21, 22, 23 y 24 | Desglose 84 / 120 / 34; el 404 esperado; cómo se sabe que el secreto no se usó; rutas de las evidencias |
| 9 · Conclusiones y mejoras | 25, 26, 27 y 28 | Acciones de prioridad media y baja; apartado 15.2 |

**Cotejo**

| Ahora | Reúne (versión completa) | Pasó a «Si preguntan» |
|---|---|---|
| 2 · El problema y el sistema auditado | 2 y 3 | Organización; evidencia recuperable; cómo se trata la falta de independencia |
| 3 · Objetivo, alcance y plan | 4, 5, 6 y 7 | Objetivos específicos; diez controles, once resultados; actividades |
| 4 · Metodología y técnicas | 8, 9 y 10 | Por qué ITAF; las cinco técnicas y su porqué |
| 5 · Amenazas y controles | 11, 12 y 13 | Demás activos; enumeración de envíos; controles que existen |
| 6 · Roles y segregación de funciones | 14, 15, 16, 17 y 18 | Recuento por rol; reglas no configurables; usuarios de prueba; interfaz solo auditor |
| 7 · Normativas y cumplimiento | 19 y 20 | Qué cumple y qué incumple, uno por uno |
| 8 · Hallazgos | 21 y 22 | Evidencia de H-01 (papel y huella); por qué los permanentes no se automatizan |
| 9 · También nos auditamos | 23 y 24 | Qué aportó C-09; alcance de la huella SHA-256 |
| 10 · Conclusiones y mejoras | 25, 26, 27 y 28 | C-02 entre ejecuciones; acciones que dependen del entorno; repositorio |

Ninguna cifra nueva: todas siguen saliendo de la Entrega 2, de la verificación
del 26/09/2026 o de la ejecución `20260926T235724886Z-4f87a8`.

## Cambios en el módulo `presentacion`

| Qué | Dónde |
|---|---|
| Opción `portadillas: no`: los `# BLOQUE` marcan el bloque sin ocupar diapositiva | `presentacion/compilador/sustentacion.ts` |
| El bloque se rotula sobre el título de cada diapositiva y sale del pie | `presentacion/src/deck/Diapositiva.tsx`, `presentacion/src/estilos/presentacion.css` |
| El recuento ya no dice «0 portadillas» | `presentacion/src/deck/formato.tsx`, `Guion.tsx`, `Inicio.tsx` |
| La prueba de los guiones comprueba los siete bloques en orden, no siete portadillas; prueba nueva para la opción | `presentacion/compilador/sustentacion.test.ts` |

## PDF

En [`entregables/sustentacion/`](../entregables/sustentacion/):

| Archivo | Páginas |
|---|---|
| `Rastro · sustentación.pdf` y `… guion.pdf` | 9 |
| `Cotejo · sustentación.pdf` y `… guion.pdf` | 10 |
| `… sustentación completa.pdf` y `… completa guion.pdf` (los de antes, renombrados) | 35 |

Generados con Edge sin interfaz y tema claro, con la orden del
[README del módulo](../modulos/presentacion/README.md#cómo-se-usa).

## Verificación

- `npm test` en `presentacion/`: 19 pruebas, 0 fallos; los dos guiones compilan
  sin avisos.
- `/rastro/?guion` y `/cotejo/?guion`: «Ninguna se desborda».
- A 360 px (modo lectura): sin scroll horizontal; las tablas se desplazan dentro
  de su contenedor.
- Pendiente: cronometrar cada deck en voz alta con los tres integrantes.
