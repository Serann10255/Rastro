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
from rastro_core.rutas import ubicacion_publica

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


@app.get(
    "/publico/envios/{envio_id}/ubicacion",
    tags=["publico"],
    summary="Donde va el envio mientras esta en reparto",
)
async def consultar_ubicacion_publica(envio_id: str = Path(pattern=PATRON_UUID)) -> dict:
    """La ultima posicion del vehiculo que lleva el envio, si la hay.

    Es una ruta aparte de la consulta del historico, y no un campo mas, por dos
    razones. La pantalla del destinatario la pregunta cada pocos segundos y el
    historico no cambia a ese ritmo. Y la consulta del historico tiene un
    contrato que otros ya leen -el programa de auditoria entre ellos-: anadirle
    la ubicacion de una persona cambiaria lo que esa vista promete no mostrar.

    Lo que se devuelve lo decide ``rutas.ubicacion_publica``: posicion
    redondeada y antiguedad, solo mientras el envio esta en reparto dentro de
    una ruta abierta y la posicion es reciente. Ni quien conduce ni sus otras
    paradas.
    """
    repositorio = obtener_repositorio()
    maestro = repositorio.maestro_publico(envio_id)
    if maestro is None:
        raise NoEncontradoError("No existe un envio con ese identificador.")

    ruta = None
    if maestro.get("ruta_id"):
        try:
            ruta = repositorio.obtener_ruta(maestro["org_id"], maestro["ruta_id"])
        except NoEncontradoError:
            ruta = None

    return {**ubicacion_publica(maestro, ruta), "consultado_en": marca_tiempo()}
