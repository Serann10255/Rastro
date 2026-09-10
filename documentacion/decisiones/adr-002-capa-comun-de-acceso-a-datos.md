# ADR-002 · Una única capa de acceso a datos para todos los microservicios

Fecha: 2026-09-10 · Estado: aceptada

## Contexto

El sistema opera sobre infraestructura compartida por varias empresas con
aislamiento estricto de los datos de cada una. El riesgo R-05 lo enuncia sin
rodeos: *una sola consulta sin filtrar por organización basta para exponer los
datos de una empresa a otra*, y eso es una fuga de información, no un defecto
funcional.

La práctica habitual en microservicios es que cada servicio sea dueño de su
acceso a datos. Aplicada aquí, obligaría a implementar y verificar el filtro por
organización seis veces.

## Decisión

Ningún microservicio construye consultas por su cuenta. Todos pasan por
`libs/rastro_core`, donde:

- `claves.py` es el único lugar donde se arma una clave, y **exige** el
  identificador de organización: sin él lanza un error.
- `repository.py` recibe ese identificador desde el token y lo aplica sin
  excepción.
- `dominio.cargar_envio` es el único camino para recuperar un envío, y aplica
  tanto el filtro por organización como la restricción del conductor a sus
  propios envíos.

Lo que sí queda separado es la responsabilidad: cada servicio despliega, escala
y falla por su cuenta, y en AWS cada uno es una función Lambda distinta.

## Consecuencias

**A favor.** El control de aislamiento se implementa una vez y se prueba una
vez. Que exista un único camino es lo que lo hace verificable: no hay una
segunda ruta que pueda olvidarlo. La prueba sustantiva C-06 de Cotejo recorre
todas las rutas de lectura precisamente porque bastaría una sin filtrar.

**En contra.** Los servicios comparten una dependencia y un cambio en ella los
afecta a todos, lo que reduce su independencia de despliegue. Se acepta porque
el riesgo que evita es mayor que el acoplamiento que introduce.

**Alternativa descartada.** Un servicio de datos independiente al que los demás
consultaran por red. Añadiría un salto de red por operación y un punto único de
fallo sin mejorar el control: el filtro seguiría siendo una línea de código en
un solo sitio.
