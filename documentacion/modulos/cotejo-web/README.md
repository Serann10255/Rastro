# Módulo `cotejo-web` — interfaz del programa de auditoría

Ubicación: `cotejo/web/` · Puerto local: 5175 · Stack: React 18 + TypeScript + Vite

## Qué hace

Tres pantallas, que son los tres momentos del trabajo de auditoría.

| Pestaña | Para qué |
|---|---|
| **Ejecución** | Ejecutar el catálogo, ver cobertura, resultado por control, papeles de trabajo y hallazgos |
| **Catálogo** | Ver contra qué criterio se va a juzgar, antes de ejecutar nada |
| **Reproducibilidad** | Comparar dos ejecuciones y comprobar que clasifican igual |

## Decisiones

**Color de acento distinto al de Rastro.** Las fichas de diseño se comparten
—son dos entregas del mismo equipo y mantener dos sistemas visuales sería trabajo
sin retorno—, pero el acento es morado en lugar de azul. El auditor debe saber
sin dudarlo si está mirando el sistema o el programa que lo evalúa.

**La limitación de independencia está siempre a la vista.** No en una nota al
pie: es la primera cosa que se lee en cualquier pantalla. El equipo audita un
sistema que él mismo construyó, y esa condición no debería poder olvidarse
mientras se leen los resultados.

**«No ejecutada» tiene su propio color.** No es verde ni rojo, sino gris con
borde marcado, y la pantalla añade un aviso explícito cuando hay controles sin
comprobar. Un control no ejecutado no es un control conforme, y confundirlos sería
el peor resultado posible de un trabajo de aseguramiento.

**El papel de trabajo muestra la salida literal, sin editar.** Y encima, si la
huella recalculada coincide con la registrada. Abrir el papel es también
comprobar que nadie lo tocó.

**La comparación avisa si ambas ejecuciones son de la misma identidad.** La
comprobación de reproducibilidad tiene más valor cuando la segunda la ejecuta un
integrante distinto del que desarrolló el ejecutor.

**El informe se muestra con ancho fijo y desplazamiento propio.** Usa 78
columnas y su alineación es parte del formato: reflujarlo lo haría ilegible.

## Comportamiento responsive

Mismo enfoque mobile-first y mismos breakpoints que
[`interfaz-web`](../interfaz-web/README.md): sm 640, md 768, lg 1024, xl 1280,
con 360 px como ancho de referencia.

| Elemento | Cómo se adapta |
|---|---|
| Pestañas | Fila deslizable en móvil |
| Métricas de cobertura | Una columna en móvil, dos en `sm`, cuatro en `lg` |
| Tarjetas de control | Siempre una columna: el enunciado y el criterio son texto largo |
| Papel de trabajo | Hoja inferior en móvil, ventana centrada desde `sm` |
| Evidencia y hashes | `overflow-wrap: anywhere`; la evidencia tiene alto máximo y scroll propio |
| Informe en texto | Ancho fijo con `overflow-x: auto` dentro de su bloque |

Verificado a 360 px sin scroll horizontal en el documento.

## Dependencias y relaciones

- **Consume**: [`cotejo-api`](../cotejo-api/README.md) para todo, y el proveedor
  de identidad de Rastro para autenticarse.
- **Comparte estilos con** [`interfaz-web`](../interfaz-web/README.md): copia
  `tokens.css`, `base.css` y `componentes.css`, y añade `cotejo.css`.

**Sobre la copia de estilos.** Son archivos duplicados, no un paquete compartido.
Es una decisión deliberada: son dos proyectos académicos distintos, entregados
por separado, y un paquete común obligaría a que uno no pudiera evaluarse sin el
otro. El coste es que un cambio de fichas hay que replicarlo; se acepta porque
las fichas cambian poco y la independencia de entrega vale más.

## Desarrollo

```bash
cd cotejo/web
npm install
npm run dev        # http://localhost:5175
```

Vite reenvía `/cotejo` al programa de auditoría y `/auth` al proveedor de
identidad de Rastro.
