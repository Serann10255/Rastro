# Módulo `rastro_core` — capa común

Ubicación: `libs/rastro_core/`

## Qué hace

Concentra los cuatro controles críticos del sistema, de modo que se implementen
y se prueben **una sola vez**. Ningún microservicio construye consultas por su
cuenta ni decide por sí mismo si una operación está permitida.

| Archivo | Responsabilidad | Requisito |
|---|---|---|
| `claves.py` | Construcción de claves. Exige el identificador de organización | REQ-06 |
| `repository.py` | Acceso a datos con filtro obligatorio por organización | REQ-06 |
| `state_machine.py` | Catálogo de nueve estados con código y transiciones válidas | REQ-03 |
| `authz.py` | Matriz de autorización de cuatro grupos por dieciséis operaciones | REQ-07 |
| `audit.py` | Encadenamiento por funciones hash y verificador | REQ-08 |
| `storage.py` | Enlaces prefirmados acotados al prefijo de la organización | REQ-05 |
| `security.py` | Emisión y validación de tokens de acceso y de refresco | — |
| `passwords.py` | Derivación y verificación de contraseñas (PBKDF2) | — |
| `maestros.py` | Directorio de usuarios, empresa y catálogos de la organización | REQ-06 |
| `config.py` | Configuración en ejecución, sin identificadores literales | REQ-09 |
| `dominio.py` | Operaciones compartidas; único camino para cargar un envío | REQ-06 |
| `http.py` | Plomería HTTP: errores, identidad, autorización con registro | REQ-07 |
| `models.py`, `ids.py`, `errors.py` | Contratos, identificadores y errores de dominio | REQ-01 |

## Cómo se usa

```python
from rastro_core.http import Contexto, contexto_actual, crear_app
from rastro_core.authz import Operacion

app = crear_app("mi-servicio", "descripcion")

@app.post("/recurso")
async def operacion(ctx: Contexto = Depends(contexto_actual)):
    ctx.exigir(Operacion.ENVIO_CREAR, recurso="recurso/nuevo")
    ...
```

`ctx.exigir` comprueba el grupo y, si lo rechaza, **registra el intento antes de
lanzar el error**. El orden importa: así el rechazo queda en la bitácora aunque
la respuesta se pierda.

## Dependencias y relaciones

- **Depende de**: `fastapi`, `pydantic`, `boto3`, `pyjwt`. Nada del proyecto.
- **Depende de él**: los ocho microservicios, la preparación del entorno local y
  la prueba de integridad de Cotejo, que reutiliza el mismo verificador.

El grafo es deliberadamente plano: la capa común no conoce a los servicios.

## Decisiones

**Una capa común en lugar de acceso a datos por servicio.** Justificada en
[ADR-002](../../decisiones/adr-002-capa-comun-de-acceso-a-datos.md). Reduce la
independencia de despliegue, pero el riesgo que evita (R-05) es mayor que el
acoplamiento que introduce.

**Dos implementaciones del repositorio con la misma interfaz.**
`RepositorioDynamo` y `RepositorioMemoria`. La segunda sostiene las pruebas
unitarias sin infraestructura. Ambas comparten `claves.py`, de modo que el
control de aislamiento no se duplica.

**Descartado: validar el token solo en la puerta de enlace.** Cada servicio lo
vuelve a validar. Cuesta unos milisegundos y hace que el sistema no dependa de
un único control ni del supuesto SU-01, todavía sin confirmar.

**Los estados llevan código numérico en saltos de diez.** El catálogo asigna
10, 20, … 90 y no 1, 2, 3. Los huecos permiten insertar un estado intermedio sin
renumerar lo existente, que es lo que rompería a la vez a todos los sistemas que
ya intercambian archivos con estos códigos. El código y el nombre salen siempre
del mismo catálogo, nunca escritos a mano en un servicio.

**Los estados de cierre se añadieron sin tocar el flujo principal.** `DEVUELTO`
y `CANCELADO` son salidas nuevas; las transiciones existentes quedaron
intactas, y de 98 pruebas solo fallaron dos, por la razón correcta: `DEVUELTO`
es ahora una salida legítima de una incidencia. Véase
[ADR-006](../../decisiones/adr-006-ampliacion-de-alcance-a-tms.md).

**Cancelar y devolver no salen de cualquier estado.** `ORIGENES_CANCELACION` se
limita a los envíos que aún no se han recogido y `ORIGENES_DEVOLUCION` a los que
ya están en la calle. Un envío entregado no se cancela: se devuelve, y eso es
otro envío. Permitir cancelar desde cualquier punto convertiría la máquina de
estados en un campo de texto libre.

**El coste de derivación de contraseñas es configurable por entorno.** A 600 000
iteraciones la suite pasa de segundos a minutos, y una suite lenta es una suite
que nadie ejecuta. `RASTRO_PBKDF2_ITERACIONES` la baja a 1 000 en las pruebas.
Es seguro porque lo que se verifica es el mecanismo —que no se almacena en
claro, que la verificación funciona, que el formato permite migrar— y no el
coste, que es un parámetro. Fuera de las pruebas se queda en el valor por
omisión.

**Escritura condicional en la bitácora.** El documento declara la concurrencia
como limitación aceptada. La implementación la acota con
`attribute_not_exists` y reintento limitado: la segunda escritura recalcula su
eslabón en vez de sobrescribir. Es una mejora sobre lo declarado, no una
garantía de serialización total.

## Comportamiento responsive

No aplica: el módulo no tiene interfaz. La adaptación a pantalla se resuelve
íntegramente en [`interfaz-web`](../interfaz-web/README.md).
