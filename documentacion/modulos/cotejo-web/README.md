# Módulo `cotejo-web` — interfaz del programa de auditoría

Ubicación: `cotejo/web/` · Puerto local: 5175 · Stack: React 18 + TypeScript + Vite

## Qué hace

Cuatro pantallas, que son los cuatro momentos del trabajo de auditoría.

| Pestaña | Se llama en pantalla | Para qué |
|---|---|---|
| Ejecución | **Revisión** | Ejecutar el catálogo y leer qué salió bien, qué mal y qué no se pudo probar |
| Catálogo | **Qué se revisa** | Ver contra qué criterio se va a juzgar, antes de ejecutar nada |
| Reproducibilidad | **Repetir** | Comparar dos ejecuciones y comprobar que clasifican igual |
| Glosario | **Diccionario** | Las palabras del oficio, explicadas |

## Cómo está escrita esta interfaz

**Doble registro: la frase llana delante, el término del oficio detrás.** Es la
regla de redacción de toda la aplicación y está en
[ADR-011](../../decisiones/adr-011-doble-registro-en-la-interfaz.md). Un control
se titula con su pregunta —*¿Una empresa puede ver los envíos de otra?*— y
lleva `en auditoría: prueba sustantiva` pegado en menor jerarquía. Ninguna de
las dos versiones sobra: sin la técnica no hay entregable, sin la llana no hay
quien lo lea.

**Las frases llanas no se escriben aquí.** Vienen del catálogo, por la API. Si
esta interfaz escribiera su propia explicación de cada control, la pantalla y el
informe acabarían diciendo cosas distintas del mismo control.

| Se muestra | Término técnico |
|---|---|
| **BIEN** | `CONFORME` |
| **MAL** | `DESVIADO` |
| **SIN REVISAR** | `NO_EJECUTADA` |

## Decisiones

**Comparte el sistema de diseño con Rastro**, que vive en `design/` y no se
copia. Aquí solo queda `identidad.css` con el índigo de la marca: el color del
examen, frente al azul y el cian del recorrido que usa Rastro. Que parezcan
productos sin relación sería un problema de producto —el mismo usuario abre los
dos el mismo día— y que fueran indistinguibles sería peor, porque uno audita al
otro. Véase [ADR-008](../../decisiones/adr-008-sistema-de-diseno-compartido.md).

**El logotipo dice lo que hace el programa**: dos hojas superpuestas —lo
declarado y lo observado— con la marca de verificación que solo aparece cuando
ambas coinciden, y tres eslabones de la cadena de huellas. Sin lupa: una lupa
dice «buscar», y auditar no es buscar sino comparar contra un criterio declarado
de antemano.

**La pantalla de acceso no prefija ninguna cuenta.** Tenía escrito un correo
válido; aunque esta interfaz se sirve en la máquina del auditor, escribir una
cuenta que existe en el formulario de entrada es publicarla.


**Color de acento distinto al de Rastro.** Las fichas de diseño se comparten
—son dos entregas del mismo equipo y mantener dos sistemas visuales sería trabajo
sin retorno—, pero el acento es morado en lugar de azul. El auditor debe saber
sin dudarlo si está mirando el sistema o el programa que lo evalúa.

**La limitación de independencia está siempre a la vista.** No en una nota al
pie: es la primera cosa que se lee en cualquier pantalla. El equipo audita un
sistema que él mismo construyó, y esa condición no debería poder olvidarse
mientras se leen los resultados.

**El resultado se lee en una frase, no en cuatro números.** Al terminar una
revisión lo primero que aparece es *«Revisamos 8 cosas que Rastro dice cumplir.
5 salieron bien, 0 salieron mal y 3 quedaron sin revisar»*, con una barra de
tres colores debajo. Las métricas siguen ahí, después. Un tablero de cifras
obliga a cada lector a componer la conclusión por su cuenta, y «5 de 5 bien»
suena a examen perfecto cuando quedaron tres preguntas sin responder.

**Hay un panel de tres pasos que explica el método**, y se puede ocultar: se
recuerda oculto en `localStorage`. Una explicación que no se puede cerrar acaba
siendo ruido para quien ya la leyó.

**Mientras se ejecuta se enseña la lista de lo que se va a comprobar, sin marcar
ninguna como hecha.** La API responde de una vez y no informa de su avance:
fingir un progreso por pasos sería inventar. Se dice qué está pasando y que
tarda unos segundos.

**«No ejecutada» tiene su propio color.** No es verde ni rojo, sino gris con
borde marcado, y la pantalla añade un aviso explícito cuando hay controles sin
comprobar. Un control no ejecutado no es un control conforme, y confundirlos sería
el peor resultado posible de un trabajo de aseguramiento.

**El papel de trabajo se lee como una narración**: qué se hizo, qué contestó
Rastro, por qué importa, y el paso a paso. Cada paso lleva una línea que traduce
la respuesta —*«Rastro dijo que ese usuario no tiene permiso (código 403)»*— y
debajo, plegado, el JSON tal como llegó. La evidencia literal no se toca: cambia
de sitio, no de contenido. Como *primera* cosa que se ve, un volcado JSON no
comunica nada; como respaldo de una frase que ya se entendió, lo respalda.

**El registro técnico va en bloques plegados, cerrados por omisión.** Marco de
referencia, criterio, procedimiento, evidencia esperada, condición/criterio/
causa/efecto. Nada se pierde por plegarlo: se pierde por ponerlo delante de
quien no lo puede leer.

**Al abrir el papel se comprueba si la huella recalculada coincide con la
registrada**, y se dice con esas palabras: *«Este archivo no se ha tocado desde
que se guardó»*. Abrir el papel es también comprobar que nadie lo editó.

**La comparación avisa si ambas ejecuciones son de la misma identidad.** La
comprobación de reproducibilidad tiene más valor cuando la segunda la ejecuta un
integrante distinto del que desarrolló el ejecutor.

**El informe se muestra con ancho fijo y desplazamiento propio.** Usa 78
columnas y su alineación es parte del formato: reflujarlo lo haría ilegible.

## Comportamiento responsive

Mismo enfoque mobile-first y mismos breakpoints que Rastro, porque es
literalmente el mismo sistema de diseño:
[sistema-de-diseno](../sistema-de-diseno/README.md). Ancho de referencia 360 px;
sm 640, md 768, lg 1024, xl 1280.

| Elemento | Cómo se adapta |
|---|---|
| Armazón | Barra superior en móvil; **columna lateral desde 1024 px** |
| Pestañas | Fila deslizable en móvil, lista vertical en la columna lateral |
| Métricas de cobertura | Una columna en móvil, dos en `sm`, cuatro en `lg` |
| Tarjetas de control | Siempre una columna: el enunciado y el criterio son texto largo |
| Papel de trabajo | Hoja inferior en móvil, ventana centrada desde `sm` |
| Evidencia y hashes | `overflow-wrap: anywhere`; la evidencia tiene alto máximo y scroll propio |
| Informe en texto | Ancho fijo con `overflow-x: auto` dentro de su bloque |
| Veredicto | Frase a `--t-lg`; sube a `--t-xl` desde `sm`. La barra de resultado es fluida (`%`) |
| Insignia de respuesta | `flex-wrap`: en 360 px el término técnico cae bajo la palabra en vez de desbordar |
| Diccionario | Una columna en móvil; rejilla `auto-fill` de mínimo `min(20rem, 100%)` desde `md` |
| Detalle plegado | El `summary` cumple los 44 px de área táctil como cualquier otro control |

Verificado a 360 px sin scroll horizontal en el documento.

## Dependencias y relaciones

- **Consume**: [`cotejo-api`](../cotejo-api/README.md) para todo, y el proveedor
  de identidad de Rastro para autenticarse.
- **Comparte el sistema de diseño** de [`design/`](../sistema-de-diseno/README.md)
  con [`interfaz-web`](../interfaz-web/README.md), y añade `identidad.css` con su
  color de marca y `cotejo.css` con lo suyo.

**Antes eran copias.** `tokens.css` y `base.css` estaban duplicados byte a byte y
`componentes.css` ya había empezado a divergir. Se decidió compartirlos de
verdad: una copia no es compartir, porque al corregir un color en una aplicación
la otra se queda atrás y nadie lo nota hasta ver las dos pantallas seguidas.

**Sobre la independencia de entrega.** Los dos proyectos siguen siendo dos, y
`design/` no pertenece a ninguno: es una carpeta del repositorio que ambos usan,
del mismo modo que `libs/rastro_core` ya sostenía al programa de auditoría con
su verificador de cadena. La dependencia se declara, que es lo que la hace
evaluable.

## Desarrollo

```bash
cd cotejo/web
npm install
npm run dev        # http://localhost:5175
```

Vite reenvía `/cotejo` al programa de auditoría y `/auth` al proveedor de
identidad de Rastro.
