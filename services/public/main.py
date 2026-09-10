"""Microservicio de consulta publica (REQ-04).

El destinatario no tiene cuenta: consulta el avance de su envio con el
identificador que le entregaron. Es el unico punto del sistema que responde sin
token, y por eso concentra dos controles.

El primero es el identificador aleatorio: con numeracion secuencial, cualquiera
podria recorrer identificadores contiguos y obtener los envios de toda la
empresa, que es la referencia directa insegura a objetos de A01:2021 (OWASP
Foundation, 2021). El segundo es la vista reducida: se devuelve el avance del
envio, no la operacion de la empresa ni la identidad de sus empleados.
"""

from __future__ import annotations

from fastapi import Path

from rastro_core.errors import NoEncontradoError
from rastro_core.http import crear_app, obtener_repositorio
from rastro_core.ids import marca_tiempo
from rastro_core.models import Destinatario, Direccion, Envio, Evento

app = crear_app(
    "rastro-publico",
    "Consulta del historico de un envio por su identificador, sin autenticacion.",
)

#: Un UUID en su forma canonica. Se valida el formato antes de consultar para
#: no convertir el punto publico en un sondeo barato del almacenamiento.
PATRON_UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


@app.get(
    "/publico/envios/{envio_id}",
    tags=["publico"],
    summary="Consultar el avance de un envio por su identificador",
)
async def consultar_envio_publico(envio_id: str = Path(pattern=PATRON_UUID)) -> dict:
    """Devuelve el registro maestro y sus eventos en orden cronologico."""
    maestro, eventos = obtener_repositorio().historico_publico(envio_id)
    if maestro is None:
        raise NoEncontradoError("No existe un envio con ese identificador.")

    envio = Envio(
        **{
            **maestro,
            "origen": Direccion(**maestro["origen"]),
            "destino": Direccion(**maestro["destino"]),
            "destinatario": Destinatario(**maestro["destinatario"]),
        }
    )

    return {
        "envio": envio.vista_publica(),
        "eventos": [Evento(**e).vista_publica() for e in eventos],
        "consultado_en": marca_tiempo(),
    }
