# Instalación y uso

Fecha: 2026-09-10 · Versión: 0.3

## Requisitos

| Herramienta | Versión probada | Para qué |
|---|---|---|
| Docker + Compose | 29.6 / v5.3 | Levantar la pila local |
| Python | 3.12 o superior | Pruebas y programa de auditoría |
| Node | 20 o superior | Solo para desarrollar las interfaces |
| AWS CLI | 2.36 | Solo para desplegar en AWS |

Con Docker basta para levantar todo: las interfaces se compilan dentro de su
imagen. Node solo hace falta para iterar sobre ellas con recarga en caliente.

---

## Levantar el sistema

```bash
docker compose up -d
```

La primera vez tarda varios minutos: descarga las imágenes y construye la del
proyecto. El servicio `preparar-entorno` crea las tres tablas con sus índices y el
contenedor de objetos, deriva las contraseñas de la semilla, siembra dos empresas
con sus diez usuarios y sus catálogos, y genera veinte envíos con recorridos
variados. Es idempotente: puede ejecutarse tantas veces como haga falta sin
duplicar recursos ni datos.

Comprobar que arrancó:

```bash
docker compose ps
```

| Componente | Dirección |
|---|---|
| Rastro — interfaz de operación | http://localhost:5173 |
| Rastro — consulta pública | http://localhost:5173/rastreo |
| Rastro — API | http://localhost:8080 |
| Cotejo — interfaz de auditoría | http://localhost:5175 |
| Cotejo — API | http://localhost:8007 |
| Consola del almacenamiento | http://localhost:9001 (`local` / `localsecreto`) |

El recorrido de cada aplicación está en
[cómo se usa cada app](../despliegue/como-usar-cada-app.md).

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

1. Entrar en http://localhost:5173 con `despacho@andes.test` / `Andes.Despacho.2026`.
2. **Registrar** — crear un envío. El sistema devuelve un identificador UUID;
   ese es el que se le entrega al destinatario.
3. Abrir el envío desde la lista y **asignar un mensajero**: los conductores de
   la empresa aparecen como opciones, no hay que saberse su identificador.
4. Marcar varias órdenes en el listado y pulsar **Guías** para imprimir sus
   etiquetas con código de barras, o **Exportar** para descargar el CSV.
5. Para un lote grande, **Nueva orden → Carga masiva**: se pega un CSV, la
   pantalla muestra qué filas se aceptan antes de enviar nada, y una fila mala
   no impide registrar las demás.

### Como conductor

1. Salir y entrar con `carlos@andes.test` / `Andes.Carlos.2026`.
2. La lista solo muestra los envíos asignados a ese conductor. El filtro lo
   aplica el servidor, no la pantalla.
3. Abrir el envío y registrar puntos de control. Solo aparecen como botones los
   estados alcanzables desde el actual; el servidor los vuelve a comprobar.
4. Antes de `ENTREGADO`, cargar la evidencia: el archivo va directamente al
   almacenamiento con un enlace prefirmado que vence en cinco minutos.

Intentar entregar sin evidencia responde con un error: la entrega exige la
prueba que la acredite.

### Como auditor

1. Entrar con `auditor@andes.test` / `Andes.Auditor.2026`.
2. La bitácora muestra cada operación con actor, acción, recurso, resultado y
   hash. **Verificar integridad** recalcula la cadena completa.
3. El auditor no puede crear ni modificar nada: si lo intenta, recibe 403 y el
   intento queda registrado.

### Como destinatario

Abrir http://localhost:5173/rastreo y pegar el identificador del envío. Sin
cuenta y sin token. Se muestra el avance, no la operación de la empresa.

### Como administrador

1. Entrar con `admin@andes.test` / `Andes.Admin.2026`.
2. **Administración** — crear un usuario, cambiarle el rol o desactivarlo. El
   sistema impide quedarse sin administradores y que uno se desactive a sí mismo.
3. **Maestros** — tiendas, clientes y transportistas. Eliminar desactiva; no
   borra, porque los envíos históricos apuntan a ellos.

### Como auditor, en Cotejo

Abrir http://localhost:5175 y entrar con la misma cuenta de auditor. Ejecutar el
catálogo, abrir un papel de trabajo y comprobar que su huella coincide.

### Comprobar el aislamiento

Entrar con `despacho@sabana.test` / `Sabana.Despacho.2026` (otra organización) e intentar
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

### Comprobar los tipos de las interfaces

```bash
cd web && npm install && npm run typecheck && npm run build
cd ../cotejo/web && npm install && npm run typecheck && npm run build
```

Las dos comparten el sistema de diseño de `design/`, que está fuera de cada
aplicación: si `npm run build` falla al resolver `@design/...`, falta el alias en
`vite.config.ts` o el permiso `fs.allow`. Detalle en
[sistema-de-diseno](../modulos/sistema-de-diseno/README.md).

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
| `COTEJO_URL_API` | Sistema que Cotejo audita | `http://gateway:80` |
| `COTEJO_DIR_PAPELES` | Dónde guarda los papeles de trabajo | `/papeles` (volumen) |
| `COTEJO_CLAVES` | Claves de los usuarios de prueba, JSON de correo a clave | las de la semilla montada |
| `COTEJO_TABLA_MAESTROS` | Directorio del que Cotejo descubre contra quién ejecutar | `rastro-maestros` |
| `RASTRO_ENDPOINT_DYNAMODB` | Dirección del almacén de datos | `http://dynamodb:8000` |
| `RASTRO_ENDPOINT_S3` | Dirección interna del almacenamiento | `http://almacen:9000` |
| `RASTRO_ENDPOINT_S3_PUBLICO` | Dirección con la que el **dispositivo** lo alcanza | `http://localhost:9000` |
| `RASTRO_JWT_SECRETO` | Secreto de firma de los tokens | valor de desarrollo |
| `RASTRO_PBKDF2_ITERACIONES` | Coste de derivación de contraseñas | `600000` (las pruebas lo bajan a `1000`) |
| `RASTRO_TABLA_MAESTROS` | Tabla de empresa, usuarios y catálogos | `rastro-maestros` |
| `RASTRO_VIGENCIA_ENLACE` | Segundos de vigencia del enlace prefirmado | `300` |

**El secreto de firma es crítico en AWS.** Quien lo conozca puede firmar un
token de administrador de cualquier organización. Por eso `30-funciones.sh` se
niega a desplegar si `RASTRO_JWT_SECRETO` no está definido o tiene menos de 32
caracteres, en lugar de caer al valor de desarrollo que está en el repositorio.

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
| El puerto 5175 está ocupado | Otro proyecto lo usa. Cambie el mapeo en `docker-compose.yml`; nada del sistema depende de ese número |
| La pantalla de operaciones aparece vacía | Falta sembrar los módulos: `docker compose run --rm preparar-entorno`. Es idempotente y respeta los que un administrador haya apagado |
| Un módulo muestra un icono genérico | Su campo `icono` no coincide con ningún trazado del sistema de diseño. Se dibuja el genérico a propósito: un hueco parecería una pantalla rota |
| Cotejo reporta C-05 y C-06 no ejecutados | No encontró credenciales de los roles que necesita. Declare `COTEJO_CLAVES` o compruebe que `./seed` esté montado en el contenedor |
| La interfaz muestra datos viejos tras una escritura | Recargue. Si persiste, es un fallo de invalidación en `web/src/api/consultas.ts` |
| `npm run dev` devuelve HTML donde espera JSON | Falta el prefijo de esa ruta en el proxy de `web/vite.config.ts`. La lista debe coincidir con la que reparte `gateway/nginx.conf` |
| Las pruebas tardan minutos | Falta `RASTRO_PBKDF2_ITERACIONES` bajo. `tests/conftest.py` lo fija; ejecutar un archivo suelto sin ese ajuste deriva a coste real |
| Un usuario no puede entrar y la clave es correcta | Puede estar desactivado. La respuesta es deliberadamente la misma; el motivo real está en la bitácora |

---

## Ver también

- [Visión general de la arquitectura](../arquitectura/vision-general.md)
- [Despliegue en AWS](../despliegue/entorno-aws.md)
- [Contratos de la interfaz](../api/contratos.md)
