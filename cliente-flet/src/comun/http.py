"""Peticiones HTTP y errores tipados, comunes a Rastro y a Cotejo.

Las pantallas no inspeccionan cadenas de texto para saber qué falló: reciben un
`ErrorApi` con el código de dominio (`NO_AUTORIZADO`, `NO_ENCONTRADO`...). Es la
misma traducción que hace la interfaz web en `web/src/api/cliente.ts`, con los
mismos códigos y los mismos mensajes, para que un error se lea igual en las dos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

# Un cliente por proceso. httpx mantiene las conexiones abiertas entre
# peticiones, que en una red móvil ahorra el saludo TLS de cada consulta.
_cliente: httpx.AsyncClient | None = None


def cliente() -> httpx.AsyncClient:
    global _cliente
    if _cliente is None:
        _cliente = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0))
    return _cliente


@dataclass
class ErrorApi(Exception):
    estado: int
    codigo: str
    mensaje: str
    detalle: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.mensaje

    @property
    def transiciones_permitidas(self) -> list[str]:
        permitidas = self.detalle.get("permitidas")
        return list(permitidas) if isinstance(permitidas, list) else []


def codigo_por_estado(estado: int) -> str:
    return {
        401: "NO_AUTENTICADO",
        403: "NO_AUTORIZADO",
        404: "NO_ENCONTRADO",
        409: "CONFLICTO",
        400: "SOLICITUD_INVALIDA",
        422: "SOLICITUD_INVALIDA",
    }.get(estado, "ERROR_INTERNO")


def mensaje_por_estado(estado: int, detalle: Any) -> str:
    if estado == 422:
        if isinstance(detalle, list) and detalle:
            # FastAPI devuelve la validación como lista; se nombra el primer
            # campo para que el usuario sepa cuál corregir.
            primero = detalle[0] if isinstance(detalle[0], dict) else {}
            ubicacion = primero.get("loc") or []
            campo = ubicacion[-1] if ubicacion else ""
            return f"Revise el campo «{campo}»: {primero.get('msg', '')}" if campo else "Datos no válidos."
        return "Los datos enviados no son válidos."
    if isinstance(detalle, str):
        return detalle
    return f"El servicio respondió con código {estado}."


SIN_CONEXION = "Sin conexión. Compruebe la red e inténtelo de nuevo."


async def enviar(
    metodo: str,
    url: str,
    *,
    cuerpo: Any = None,
    parametros: dict[str, Any] | None = None,
    cabeceras: dict[str, str] | None = None,
    contenido: bytes | None = None,
) -> httpx.Response:
    """Envía la petición. Un fallo de red se convierte en `SIN_CONEXION`: la
    condición real del mensajero es conectividad intermitente, y un fallo de red
    no es un fallo del sistema."""
    consulta = {k: v for k, v in (parametros or {}).items() if v is not None and v != ""}
    try:
        return await cliente().request(
            metodo,
            url,
            json=cuerpo if contenido is None else None,
            content=contenido,
            params=consulta or None,
            headers=cabeceras,
        )
    except httpx.HTTPError as error:
        raise ErrorApi(0, "SIN_CONEXION", SIN_CONEXION) from error


def interpretar(respuesta: httpx.Response) -> Any:
    """El cuerpo de la respuesta, o un `ErrorApi` si no fue satisfactoria."""
    try:
        datos = respuesta.json() if respuesta.content else None
    except ValueError:
        datos = None

    if respuesta.is_success:
        return datos

    cuerpo = datos if isinstance(datos, dict) else {}
    raise ErrorApi(
        respuesta.status_code,
        cuerpo.get("codigo") or codigo_por_estado(respuesta.status_code),
        cuerpo.get("mensaje") or mensaje_por_estado(respuesta.status_code, cuerpo.get("detail")),
        cuerpo.get("detalle") or {},
    )


def mensaje_de_error(error: BaseException) -> str:
    """Lo que se le dice a la persona. Cada aplicación puede afinarlo con su
    vocabulario; esto es lo mínimo: el mensaje del servidor, o el del fallo de
    la interfaz tal cual, sin disfrazarlo de error del servidor."""
    if isinstance(error, ErrorApi):
        return error.mensaje
    return str(error) or "Ocurrió un error inesperado."
