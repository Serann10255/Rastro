# Sustentación

Fecha: 2026-09-26

Guiones de las dos sustentaciones. **Son la fuente de las diapositivas**: el
módulo [`presentacion`](../modulos/presentacion/README.md) los lee al construir,
así que para cambiar una diapositiva se edita aquí, no en el código.

| Guion | Asignatura | Deck |
|---|---|---|
| [`sustentacion-rastro.md`](sustentacion-rastro.md) | Cloud Computing (ISD38) | `/rastro` |
| [`sustentacion-cotejo.md`](sustentacion-cotejo.md) | Auditoría de Sistemas (ISD39) | `/cotejo` |

Cada guion sigue los siete bloques que exige el docente: presentación del
sistema, planificación, metodología, riesgos y controles, normativas, hallazgos
y evidencias, y conclusiones.

## Reglas para editar

- **Ninguna cifra es decorativa.** Todas salen de la Entrega 2, de la
  verificación del despliegue del 26/09/2026, de la ejecución de referencia
  `20260926T235724886Z-4f87a8` o del código. No se inventan ni se redondean.
- **El número de cada diapositiva lo escribe el autor** (`## 7 · Título`). Si se
  inserta una, hay que renumerar las siguientes y revisar las notas que citan
  números («desarrollarlo en la 23»). La construcción avisa de los saltos.
- **Cada diapositiva lleva su guion hablado:** `> Guion: Sergio. …`, con lo que
  dice quien la presenta. Debajo, si hace falta, `> Indicación: …` (cómo
  decirlo) y `> Si preguntan: …` (respuesta preparada). Del guion salen el
  reparto de intervenciones y el tiempo estimado del índice.
- **El guion se escribe a partir de lo que muestra la diapositiva.** Si cambia
  una cifra en la diapositiva, cambia también en el guion.
- El formato completo está en el
  [README del módulo](../modulos/presentacion/README.md#formato-del-guion).

## Reparto de intervenciones

Equilibrado en número de diapositivas y en tiempo. Cada integrante abre un deck
y, entre los dos, presenta un bloque de riesgos y controles y uno de hallazgos.

| Deck | Sergio | Nicolás | Oscar |
|---|---|---|---|
| Rastro | 1–9 y 28 · ≈ 4 min 45 s | 10–18 · ≈ 4 min 55 s | 19–27 · ≈ 4 min 30 s |
| Cotejo | 19–27 · ≈ 5 min 20 s | 1–9 y 28 · ≈ 5 min 10 s | 10–18 · ≈ 4 min 50 s |

El índice del sitio lo recalcula desde el guion cada vez que cambia.

## Matrices de permisos

Las diapositivas de roles (Rastro 15–18, Cotejo 14–18) reproducen el catálogo
de `libs/rastro_core/authz.py`: 19 operaciones y los cinco roles de fábrica. Se
cotejaron celda por celda contra `ROLES_INTEGRADOS` el 2026-09-26. **Si cambia
un rol en el código, hay que actualizar estas diapositivas**; véase
[roles-y-permisos](../modulos/roles-y-permisos/README.md).

## Revisar tras editar

```bash
cd presentacion
npm test          # el guion compila sin avisos
npm run dev       # http://localhost:5177/rastro/?guion muestra si alguna se desborda
```
