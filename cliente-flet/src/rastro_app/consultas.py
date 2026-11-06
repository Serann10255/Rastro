"""Consultas de Rastro que usan varias pantallas, con sus claves de caché.

Las claves están en un solo lugar por la misma razón que en la web: una
invalidación que no acierta con la clave deja una pantalla vieja sin que nadie
lo note.
"""

from __future__ import annotations

from typing import Callable

from comun.datos import Consulta, use_consulta
from rastro_app.contexto import use_app

HORA = 3600
CINCO_MINUTOS = 300

# Cada cuánto se refresca cada vista de rutas. El mapa de la empresa es el que
# más pregunta, porque es el que alguien mira esperando ver moverse un punto.
REFRESCO_SEGUIMIENTO = 10
REFRESCO_RUTA_PROPIA = 30
REFRESCO_PUBLICO = 20

# Toda escritura invalida lo que pudo afectar. La bitácora y el tablero se
# invalidan siempre: cada operación deja un eslabón y mueve un indicador, y una
# vista de auditoría desactualizada es peor que ninguna. Las rutas también: una
# entrega cambia la parada de su ruta.
TRAS_ESCRIBIR = ("envios", "envio", "transiciones", "evidencias", "bitacora", "tablero", "rutas")


def use_catalogo_estados() -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("catalogo", "estados"), app.api.catalogo_estados, vigencia=HORA)


def use_estados_finales() -> Callable[[str], bool]:
    """Qué estados cierran un envío, según el catálogo del servidor. Mientras el
    catálogo no llega, nada se da por cerrado: contar de menos es preferible a
    mostrar como pendiente algo que ya terminó."""
    catalogo = use_catalogo_estados()
    finales = {e["estado"] for e in (catalogo.datos or {}).get("estados", []) if e.get("final")}
    return lambda estado: estado in finales


def use_modulos() -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("catalogo", "modulos"), app.api.modulos, vigencia=CINCO_MINUTOS)


def use_envios(habilitada: bool = True) -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("envios",), app.api.listar_envios, habilitada=habilitada)


def use_maestro(recurso: str, habilitada: bool = True) -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, (recurso,), lambda: app.api.maestros(recurso), habilitada=habilitada)


def use_mensajeros(habilitada: bool = True) -> Consulta:
    app = use_app()
    return use_consulta(
        app.almacen, ("equipo", "mensajeros"), app.api.mensajeros, habilitada=habilitada, vigencia=CINCO_MINUTOS
    )


def use_roles(habilitada: bool = True) -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("roles",), app.api.roles, habilitada=habilitada, vigencia=CINCO_MINUTOS)


def use_catalogo_de_operaciones() -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("catalogo", "operaciones"), app.api.catalogo_de_operaciones, vigencia=HORA)


def use_usuarios(habilitada: bool = True) -> Consulta:
    app = use_app()
    return use_consulta(app.almacen, ("usuarios",), app.api.usuarios, habilitada=habilitada)
