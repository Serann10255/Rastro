# Instalación y uso

Fecha: 2026-09-10 · Versión: 0.1

## Requisitos

| Herramienta | Versión probada | Para qué |
|---|---|---|
| Docker + Compose | 29.6 / v5.3 | Levantar la pila local |
| Python | 3.12 o superior | Pruebas y programa de auditoría |
| AWS CLI | 2.36 | Solo para desplegar en AWS |

---

## Levantar el sistema

```bash
docker compose up -d
```

La primera vez tarda varios minutos: descarga las imágenes y construye la del
proyecto. El servicio `preparar-entorno` crea las tablas con sus índices, el
contenedor de objetos y siembra tres envíos sintéticos. Es idempotente: puede
ejecutarse tantas veces como haga falta sin duplicar recursos ni datos.

Comprobar que arrancó:

```bash
docker compose ps
```

| Componente | Dirección |
|---|---|
| Interfaz de operación | http://localhost:5173 |
| Consulta pública | http://localhost:5173/rastreo.html |
| Puerta de enlace (API) | http://localhost:8080 |
| Consola del almacenamiento | http://localhost:9001 (`local` / `localsecreto`) |

Cada microservicio expone además su documentación interactiva en su puerto
directo, por ejemplo http://localhost:8002/docs para envíos.

### Detener y limpiar

```bash
docker compose down          # detiene y conserva los datos
docker compose down -v       # además borra los volúmenes
```

---

## Recorrer el sistema

### Como despachador

1. Entrar en http://localhost:5173 con `despacho@andes.test` / `Andes.2026`.
2. **Registrar** — crear un envío. El sistema devuelve un identificador UUID;
   ese es el que se le entrega al destinatario.
3. Abrir el envío desde la lista y **asignar un mensajero**
   (`u-andes-cond-1`, Carlos Nieto).

### Como conductor

1. Salir y entrar con `carlos@andes.test` / `Andes.2026`.
2. La lista solo muestra los envíos asignados a ese conductor. El filtro lo
   aplica el servidor, no la pantalla.
3. Abrir el envío y registrar puntos de control. El desplegable solo ofrece los
   estados alcanzables desde el actual.
4. Antes de `ENTREGADO`, cargar la evidencia: el archivo va directamente al
   almacenamiento con un enlace prefirmado que vence en cinco minutos.

Intentar entregar sin evidencia responde con un error: la entrega exige la
prueba que la acredite.

### Como auditor

1. Entrar con `auditor@andes.test` / `Andes.2026`.
2. La bitácora muestra cada operación con actor, acción, recurso, resultado y
   hash. **Verificar integridad** recalcula la cadena completa.
3. El auditor no puede crear ni modificar nada: si lo intenta, recibe 403 y el
   intento queda registrado.

### Como destinatario

Abrir http://localhost:5173/rastreo.html y pegar el identificador del envío. Sin
cuenta y sin token. Se muestra el avance, no la operación de la empresa.

### Comprobar el aislamiento

Entrar con `despacho@sabana.test` / `Sabana.2026` (otra organización) e intentar
abrir un envío de `org-andes` por su identificador: el sistema responde como si
no existiera, y el intento queda en la bitácora de `org-sabana`.

---

## Ejecutar las pruebas

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q
```

No requieren Docker. `pip install -e .` deja `rastro_core` importable desde
cualquier punto del repositorio.

```bash
python -m pytest tests/unit -q      # solo unitarias
python -m pytest tests/e2e -q       # solo extremo a extremo
python -m pytest cotejo/tests -q    # solo el programa de auditoría
```

---

## Ejecutar la auditoría

Con la pila levantada:

```bash
cd cotejo
python -m cotejo ejecutar
```

> Contra el entorno local hay que dar credenciales ficticias y la dirección del
> almacenamiento, porque las pruebas de cumplimiento consultan la interfaz del
> proveedor:
>
> ```bash
> AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=localsecreto \
> COTEJO_ENDPOINT_S3=http://localhost:9000 python -m cotejo ejecutar
> ```

Otros comandos:

```bash
python -m cotejo catalogo                    # ver la matriz de controles
python -m cotejo ejecutar --solo C-05 C-06   # ejecutar controles concretos
python -m cotejo verificar <ejecución>       # recalcular las huellas del almacén
python -m cotejo comparar <ej-a> <ej-b>      # comprobar reproducibilidad
```

Códigos de salida: `0` todo conforme · `1` hay desviaciones · `3` algo no pudo
comprobarse. La distinción importa: no es lo mismo un control que falló que uno
que no se probó.

---

## Configuración

Precedencia: variable de entorno → `config/deployment.json` → valor por omisión.

| Variable | Para qué | Valor local |
|---|---|---|
| `RASTRO_ENTORNO` | `local`, `aws` o `memoria` (pruebas) | `local` |
| `RASTRO_ENDPOINT_DYNAMODB` | Dirección del almacén de datos | `http://dynamodb:8000` |
| `RASTRO_ENDPOINT_S3` | Dirección interna del almacenamiento | `http://almacen:9000` |
| `RASTRO_ENDPOINT_S3_PUBLICO` | Dirección con la que el **dispositivo** lo alcanza | `http://localhost:9000` |
| `RASTRO_JWT_SECRETO` | Secreto del emisor local | valor de desarrollo |
| `RASTRO_VIGENCIA_ENLACE` | Segundos de vigencia del enlace prefirmado | `300` |

**Por qué dos direcciones de almacenamiento.** La firma de un enlace prefirmado
cubre el nombre del servidor. El servicio alcanza el almacenamiento por el
nombre del contenedor, pero el navegador del mensajero no lo resuelve: hay que
firmar contra la dirección que usará el cliente. En AWS ambas coinciden.

---

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| La API responde 404 en rutas que existen | La puerta de enlace resolvió direcciones antiguas tras recrear contenedores. Ya se corrigió con resolución en tiempo de ejecución; si reaparece, `docker compose restart gateway` |
| `Float types are not supported` | El almacén no acepta números con decimales de Python. La capa de repositorio los convierte; si aparece, es que una escritura no pasó por ella |
| El enlace prefirmado da error de nombre | Falta `RASTRO_ENDPOINT_S3_PUBLICO`, o apunta a un nombre que el cliente no resuelve |
| `bloqueo de acceso publico: NO disponible` al preparar | Esperado: el almacenamiento local no implementa esa operación. En AWS sí se aplica |
| Cotejo marca C-01 a C-03 como no ejecutados | Esperado en local: esas capacidades no existen. Se comprueban contra la cuenta desplegada |

---

## Ver también

- [Visión general de la arquitectura](../arquitectura/vision-general.md)
- [Despliegue en AWS](../despliegue/entorno-aws.md)
- [Contratos de la interfaz](../api/contratos.md)
