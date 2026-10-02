# ADR-012 · El sitio se sirve por HTTPS a través de API Gateway

Fecha: 2026-10-02 · Estado: aceptada · Afecta a la secuencia de despliegue en AWS
(`deploy/aws/65-sitio-https.sh`) y a la regla CORS del contenedor de evidencias

## Contexto

El sitio de Rastro se publica en el alojamiento estático de S3, que **solo
responde por HTTP**. Hasta ahora se aceptaba como limitación conocida: la API sí
va por HTTPS, de modo que el token no viaja en claro, pero el propio sitio podía
alterarse en tránsito y el navegador lo marcaba como «No seguro». Había además
una segunda limitación: los enlaces directos (`/rastreo`, `/envios/<id>`)
respondían 404 aunque la página se mostrara bien.

La documentación de despliegue proponía CloudFront para las dos cosas y lo
dejaba fuera solo para no añadir un componente más. Al intentarlo el
2026-10-02, el laboratorio lo niega por completo: la sesión no puede ni listar
distribuciones.

```
AccessDenied ... is not authorized to perform: cloudfront:ListDistributions
because no identity-based policy allows the cloudfront:ListDistributions action
```

Se registra como restricción **RE-05** del entorno.

## Decisión

**Una segunda interfaz HTTP de API Gateway, `rastro-sitio`, sirve los archivos del
sitio por HTTPS.** API Gateway ya está en uso para la API, de modo que no entra
ningún servicio nuevo, y termina TLS con el certificado que Amazon emite y renueva
para `*.execute-api.us-east-1.amazonaws.com`.

| Ruta | Destino en el contenedor | Para qué |
|---|---|---|
| `GET /assets/{proxy+}` | `/assets/{proxy}` | Recursos compilados, con su caché de un año |
| `GET /<archivo>` | `/<archivo>` | Una ruta por cada archivo suelto de `web/dist` (`configuracion.json`, `icono.svg`) |
| `GET /` y `GET /{proxy+}` | `/index.html` | Todo lo demás es una ruta de la aplicación: recibe el índice **con estado 200** |

Los archivos se leen del **punto REST** del contenedor
(`https://<contenedor>.s3.us-east-1.amazonaws.com`) y no del de sitio web, que
solo habla HTTP. Así ningún tramo viaja en claro. El nombre del contenedor no
lleva puntos, de modo que lo cubre el certificado comodín de S3.

S3 responde **403** a un objeto que no existe, porque la política concede leer y
no listar. La integración lo traduce a **404**: un recurso que falta se ve como
lo que es.

### Por qué una interfaz aparte

Las rutas de la aplicación y las de la API coinciden: `/envios/<id>` es a la vez
una pantalla y un recurso. En una sola interfaz, la ruta comodín del sitio y las
de la API competirían por los mismos caminos.

### Por qué los archivos sueltos se leen del compilado

Si se enumeraran a mano, uno nuevo que faltara recibiría el índice en su lugar,
con estado 200, y el fallo pasaría desapercibido. La etapa recorre `web/dist` y
crea una ruta por archivo.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **CloudFront** delante del contenedor | Es la solución habitual y la que proponía la documentación. Impedida por el laboratorio (RE-05) |
| **Punto REST de S3 directamente** (`https://<contenedor>.s3.amazonaws.com/index.html`) | Tiene HTTPS, pero no sabe de aplicaciones de una sola página: la raíz no sirve el índice y un enlace directo responde con un error XML |
| **Función Lambda que sirva los archivos** | Funciona, pero es código propio que mantener para algo que la integración de paso hace sin código |
| **Certificado propio** (ACM o Let's Encrypt) | Exige un dominio propio, que el proyecto no tiene. ACM sin dominio no emite nada |
| **Instancia EC2 con un servidor web** | Se detiene entre sesiones del laboratorio: el sitio dejaría de estar disponible justo cuando nadie está mirando |

## Consecuencias

- **El sitio responde por HTTPS con un certificado válido**, emitido y renovado
  por Amazon, sin nada que mantener.
- **Los enlaces directos responden 200.** Desaparece la segunda limitación del
  sitio de S3.
- **El sitio de S3 sigue respondiendo por HTTP** en su dirección de siempre. No
  se retira para no romper enlaces ya compartidos; la dirección que se comunica
  es la HTTPS.
- **La regla CORS del contenedor de evidencias admite los dos orígenes.** Sin
  ello la consulta funcionaría por HTTPS y la carga de evidencias fallaría en el
  navegador del mensajero. La regla vive en `comun.sh` (`aplicar_cors_evidencias`)
  y busca la interfaz del sitio por nombre, de modo que `10-datos.sh` y
  `65-sitio-https.sh` dejan la misma regla en cualquier orden.
- **REQ-09 se mantiene.** Ningún identificador se escribe a mano: el contenedor se
  deriva de la cuenta y el identificador de la interfaz queda en
  `config/.sitio.env` y en `config/deployment.json` (`url_sitio`).
- **Coste.** Una petición por archivo al pago por uso de API Gateway; con el
  volumen de un entorno de pruebas es marginal, y no hay cargo fijo.
- **Límites aceptados.** Solo se enrutan peticiones `GET`: una petición `HEAD`
  responde 404. API Gateway no comprime las respuestas; el sitio pesa poco y no
  compensa añadir otra pieza para ello.
- **La dirección es la del proveedor**, `https://<id>.execute-api.us-east-1.amazonaws.com`.
  Un dominio propio exigiría un nombre de dominio y un certificado de ACM, que
  quedan fuera del alcance.
