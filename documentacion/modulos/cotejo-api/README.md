# Módulo `cotejo-api` — interfaz HTTP del programa de auditoría

Ubicación: `cotejo/api/` · Puerto local: 8007

## Qué hace

Expone el catálogo, la ejecución del programa y los papeles de trabajo, para que
el auditor pueda operar sin línea de comandos.

| Operación | Para qué |
|---|---|
| `GET /salud` | Estado del programa y sistema auditado. Sin autenticación |
| `GET /catalogo` | Matriz de controles y hallazgos permanentes |
| `GET /ejecuciones` | Ejecuciones almacenadas, de la más reciente a la más antigua |
| `POST /ejecuciones` | Recorre el catálogo completo. En local responde `201` con el resultado; en AWS, `202` y la ejecución sigue aparte |
| `GET /ejecuciones/{id}/estado` | Si una ejecución encargada sigue en curso, terminó o falló (con su motivo) |
| `GET /ejecuciones/{id}` | Cobertura, resultado por control y hallazgos |
| `GET /ejecuciones/{id}/informe.txt` | Informe en texto plano |
| `GET /ejecuciones/{id}/papeles/{control}` | Evidencia literal, con la huella recalculada |
| `POST /ejecuciones/{id}/verificacion` | Recalcula todas las huellas del almacén |
| `GET /comparacion?a=&b=` | Compara la clasificación de dos ejecuciones |

## Decisiones

**Acceso restringido al rol auditor.** El almacén de papeles de trabajo concentra
información sobre las debilidades del sistema auditado, y su divulgación
facilitaría un ataque. Se valida el mismo token que emite el proveedor de
identidad de Rastro y se exige el grupo `auditor`. Un despachador con token
válido recibe 403.

**No hay una segunda implementación del ejecutor.** Esta interfaz llama a las
mismas funciones que la línea de comandos. Una copia paralela podría divergir, y
entonces el resultado dependería de por dónde se ejecutó, que es justo lo que un
programa de auditoría no puede permitirse.

**La línea de comandos sigue siendo el camino principal.** Es la que se versiona
y la que ejecuta un evaluador independiente. Esta interfaz existe para leer y
comparar con comodidad, no para sustituirla.

**La huella se recalcula al leer un papel, no se copia del índice.** Así abrir el
papel sirve además como comprobación de que nadie lo editó.

**Los identificadores se validan contra recorrido de directorios.** Un
identificador con `/`, `\` o `..` se rechaza antes de tocar el sistema de
archivos.

**En AWS la ejecución se encarga y se espera** (ADR-015). API Gateway corta a
los 30 segundos y una revisión completa puede tardar más. Con un lanzador
configurado —lo fija `aws.py`, el punto de entrada de la función—, `POST
/ejecuciones` anota el estado «en curso» en `papeles/_estados/`, invoca la misma
función de forma asíncrona y responde `202`. La invocación ejecuta el mismo
`completar_ejecucion` que la petición local y anota «lista» o «fallida». El
estado va fuera de la carpeta de la ejecución porque esa carpeta es evidencia y
se verifica por su huella.

**En AWS los papeles viven en S3.** El disco de la función no dura: `aws.py` trae
del contenedor de papeles lo que falte antes de cada petición y sube después lo
escrito. Cubierto por `cotejo/tests/test_api_en_aws.py`, con S3 y Lambda
simulados.

## Dependencias y relaciones

- **Depende de**: el paquete `cotejo` (ejecutor, papeles, informe) y de
  `rastro_core.security` para validar el token.
- **Audita a**: Rastro, a través de la puerta de enlace y de la interfaz de
  configuración del proveedor.
- **Lo consume**: [`cotejo-web`](../cotejo-web/README.md).

**Dependencia declarada.** Cotejo no mantiene su propio directorio de usuarios:
depende del proveedor de identidad del sistema que audita. Es defendible —el
auditor es un usuario de la organización auditada— pero conviene enunciarlo: si
ese proveedor cayera, la interfaz de auditoría no sería accesible. La línea de
comandos no tiene esa dependencia.

## Comportamiento responsive

No aplica: el servicio no tiene interfaz.
