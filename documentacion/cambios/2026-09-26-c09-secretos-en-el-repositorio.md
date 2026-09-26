# Cambios · 2026-09-26 · C-09: secretos en el repositorio

Cotejo gana tres controles (catálogo 0.3): de ocho pasa a once. Se agregan por
un riesgo que ya se materializó una vez: el secreto de firma de los tokens
quedó versionado en el repositorio público
([H-01](2026-09-26-h01-secreto-expuesto.md)), y ninguno de los ocho controles
anteriores lo habría detectado.

Detalle del diseño en el [módulo Cotejo](../modulos/cotejo/README.md#c-09-secretos-en-el-repositorio).

---

## Los tres controles

| Id | Pregunta | Tipo | Severidad |
|---|---|---|---|
| C-09a | ¿Hay algún secreto versionado hoy, en el árbol actual? | cumplimiento | alta |
| C-09b | ¿Hay algún secreto en el historial de commits? | cumplimiento | media |
| C-09c | ¿Algún secreto hallado sigue siendo aceptado por el sistema? | sustantiva | alta |

## Por qué tres y no dos

La propuesta inicial eran dos comprobaciones, árbol e historial, para que el
informe no mezclara «hay un secreto vivo publicado» con «hay un secreto
invalidado en el historial». La intención era la correcta, pero dos
comprobaciones no alcanzan a hacer esa distinción.

Un secreto que se borra del árbol **sin rotarse** sale bien en el árbol y mal en
el historial, que es el mismo resultado que da uno ya rotado. Los dos casos se
verían iguales en el informe, y el primero sigue abriendo el sistema. Lo que
separa lo vivo de lo invalidado es probarlo, y eso hace C-09c: firma con cada
secreto hallado un token sin roles, a nombre de un usuario inexistente, y
comprueba que el sistema lo rechace por firma inválida.

Así cada control conserva una severidad fija declarada de antemano, en vez de
ajustarla después de ver el resultado. El historial es media porque su riesgo
real lo mide C-09c, que es alta.

## Reglas que se declararon antes de ejecutar

- **Ningún papel contiene el valor hallado.** Solo tipo, ruta, línea o commit y
  los primeros 16 caracteres de la huella SHA-256. El token de C-09c tampoco
  llega al papel.
- **Qué no es un secreto:** referencias a variables, marcadores, valores más
  cortos que el mínimo de su tipo y claves de ejemplo de AWS. Sin estas
  exclusiones, el detector acusaría al propio guion de despliegue.
- **El secreto de desarrollo es público por diseño.** No es hallazgo en C-09a
  ni C-09b, pero C-09c lo prueba fuera del entorno local.
- **Lo que no se puede probar no se presume invalidado.** Si hay un secreto de
  un tipo sin prueba de uso, o la interfaz no responde, C-09c queda *sin
  ejecutar*.
- **Sin repositorio git no se concluye.** El contenedor de la API no lo lleva, y
  ahí los tres quedan *sin ejecutar* con ese motivo.

## Validación en los dos sentidos

18 pruebas nuevas en `cotejo/tests/test_secretos.py`, sobre repositorios git
temporales y un sistema simulado que acepta un único secreto. Cubren: el
repositorio limpio (BIEN), el secreto versionado hoy (MAL en a y b), el
secreto borrado (BIEN en a, MAL en b), el secreto borrado sin rotar (MAL en c,
el caso que justifica el tercer control), las exclusiones, un rechazo por
emisor que no debe tomarse por firma inválida, la interfaz caída y que ningún
resultado contenga el secreto ni el token.

Suite completa: **132 pruebas pasan** (114 antes del cambio).

## Primera ejecución

Contra el repositorio en `eca3475` y el despliegue en AWS, en una carpeta de
prueba fuera del almacén oficial:

| Control | Resultado |
|---|---|
| C-09a | **BIEN**: ningún secreto en 206 archivos; un valor de desarrollo declarado |
| C-09b | **MAL**: `config/.jwt.env` en `be75812`, ya fuera del árbol actual |
| C-09c | **BIEN**: el secreto de H-01 y el de desarrollo, rechazados con 401 por firma inválida |

Se comprobó que ninguno de los tres secretos (el expuesto, el vigente y el de
desarrollo) ni ningún token aparece en los papeles de esa ejecución.

## Otros cambios

- `Contexto` incorpora el emisor y la audiencia de los tokens (de
  `config/deployment.json`), para que en el token de prueba de C-09c lo único
  distinto sea la firma, y la raíz del repositorio (`COTEJO_REPOSITORIO`).
- El informe usa la causa que deduce la propia prueba cuando la trae. La
  genérica de las pruebas de cumplimiento habla de recursos de la nube y no
  describía un secreto versionado.
- Las pruebas de `test_cotejo.py` que fijaban ocho controles ahora toman el
  total del catálogo, salvo una guarda explícita con el número actual.
- Documentación: módulo Cotejo (tabla del catálogo, diseño de C-09, límites del
  sellado y de la numeración de hallazgos), despliegue, guía de uso y contrato
  de la API.
