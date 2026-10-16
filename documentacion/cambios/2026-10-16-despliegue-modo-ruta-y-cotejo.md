# Cambios · 2026-10-16 · Despliegue del modo ruta y de Cotejo en AWS

Con la sesión del laboratorio abierta, se desplegó en la cuenta 484948252891 el
[modo ruta](2026-10-16-modo-ruta.md) y, por primera vez, **Cotejo entero**: su
API como función y su interfaz por HTTPS, para mostrarlo en la sustentación
desde cualquier equipo. La decisión y lo que cuesta están en el
[ADR-015](../decisiones/adr-015-cotejo-desplegado-en-aws.md).

## Direcciones

| Qué | Dirección |
|---|---|
| Rastro (operación y consulta pública) | https://td70a5indc.execute-api.us-east-1.amazonaws.com |
| API de Rastro | https://l7ymvbqqc4.execute-api.us-east-1.amazonaws.com |
| Cotejo (interfaz de auditoría) | https://osgo93nahb.execute-api.us-east-1.amazonaws.com |
| API de Cotejo | https://2amcyjn5b8.execute-api.us-east-1.amazonaws.com |

## Qué se hizo

1. **El secreto de firma se recuperó del despliegue**, no se generó uno nuevo.
   `config/.jwt.env` no estaba en este equipo (no viaja con el repositorio) y,
   sin él, `30-funciones.sh` no despliega. Se leyó de la función `rastro-auth`,
   se comprobó que `rastro-tracking` tenía el mismo y se escribió en
   `config/.jwt.env` sin imprimirlo. Así las sesiones abiertas siguieron
   valiendo.
2. **Secuencia completa de Rastro** (`desplegar.sh`, 8 min 22 s): retención por
   TTL del recorrido activada, módulos `entregas` y `seguimiento` sembrados en
   las dos empresas, las ocho funciones actualizadas, las siete rutas nuevas
   creadas, sitio publicado por HTTPS. `95-verificar.sh`: todo conforme.
3. **Cotejo en AWS** (etapas nuevas):
   - `55-cotejo-api.sh` — contenedor `rastro-cotejo-papeles-<cuenta>` (privado,
     versionado, cifrado), función `rastro-cotejo` (300 s, 1 GB, invocación
     asíncrona sin reintentos) e interfaz `rastro-cotejo-api`.
   - `60-sitios.sh` con `RASTRO_PUBLICAR_COTEJO=si` — ahora lee la dirección de
     la API de Cotejo de `config/.cotejo.env`.
   - `67-cotejo-sitio-https.sh` — interfaz `rastro-cotejo-sitio`, el mismo
     arreglo HTTPS que el ADR-012.
   - `desplegar.sh` incluye las dos etapas; sin la variable informan y siguen.
   - `95-verificar.sh` comprueba Cotejo si está desplegado.
4. **Cambios en Cotejo para correr en una función** — `cotejo/api/aws.py` (papeles
   en S3, autoinvocación asíncrona), ejecución diferida en `cotejo/api/main.py`
   (`POST /ejecuciones` → `202`, `GET /ejecuciones/{id}/estado`) y la interfaz
   espera la revisión. En local todo sigue igual.

## Verificación contra la cuenta

| Comprobación | Resultado |
|---|---|
| Permisos efectivos del conductor tras el despliegue | Incluyen `ruta:operar` sin haber tocado su rol guardado |
| Salir a ruta (conductora Camila, dos guías) | 201; las dos en `EN_REPARTO`; una transición registrada |
| Nueve posiciones reportadas | 200; señal `en_linea`; el administrador la ve con su recorrido |
| Consulta pública en el navegador, a 360 px | Mapa con teselas de OpenStreetMap; **el punto se movió solo** al llegar posiciones nuevas; sin desbordamiento horizontal |
| Entrega con foto | Subida a S3 con el enlace prefirmado (200), confirmada con cifrado `aws:kms`; parada en `ENTREGADO`; la vista pública de ese envío se oculta |
| Cierre de la ruta | `FINALIZADA`, cierre `manual`; una posición tardía responde 409; la vista pública pasa a `sin_ruta_activa` |
| Revisión de Cotejo encargada por la API | `202`, «lista» a los 15 s; **8 conformes, 0 desviados, 3 no ejecutados** (C-09a/b/c: sin repositorio git en la función) |
| Integridad del almacén de papeles tras pasar por S3 | Íntegro, sin discrepancias de huella |
| Interfaz de Cotejo por HTTPS | Carga, lee su configuración y muestra el sistema auditado (consulta `/salud` sin errores de CORS) |
| CORS desde el sitio de Cotejo | Preflight a la API de Cotejo con `Authorization` y a `/auth/token` de Rastro: permitidos |

Salida literal de cada etapa en `evidencias-despliegue/20261016T16*`. Ningún
archivo de evidencia contiene el secreto de firma ni claves (comprobado con
`grep`).

## Actualización: los controles de secretos (C-09) en AWS

Al revisar la interfaz de Cotejo en AWS, los tres C-09 salían **SIN REVISAR**
con «git no esta instalado en esta maquina»: la primera versión de la función
era un paquete .zip, y el entorno de Python de Lambda no trae git ni hay
repositorio que revisar. Se corrigió el mismo día:

- `cotejo/Dockerfile.lambda` — la función pasa a ser **imagen de contenedor**
  con `git-core` sobre la imagen base de Lambda para Python 3.12. Se sube al
  repositorio `rastro-cotejo` de ECR, con análisis de vulnerabilidades al subir.
- `cotejo/api/aws.py` — antes de cada revisión **clona el repositorio
  publicado** (`https://github.com/Serann10255/Rastro`), desnudo, con todas las
  ramas y de cero cada vez; tarda unos 7 s.
- `cotejo/cotejo/pruebas/secretos.py` — C-09a y C-09b anotan en el papel el
  `remoto` de la copia revisada.
- `55-cotejo-api.sh` — construye y sube la imagen; como una función no cambia de
  .zip a imagen, retira la anterior y la crea de nuevo (los papeles están en S3 y
  no se pierden).
- `cotejo/tests/test_api_en_aws.py` — tres pruebas más: el clon trae todas las
  ramas y el papel dice de dónde salió; cada revisión ve lo último publicado; si
  el clon falla, C-09 no revisa otra carpeta por error.

Antes de desplegar se construyó la imagen en local y, dentro de ella, se clonó
el repositorio publicado y se corrieron las revisiones de árbol e historial.

Revisión en AWS tras el cambio (`20261016T164718872Z-3e6a7d`):

| Control | Resultado |
|---|---|
| C-01 a C-08 | CONFORME |
| C-09a | CONFORME — ningún secreto en el árbol publicado (commit `ead33e3`, 311 archivos); solo el valor de desarrollo declarado |
| C-09b | **DESVIADO** — el secreto de firma de `config/.jwt.env` en el commit `be75812` sigue en el historial publicado: es el hallazgo **H-01** |
| C-09c | CONFORME — los dos secretos de firma hallados son rechazados por firma inválida: el de H-01 se rotó |

**11 de 11 ejecutados: 10 conformes, 1 desviado.** El desviado es correcto: el
historial publicado todavía contiene el secreto. Quitarlo exigiría reescribir el
historial y forzar la publicación en GitHub, una decisión del equipo que no se
tomó aquí. El almacén de papeles verificó íntegro y los registros de la función
no contienen el secreto.

## Qué no se verificó

- **Las pantallas con sesión en el navegador** (Entregas, Seguimiento, la consola
  de Cotejo). El asistente no escribe contraseñas en sitios que no sean
  `localhost`; esas pantallas se probaron en la pila local y sus llamadas, contra
  AWS por la API. Falta recorrerlas a mano en el despliegue.
- **El GPS de un teléfono real.**

## Datos que quedaron cambiados en la cuenta

La prueba usó a la conductora **Camila** (`camila@andes.test`) para no gastar los
envíos de Carlos, que son los de la demostración: uno de sus envíos quedó
`ENTREGADO` con una foto de prueba y otro en `EN_REPARTO` sin ruta. Las cuentas,
roles y demás envíos no se tocaron. En la bitácora de `org-andes` constan el
inicio y el cierre de esa ruta y las consultas de seguimiento.
