# ADR-006 · Ampliación del alcance a sistema de gestión de transporte

Fecha: 2026-09-10 · Estado: aceptada · Amplía el alcance de la Entrega 1

## Contexto

La Entrega 1 delimita el sistema a **cinco operaciones** sobre el ciclo de vida
del envío y excluye de forma explícita, entre otras cosas, el registro autónomo
de organizaciones y todo lo que no figure como incluido. Esa delimitación fue
correcta para lo que el documento buscaba: acotar un problema verificable dentro
de un periodo académico.

El equipo decidió después construir un sistema de gestión de transporte
utilizable en operación real, con la intención de que el proyecto pueda tener
recorrido más allá de la entrega. Eso exige cosas que el alcance original no
contemplaba: cuentas de usuario administradas desde el propio sistema, catálogos
de tiendas, clientes y transportistas, registro masivo, generación de guías y un
tablero de operación.

Esta decisión existe para que el código y el documento no se contradigan. Un
sistema que hace más de lo que su documento declara no es un problema técnico,
pero sí un problema de trazabilidad: el evaluador no puede juzgar contra un
criterio que ya no describe lo construido.

## Decisión

Se amplía el alcance. Lo que entra:

| Capacidad | Por qué entra |
|---|---|
| Directorio de usuarios propio, con contraseñas derivadas y sesiones revocables | Sin cuentas administrables, el control de acceso por rol es una demostración, no un control |
| Catálogo de estados con código numérico | Un TMS intercambia archivos con transportistas y clientes; el nombre en texto es frágil, el código no |
| Tiendas, clientes y transportistas | Un envío no se registra en el vacío: sale de algún sitio, lo despacha alguien y lo mueve alguien |
| Registro masivo y guías imprimibles | Es la operación diaria de un cliente corporativo; sin ella nadie usa el sistema |
| Tablero con indicadores de la empresa | Lo que un despachador necesita ver al abrir el sistema |
| Cierre por devolución y por cancelación | Un envío que no llega tiene que poder cerrarse; sin ellos quedaría abierto para siempre |

Lo que **sigue excluido**, y por qué:

| Excluido | Razón |
|---|---|
| Registro autónomo de organizaciones | Pertenece a un modelo comercial. Las empresas se aprovisionan con el despliegue |
| Optimización de rutas | Exige datos de tráfico y dispositivos fuera del presupuesto del laboratorio |
| Rastreo por posición continua | Misma razón, más la objeción ética: el sistema documenta el envío, no vigila a la persona |
| Facturación | No forma parte del problema planteado |
| Aduanas y envíos internacionales | El problema se delimita a la operación urbana en una sola ciudad |

## Consecuencias

**Sobre los requisitos.** Los nueve requisitos preliminares (REQ-01 a REQ-09) se
mantienen íntegros y sus criterios de aceptación siguen verificándose con las
mismas pruebas. Lo añadido no los sustituye: los rodea.

**Sobre la máquina de estados.** Se añadieron dos estados de cierre —`DEVUELTO`
y `CANCELADO`— sin tocar el flujo principal ni las transiciones existentes. Las
pruebas que fijaban el comportamiento anterior siguieron pasando salvo dos, que
fallaron por la razón correcta: `DEVUELTO` es ahora una salida legítima de una
incidencia. Se actualizaron declarando el motivo.

**Sobre Cotejo.** El control C-07 verifica que el sistema rechaza transiciones no
contempladas, y sigue haciéndolo. El catálogo de auditoría no cambia: lo
auditado creció, pero los ocho controles siguen siendo los que el documento
declaró y el que falte se atribuye a una decisión de alcance, no a un olvido.

**Sobre la Entrega 2.** El documento debe recoger esta ampliación en su apartado
de alcance, con la misma tabla de incluidos y excluidos. Mantener la versión
anterior y entregar este sistema sería presentar una cosa y construir otra.

**Riesgo asumido.** Un alcance mayor es más superficie que probar y más que
sostener con un equipo de tres personas con dedicación parcial. Se acota
manteniendo intactas las exclusiones de arriba: lo que se añadió tiene pruebas y
lo que no se añadió está dicho.
