"""Quién puede abrir cada pantalla.

Es comodidad, no control: evita ofrecer caminos que el servidor va a rechazar.
La autorización la decide el servidor en cada operación, y nada de lo que hay
aquí puede afectarla.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from comun import ui
from rastro_app.contexto import use_app, use_sesion
from rastro_app.estructura import Estructura


@ft.component
def Redirigir(destino: str):
    """Navega al montarse. Es el `<Navigate>` de React Router."""
    app = use_app()
    ft.use_effect(lambda: app.ir(destino, reemplazar=True), [destino])
    return ui.Cargando("Abriendo…")


@ft.component
def Inicio():
    return Redirigir("/panel")


@ft.component
def RutaProtegida():
    app = use_app()
    sesion = use_sesion()
    salida = ft.use_route_outlet()

    if not sesion.autenticado:
        # Se recuerda a dónde iba para devolverlo allí tras entrar: con sesiones
        # que caducan, perder el destino obliga a repetir la navegación varias
        # veces al día.
        app.traspaso["desde"] = app.pagina.route or "/panel"
        return Redirigir("/acceso")
    return Estructura(salida)


@ft.component
def ExigeGrupo(grupos: list[str], pantalla: Callable):
    sesion = use_sesion()
    if sesion.tiene_grupo(*grupos):
        return pantalla()
    return ui.Tarjeta(
        ui.Vacio(
            "Esta sección no corresponde a su rol",
            f"Está reservada a: {', '.join(grupos)}. Si intentara la operación de todos modos, el "
            "servidor la rechazaría y el intento quedaría en la bitácora.",
        )
    )


@ft.component
def ExigePermiso(operacion: str, descripcion: str, pantalla: Callable):
    """Espera a que los permisos lleguen del servidor: antes de eso `puede`
    responde que no a todo, y decidir con eso le diría a quien sí puede que la
    sección no es para él."""
    sesion = use_sesion()
    if not sesion.permisos_cargados:
        return ui.ListaEsqueleto(3)
    if sesion.puede(operacion):
        return pantalla()
    return ui.Tarjeta(
        ui.Vacio(
            "Esta sección no corresponde a su rol",
            f"Para {descripcion} hace falta el permiso «{operacion}». Si intentara la operación de "
            "todos modos, el servidor la rechazaría y el intento quedaría en la bitácora.",
        )
    )


@ft.component
def NoEncontrado():
    app = use_app()
    return ft.Container(
        ui.Tarjeta(
            ui.Vacio(
                "Esa página no existe",
                "Compruebe la dirección o vuelva al panel.",
                ui.Boton("Ir al panel", lambda: app.ir("/panel")),
            )
        ),
        padding=16,
    )
