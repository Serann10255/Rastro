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
