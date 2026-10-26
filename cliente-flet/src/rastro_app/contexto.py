"""Lo que comparten todas las pantallas de Rastro: la aplicación de la página
abierta y la sesión.

`Aplicacion` agrupa lo que no cambia mientras la página está abierta —el
cliente de la API, el almacén de consultas, las preferencias del dispositivo—.
`EstadoSesion` es lo que sí cambia —quién entró, en nombre de qué empresa y con
qué permisos— y llega a las pantallas por contexto, como en la web.

La interfaz oculta lo que un rol no puede hacer, pero eso es comodidad y no
control: la autorización la decide el servidor en cada operación.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import flet as ft

from comun.datos import Almacen
from comun.http import ErrorApi
from rastro_app.api import ClienteRastro
from rastro_app.ubicacion import Gps


@dataclass(eq=False)
class Aplicacion:
    pagina: ft.Page
    api: ClienteRastro
    preferencias: ft.SharedPreferences
    origen_configuracion: str
    almacen: Almacen = field(default_factory=Almacen)
    gps: Gps = field(default_factory=Gps)
    # Lo que una pantalla le pasa a la siguiente al navegar: los envíos
    # elegidos para las guías, el aviso de «recién creado», a dónde volver
    # tras entrar. Es el `state` de React Router.
    traspaso: dict[str, Any] = field(default_factory=dict)
    historial: list[str] = field(default_factory=list)
    # El tema elegido («sistema», «claro», «oscuro») y cómo cambiarlo. Los
    # pone la raíz, que es la que guarda el estado.
    tema: str = "sistema"
    cambiar_tema: Callable[[str], Awaitable[Any]] | None = None
    # La barra fija al pie del armazón (la de «Generar guías» o «Salir a
    # ruta»): queda a la vista mientras se recorre una lista larga. La pantalla
    # describe la barra con `BarraFija` y el armazón la dibuja.
    poner_barra: Callable[["BarraFija | None"], None] = lambda _barra: None

    @property
    def configuracion(self) -> dict[str, Any]:
        return self.api.configuracion

    def ir(self, ruta: str, reemplazar: bool = False, **traspaso: Any) -> None:
        self.traspaso.update(traspaso)
        if reemplazar and self.historial:
            self.historial[-1] = ruta
        else:
            self.historial.append(ruta)
        del self.historial[:-50]
        self.pagina.navigate(ruta)

    def volver(self, por_omision: str = "/panel") -> None:
        if len(self.historial) > 1:
            self.historial.pop()
            self.pagina.navigate(self.historial[-1])
        else:
            self.ir(por_omision, reemplazar=True)

    def tomar(self, clave: str, por_omision: Any = None) -> Any:
        """Lee y olvida un dato de traspaso: el aviso de «recién creado» no debe
        volver a salir al regresar a la misma pantalla más tarde."""
        return self.traspaso.pop(clave, por_omision)

    def avisar(self, texto: str, tono: str = "info") -> None:
        """Confirmación breve de que algo surtió efecto. Los errores que hay que
        leer y corregir no van aquí: van junto al formulario que los produjo."""
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

    def en_segundo_plano(self, trabajo: Callable[[], Awaitable[Any]]) -> None:
        self.pagina.run_task(trabajo)


@dataclass(frozen=True, eq=False)
class EstadoSesion:
    sesion: dict[str, Any] | None = None
    empresa: dict[str, Any] | None = None
    permisos: tuple[str, ...] = ()
    permisos_cargados: bool = False
    motivo_de_salida: str | None = None
    entrar: Callable[[str, str], Awaitable[Any]] = lambda _c, _k: asyncio.sleep(0)
    salir: Callable[..., Awaitable[Any]] = lambda *_a, **_k: asyncio.sleep(0)

    @property
    def autenticado(self) -> bool:
        return self.sesion is not None

    @property
    def usuario(self) -> dict[str, Any]:
        return (self.sesion or {}).get("usuario") or {}

    @property
    def grupos(self) -> list[str]:
        return list(self.usuario.get("grupos") or [])

    def tiene_grupo(self, *grupos: str) -> bool:
        return any(grupo in self.grupos for grupo in grupos)

    def puede(self, *operaciones: str) -> bool:
        """Si la sesión tiene alguno de los permisos. Es lo que decide qué
        ofrecer: preguntar por el nombre del rol dejó de servir cuando los roles
        pasaron a ser configurables."""
        return any(operacion in self.permisos for operacion in operaciones)


@dataclass(frozen=True, eq=False)
class BarraFija:
    texto: str
    acciones: tuple[tuple[str, Callable[[], Any], str], ...]
    """(texto, acción, variante) de cada botón."""


AppContexto = ft.create_context(None)
SesionContexto = ft.create_context(EstadoSesion())
AnchoContexto = ft.create_context(1280.0)


def use_app() -> Aplicacion:
    return ft.use_context(AppContexto)


def use_sesion() -> EstadoSesion:
    return ft.use_context(SesionContexto)


def use_ancho() -> float:
    """El ancho de la ventana, para las decisiones de forma que una rejilla
    responsive no resuelve (la navegación lateral o colapsada)."""
    return ft.use_context(AnchoContexto)


# --------------------------------------------------------------------------- #
# Errores en el vocabulario de Rastro
# --------------------------------------------------------------------------- #


def mensaje_de_error(error: BaseException | None) -> str:
    """Traduce un error a algo que la persona pueda entender y, cuando aplica,
    hacer algo al respecto. Los mismos textos que la interfaz web."""
    if error is None:
        return ""
    if isinstance(error, ErrorApi):
        if error.codigo == "SIN_CONEXION":
            return "Sin conexión. El registro no se guardó; inténtelo de nuevo cuando tenga señal."
        if error.codigo == "NO_AUTORIZADO":
            return "Su rol no puede ejecutar esa operación. El intento quedó registrado en la bitácora."
        if error.codigo == "NO_ENCONTRADO":
            return "El envío no existe o no pertenece a su organización."
        if error.codigo == "TRANSICION_INVALIDA" and error.transiciones_permitidas:
            permitidas = ", ".join(e.replace("_", " ") for e in error.transiciones_permitidas)
            return f"{error.mensaje} Desde el estado actual solo se puede pasar a: {permitidas}."
        if error.codigo == "NO_AUTENTICADO":
            return error.mensaje or "La sesión expiró. Vuelva a entrar."
        return error.mensaje
    return str(error) or "Ocurrió un error inesperado."


# --------------------------------------------------------------------------- #
# Iconos por nombre
# --------------------------------------------------------------------------- #

# Los módulos dicen el **nombre** de su icono, no el dibujo (vive en la tabla de
# maestros). Un nombre desconocido dibuja el genérico en lugar de dejar un hueco.
ICONOS = {
    "paquete": ft.Icons.INVENTORY_2_OUTLINED,
    "mas": ft.Icons.ADD_BOX_OUTLINED,
    "etiqueta": ft.Icons.QR_CODE_2,
    "rastro": ft.Icons.TRAVEL_EXPLORE,
    "camion": ft.Icons.LOCAL_SHIPPING_OUTLINED,
    "tienda": ft.Icons.STOREFRONT_OUTLINED,
    "recoleccion": ft.Icons.MOVE_TO_INBOX_OUTLINED,
    "mapa": ft.Icons.MAP_OUTLINED,
    "ruta": ft.Icons.ROUTE_OUTLINED,
    "ubicacion": ft.Icons.MY_LOCATION,
    "usuarios": ft.Icons.GROUP_OUTLINED,
    "clientes": ft.Icons.BADGE_OUTLINED,
    "documento": ft.Icons.DESCRIPTION_OUTLINED,
    "bitacora": ft.Icons.RECEIPT_LONG_OUTLINED,
    "factura": ft.Icons.REQUEST_QUOTE_OUTLINED,
    "estados": ft.Icons.ACCOUNT_TREE_OUTLINED,
    "panel": ft.Icons.DASHBOARD_OUTLINED,
    "auditoria": ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
    "verificado": ft.Icons.VERIFIED_OUTLINED,
    "alerta": ft.Icons.WARNING_AMBER_OUTLINED,
    "cadena": ft.Icons.LINK,
    "reloj": ft.Icons.SCHEDULE,
}


def icono(nombre: str) -> ft.IconData:
    return ICONOS.get(nombre, ft.Icons.APPS)
