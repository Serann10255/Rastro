# Cambios · 2026-09-26 · Diapositivas de sustentación y matriz de permisos

Nuevo módulo [`presentacion`](../modulos/presentacion/README.md): los dos decks
de sustentación se generan al construir desde
[`documentacion/sustentacion/`](../sustentacion/README.md). Los guiones ganan
las diapositivas de roles y permisos que faltaban.

---

## Módulo `presentacion`

| Qué | Dónde |
|---|---|
| Compilador de guiones (Markdown → deck) con sus pruebas | `presentacion/compilador/` |
| Visor, guion imprimible y modo lectura | `presentacion/src/deck/` |
| Figuras en SVG sobre las fichas de diseño | `presentacion/src/figuras/` |
| Índice con el reparto de intervenciones | `presentacion/src/Inicio.tsx` |

Sin dependencias nuevas fuera de React y Vite, las mismas de las otras dos
interfaces. Las pruebas usan el ejecutor de Node.

## Cambios en los guiones

**Rastro** — tres diapositivas nuevas en el bloque 4, tras «Roles y permisos»:

| N.º | Diapositiva |
|---|---|
| 16 | Matriz de permisos · envíos y operación (8 operaciones × 5 roles) |
| 17 | Matriz de permisos · administración y auditoría (11 operaciones × 5 roles) |
| 18 | Reglas de los roles que no se pueden configurar |

Las antiguas 16–25 pasan a 19–28. La diapositiva 3 incorpora la figura de la
arquitectura en AWS y su nota una frase sobre cómo señalarla.

**Cotejo** — cuatro diapositivas nuevas en el bloque 4, tras «Roles y permisos
del sistema auditado»: las dos matrices (15 y 16), las reglas (17, que dice qué
celda comprueba C-05) y «Permisos fuera de la aplicación» (18: rol compartido,
ejecutor con escritura, usuarios de prueba, interfaz restringida). Las antiguas
15–24 pasan a 19–28; las dos notas que citaban «la 19» citan ahora la 23. La
diapositiva 8 incorpora la figura del ejecutor y sus tres fuentes de evidencia.

**Origen de los datos nuevos.** Las matrices salen de `ROLES_INTEGRADOS` en
`libs/rastro_core/authz.py` y se cotejaron celda por celda: 19 operaciones, cero
diferencias, totales 17 · 12 · 9 · 6 · 8. Las reglas, del mismo archivo, de
`services/auth/main.py` y de sus pruebas. La diapositiva 18 de Cotejo, de las
tablas 4, 11 y 14 de la Entrega 2.

## Verificación

| Comprobación | Resultado |
|---|---|
| `npm test` (16 pruebas, incluidos los dos guiones reales) | 16 superadas, sin avisos |
| `npm run build` | 35 diapositivas por deck: 28 de contenido y 7 portadillas |
| Desbordes en el lienzo | Ninguno. La 17 de Rastro y la 16 de Cotejo quedan con 11 px de holgura |
| Tamaño mínimo del contenido | 24,1 px (dato de la cuenta en Rastro 3); figuras a 25 px |
| Impresión (Edge, sin interfaz) | 35 páginas horizontales por deck, notas debajo de cada diapositiva |
| Enlace directo `/rastro#7` | Abre la diapositiva 7 |
| Teclado, clic en los bordes, notas | Comprobados en navegador |
| 360 px | Modo lectura sin desbordes en el documento ni en las tarjetas |
| Pantalla completa | **No comprobada**: el navegador integrado no concede la API |

## Observaciones para el equipo

Encontradas al construir, no corregidas porque son decisiones de contenido:

1. **Cómo se detectó el secreto — corregido en las diapositivas 23 y 25 de los
   dos decks.** Decían
   que lo detectó el control automatizado y no la revisión manual. El registro de
   [H-01](2026-09-26-h01-secreto-expuesto.md) dice «detección durante la revisión
   del despliegue» (≈23:03 UTC) y C-09 se añadió después (commit `0a27b47`,
   23:44 UTC); la Entrega 2 de Rastro también dice «revisión propia». Lo que el
   control detectó fue el secreto que **permanece en el historial** (C-09b).
   Ahora Rastro 23 dice que lo detectó el equipo y que desde entonces lo vigila
   C-09, y Cotejo 23 lo presenta como un hueco del catálogo, junto al error de
   criterio de C-02. Rastro 25 dice que el incidente se detectó a mano y dejó un
   control que antes no existía, y Cotejo 25 cierra con que la verificación vale
   lo que vale su catálogo. **Sigue afirmándolo** la Entrega 2 de Cotejo
   (apartados 1.1, 3.1, 9.1, 10, 14 y 15.1).
6. **Las dos ejecuciones — corregido en Cotejo 25.** Decía «dos ejecuciones que
   reproducen la misma clasificación». Según la Entrega 2 (apartado 9.3), la
   segunda cambió C-02 de desviado a conforme por la única diferencia
   introducida a propósito, cargar una evidencia, y las otras diez se
   mantuvieron. La diapositiva lo dice ahora así y la nota de Oscar lo explica.
2. **Reparto de intervenciones.** Según las notas: en Cotejo, Oscar presenta 16
   de 28 diapositivas, Nicolás 6 y Sergio 6; en Rastro, Oscar 12, Sergio 10 y
   Nicolás 6. Las diapositivas nuevas siguen al presentador de su bloque. El
   índice del sitio muestra el reparto actualizado.
3. **Rúbrica, criterio 3.** Las tablas de riesgo tienen probabilidad e impacto,
   pero no una columna de vulnerabilidad ni una prioridad explícita.
4. **«Falla cerrado».** Si la tabla de roles no responde se aplican los de
   fábrica (`http.py`). Es más restrictivo solo si la empresa amplió sus roles;
   si los había recortado, el de fábrica concede más. No se llevó a las
   diapositivas por eso y porque no tiene prueba.
5. La tabla 6 de la Entrega 2 de Rastro atribuye al despachador la reanudación
   tras incidencia; el código y la tabla 16 del mismo documento se la dan al
   coordinador.
