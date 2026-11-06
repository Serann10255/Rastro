"""Lo que comparten todas las pantallas de Cotejo: la aplicación de la página
abierta, la sesión del auditor y el estado de la consola.

Es la misma forma que en Rastro (`rastro_app/contexto.py`) pero más corta:
Cotejo tiene un solo rol, el de auditor, y cuatro pantallas.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import flet as ft

from comun.datos import Almacen
from comun.http import ErrorApi
from cotejo_app.api import ClienteCotejo


@dataclass(eq=False)
class Aplicacion:
    pagina: ft.Page
    api: ClienteCotejo
    preferencias: ft.SharedPreferences
    origen_configuracion: str
    almacen: Almacen = field(default_factory=Almacen)
    historial: list[str] = field(default_factory=list)
    tema: str = "sistema"
    cambiar_tema: Callable[[str], Awaitable[Any]] | None = None
    # Preferencias de lectura de esta persona (la ayuda oculta). Se leen al
    # arrancar porque las del dispositivo solo se piden con la página abierta.
    banderas: dict[str, bool] = field(default_factory=dict)

    @property
    def configuracion(self) -> dict[str, Any]:
        return self.api.configuracion

    def ir(self, ruta: str, reemplazar: bool = False) -> None:
        if reemplazar and self.historial:
            self.historial[-1] = ruta
        else:
            self.historial.append(ruta)
        del self.historial[:-50]
        self.pagina.navigate(ruta)

    def volver(self, por_omision: str = "/revision") -> None:
        if len(self.historial) > 1:
            self.historial.pop()
            self.pagina.navigate(self.historial[-1])
        else:
            self.ir(por_omision, reemplazar=True)

    def avisar(self, texto: str, tono: str = "info") -> None:
        icono = {
            "exito": ft.Icons.CHECK_CIRCLE,
            "alerta": ft.Icons.WARNING_AMBER,
            "error": ft.Icons.ERROR,
        }.get(tono, ft.Icons.INFO)
        self.pagina.show_dialog(
            ft.SnackBar(
                ft.Row([ft.Icon(icono, size=18), ft.Text(texto, expand=True)], spacing=8),
                duration=ft.Duration(seconds=5),
                behavior=ft.SnackBarBehavior.FLOATING,
                show_close_icon=True,
            )
        )

    async def poner_bandera(self, clave: str, valor: bool) -> None:
        """Banderas de interfaz. Se guardan en el dispositivo y no en el
        servidor: son preferencias de lectura de una persona, no estado del
        trabajo de auditoría."""
        self.banderas[clave] = valor
        try:
            if valor:
                await self.preferencias.set(clave, True)
            else:
                await self.preferencias.remove(clave)
        except Exception:  # noqa: BLE001 - sin almacenamiento, la ayuda vuelve a aparecer
            pass


@dataclass(frozen=True, eq=False)
class EstadoSesion:
    sesion: dict[str, Any] | None = None
    motivo_de_salida: str | None = None
    entrar: Callable[[str, str], Awaitable[Any]] = lambda _c, _k: asyncio.sleep(0)
    salir: Callable[..., Any] = lambda *_a, **_k: None

    @property
    def autenticado(self) -> bool:
        return self.sesion is not None

    @property
    def usuario(self) -> dict[str, Any]:
        return (self.sesion or {}).get("usuario") or {}


@dataclass(frozen=True, eq=False)
class EstadoConsola:
    """La revisión que se está viendo y la que se está ejecutando. Viven en la
    consola y no en la pantalla de revisión: cambiar de pestaña a mitad de una
    revisión no debe perderla."""

    ejecucion_id: str | None = None
    elegir: Callable[[str], None] = lambda _id: None
    ejecutar: Callable[[], Awaitable[Any]] | None = None
    ejecutando: bool = False
    error_ejecucion: BaseException | None = None
    catalogo: Any = None
    ejecuciones: Any = None


AppContexto = ft.create_context(None)
SesionContexto = ft.create_context(EstadoSesion())
ConsolaContexto = ft.create_context(EstadoConsola())
AnchoContexto = ft.create_context(1280.0)


def use_app() -> Aplicacion:
    return ft.use_context(AppContexto)


def use_sesion() -> EstadoSesion:
    return ft.use_context(SesionContexto)


def use_consola() -> EstadoConsola:
    return ft.use_context(ConsolaContexto)


def use_ancho() -> float:
    return ft.use_context(AnchoContexto)


def mensaje_de_error(error: BaseException | None) -> str:
    if error is None:
        return ""
    if isinstance(error, ErrorApi):
        return error.mensaje
    return str(error) or "Ocurrió un error inesperado."
