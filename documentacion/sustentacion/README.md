# Sustentación

Fecha: 2026-09-26 · Versión corta: 2026-10-16

Guiones de las dos sustentaciones. **Son la fuente de las diapositivas**: el
módulo [`presentacion`](../modulos/presentacion/README.md) los lee al construir,
así que para cambiar una diapositiva se edita aquí, no en el código.

| Guion | Asignatura | Deck | Diapositivas | Guion hablado |
|---|---|---|---|---|
| [`sustentacion-rastro.md`](sustentacion-rastro.md) | Cloud Computing (ISD38) | `/rastro` | 9 | ≈ 4 min 10 s |
| [`sustentacion-cotejo.md`](sustentacion-cotejo.md) | Auditoría de Sistemas (ISD39) | `/cotejo` | 10 | ≈ 4 min 10 s |

Cada guion sigue los siete bloques que exige el docente: presentación del
sistema, planificación, metodología, riesgos y controles, normativas, hallazgos
y evidencias, y conclusiones.

## Versión corta, para cinco minutos

El 2026-10-16 se supo que cada sustentación dura **cinco minutos** y sigue otro
grupo. Los guiones pasaron de 28 diapositivas más 7 portadillas (≈ 15 min) a
**una o dos diapositivas por bloque**:

- **Sin portadillas** (`portadillas: no`): cada diapositiva lleva su bloque
  encima del título, «BLOQUE 4 · RIESGOS Y CONTROLES», así que los siete
  bloques se siguen viendo sin gastar siete clics.
- **Nada se pierde.** Lo que salió de las láminas —objetivos específicos,
  matriz completa de permisos, desglose de pruebas, rutas de las evidencias,
  acciones de prioridad media— pasó a la respuesta preparada («Si preguntan»)
  de la diapositiva que le corresponde. Se ve con `n` en el visor y en el guion
  impreso.
- **≈ 4 min 10 s de habla a 130 palabras por minuto**, para dejar margen a los
  cambios de diapositiva y a los nervios. Cronometrarse en voz alta antes del
  lunes.
- La versión completa queda en
  [`entregables/sustentacion/`](../entregables/sustentacion/) como
  `… sustentación completa.pdf` y `… completa guion.pdf`, y en el historial del
  repositorio (commit `36773f2`).

| Bloque | Rastro | Cotejo |
|---|---|---|
| — | 1 · Portada | 1 · Portada |
| 1 · Presentación del sistema | 2 · El problema y el sistema | 2 · El problema y el sistema auditado |
| 2 · Planificación | 3 · Objetivo, alcance y plan | 3 · Objetivo, alcance y plan |
| 3 · Metodología | 4 · Metodología y técnicas | 4 · Metodología y técnicas |
| 4 · Riesgos y controles | 5 · Riesgos y controles · 6 · Roles y separación de funciones | 5 · Amenazas y controles · 6 · Roles y segregación de funciones |
| 5 · Normativas | 7 · Normativas y cumplimiento | 7 · Normativas y cumplimiento |
| 6 · Hallazgos y evidencias | 8 · Evidencias y hallazgo principal | 8 · Hallazgos · 9 · También nos auditamos |
| 7 · Conclusiones y mejoras | 9 · Conclusiones y mejoras | 10 · Conclusiones y mejoras |

## Reglas para editar

- **Ninguna cifra es decorativa.** Todas salen de la Entrega 2, de la
  verificación del despliegue del 26/09/2026, de la ejecución de referencia
  `20260926T235724886Z-4f87a8` o del código. No se inventan ni se redondean.
- **Cinco minutos es el límite.** Si se añade algo a una diapositiva, se quita
  otra cosa del guion hablado: el índice del sitio muestra la duración estimada
  de cada deck y de cada integrante. Lo que no cabe va a «Si preguntan».
- **El número de cada diapositiva lo escribe el autor** (`## 7 · Título`). Si se
  inserta una, hay que renumerar las siguientes y revisar las notas que citan
  números. La construcción avisa de los saltos.
- **Cada diapositiva lleva su guion hablado:** `> Guion: Sergio. …`, con lo que
  dice quien la presenta. Debajo, si hace falta, `> Indicación: …` (cómo
  decirlo) y `> Si preguntan: …` (respuesta preparada). Del guion salen el
  reparto de intervenciones y el tiempo estimado del índice.
- **El guion se escribe a partir de lo que muestra la diapositiva.** Si cambia
  una cifra en la diapositiva, cambia también en el guion.
- **Cada uno de los siete bloques necesita al menos una diapositiva**: `npm
  test` lo comprueba.
- El formato completo está en el
  [README del módulo](../modulos/presentacion/README.md#formato-del-guion).

## Reparto de intervenciones

Equilibrado en tiempo. Sergio abre Rastro y Nicolás abre Cotejo; entre los dos
decks, cada integrante presenta riesgos y controles o hallazgos.

| Deck | Sergio | Nicolás | Oscar |
|---|---|---|---|
| Rastro | 1–3 · ≈ 1 min 20 s | 4–6 · ≈ 1 min 30 s | 7–9 · ≈ 1 min 25 s |
| Cotejo | 7–9 · ≈ 1 min 15 s | 1–3 y 10 · ≈ 1 min 35 s | 4–6 · ≈ 1 min 20 s |

El índice del sitio lo recalcula desde el guion cada vez que cambia.

## Matrices de permisos

La diapositiva de roles (Rastro 6, Cotejo 6) resume los cinco roles de fábrica
de `libs/rastro_core/authz.py`; el recuento por rol de las 19 operaciones y las
reglas no configurables están en su «Si preguntan». La matriz celda por celda
quedó en la versión completa (Rastro 16–17, Cotejo 15–16), cotejada contra
`ROLES_INTEGRADOS` el 2026-09-26. **Si cambia un rol en el código, hay que
actualizar las dos**; véase
[roles-y-permisos](../modulos/roles-y-permisos/README.md).

## Revisar tras editar

```bash
cd presentacion
npm test          # el guion compila sin avisos y cubre los siete bloques
npm run dev       # http://localhost:5177/rastro/?guion muestra si alguna se desborda
```
