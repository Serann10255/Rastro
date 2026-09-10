# Servicio `evidence` — evidencias de entrega

Ubicación: `services/evidence/` · Puerto local: 8004 · Requisito: REQ-05

## Qué hace

Emite enlaces prefirmados de vigencia limitada, confirma que la carga se
completó y entrega enlaces de descarga a los roles autorizados.

| Operación | Grupos |
|---|---|
| `POST /envios/{id}/evidencias` | conductor |
| `POST /envios/{id}/evidencias/{ev}/confirmacion` | conductor |
| `GET /envios/{id}/evidencias` | administrador, despachador, auditor |

## Flujo

1. El conductor pide un enlace. El servicio lo emite acotado al prefijo de su
   organización, con cifrado impuesto en los parámetros de la firma.
2. **El dispositivo carga el archivo directamente contra el almacenamiento.** No
   pasa por el servicio: ni lo recibe, ni lo reenvía, ni lo almacena en memoria.
3. El conductor confirma. El servicio **consulta el objeto en el almacenamiento**
   y solo entonces lo asocia al envío.

## Decisiones

**La confirmación no cree al cliente.** Comprobar el objeto es la diferencia
entre registrar que alguien dijo haber cargado una foto y acreditar que la foto
está guardada y cifrada.

**El cifrado se impone en la firma.** Un cliente que intente cargar sin la
cabecera de cifrado obtiene una firma inválida. Además, una política del
contenedor rechaza toda carga sin cifrar: la primera medida cubre al cliente
distraído, la segunda al deliberado.

**El conductor no puede descargar.** Carga la prueba de entrega; consultarla
corresponde a otros roles.

**Una clave fuera del prefijo de la organización responde *no encontrado*, nunca
*no autorizado*.** Responder 403 confirmaría que el objeto existe.

**Dos clientes de almacenamiento.** Uno para las operaciones del servicio y otro
para firmar enlaces. La firma cubre el nombre del servidor: el servicio alcanza
el almacenamiento por su dirección interna, pero el navegador del mensajero no la
resuelve. En AWS ambas coinciden y es el mismo objeto.

## Dependencias y relaciones

- **Depende de**: `rastro_core.storage` y del almacenamiento de objetos.
- **Depende de él**: `tracking`, que no acepta `ENTREGADO` sin evidencia
  confirmada.

## Comportamiento responsive

No aplica al servicio. El formulario de captura vive en
[`interfaz-web`](../interfaz-web/README.md), que usa `capture="environment"` para
abrir la cámara trasera en móvil.
