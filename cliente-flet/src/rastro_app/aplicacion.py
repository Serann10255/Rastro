"""Arranque de Rastro en Flet: configuración, tema, sesión y rutas.

Las rutas son las de la interfaz web (`web/src/App.tsx`), con el mismo nombre y
el mismo control de acceso, de modo que un enlace a `/envios/<id>` o a
`/rastreo?envio=<id>` sirve en las dos. En el modo web la ruta va en la barra de
direcciones; en escritorio y en el teléfono, en la navegación interna.
"""

from __future__ import annotations

import flet as ft

from comun import diseno, ui
from comun.configuracion import cargar
from rastro_app.aplicacion_claves import CLAVE_TEMA, CLAVE_URL_API
from rastro_app.api import POR_OMISION, ClienteRastro
from rastro_app.contexto import AnchoContexto, AppContexto, Aplicacion, EstadoSesion, SesionContexto
from rastro_app.paginas.acceso import Acceso
from rastro_app.paginas.administracion import Administracion
from rastro_app.paginas.bitacora import Bitacora
from rastro_app.paginas.entregas import Entregas
from rastro_app.paginas.envio_detalle import EnvioDetalle
from rastro_app.paginas.envio_nuevo import EnvioNuevo
from rastro_app.paginas.envios import Envios
from rastro_app.paginas.guias import Guias
from rastro_app.paginas.maestros import Maestros
from rastro_app.paginas.operaciones import CatalogoEstados, Operaciones
from rastro_app.paginas.panel import Panel
from rastro_app.paginas.rastreo import Rastreo
from rastro_app.paginas.roles import Roles
from rastro_app.paginas.seguimiento import Seguimiento
from rastro_app.proteccion import ExigeGrupo, ExigePermiso, Inicio, NoEncontrado, RutaProtegida

def _con(componente, envoltura):
    """Una pantalla envuelta en su control de acceso, como componente de ruta."""

    @ft.component
    def Ruta():
        return envoltura(componente)

    return Ruta


def _grupos(*grupos: str):
    return lambda pantalla: ExigeGrupo(list(grupos), pantalla)


def _permiso(operacion: str, descripcion: str):
    return lambda pantalla: ExigePermiso(operacion, descripcion, pantalla)


RUTAS = [
    # Sin sesión: el destinatario no tiene cuenta.
    ft.Route(path="rastreo", component=Rastreo),
    ft.Route(path="acceso", component=Acceso),
    ft.Route(
        component=RutaProtegida,
        children=[
            ft.Route(index=True, component=Inicio),
            ft.Route(path="panel", component=Panel),
            # Las rutas fijas antes que la paramétrica, o «nuevo» se
            # interpretaría como un identificador.
            ft.Route(path="envios", component=_con(Envios, _grupos("administrador", "despachador", "conductor"))),
            ft.Route(path="envios/nuevo", component=_con(EnvioNuevo, _grupos("administrador", "despachador"))),
            ft.Route(path="envios/guias", component=_con(Guias, _grupos("administrador", "despachador"))),
            ft.Route(path="envios/:envio_id", component=EnvioDetalle),
            # Las rutas de entrega deciden por permiso y no por rol: compartir y
            # ver la ubicación de una persona se conceden aparte.
            ft.Route(
                path="entregas",
                component=_con(Entregas, _permiso("ruta:operar", "salir a ruta con sus guías")),
            ),
            ft.Route(
                path="seguimiento",
                component=_con(
                    Seguimiento, _permiso("ruta:seguir", "ver la ubicación de los conductores en ruta")
                ),
            ),
            ft.Route(path="operaciones", component=_con(Operaciones, _grupos("administrador", "despachador"))),
            ft.Route(path="operaciones/estados", component=CatalogoEstados),
            ft.Route(path="maestros/:recurso", component=_con(Maestros, _grupos("administrador", "despachador"))),
            ft.Route(path="administracion/roles", component=_con(Roles, _grupos("administrador", "auditor"))),
            ft.Route(path="administracion", component=_con(Administracion, _grupos("administrador", "auditor"))),
            ft.Route(path="bitacora", component=_con(Bitacora, _grupos("auditor"))),
        ],
    ),
]


@ft.component
def Raiz(app: Aplicacion, tema_inicial: str):
    pagina = app.pagina
    sesion, poner_sesion = ft.use_state(None)
    datos_yo, poner_datos_yo = ft.use_state(lambda: {"empresa": None, "permisos": (), "cargados": False})
    motivo, poner_motivo = ft.use_state(None)
    tema, poner_tema = ft.use_state(tema_inicial)
    brillo, poner_brillo = ft.use_state(pagina.platform_brightness)
    ancho, poner_ancho = ft.use_state(pagina.width or 1280)

    # El cliente avisa cuando renueva la sesión sola o cuando el servidor la
    # rechaza. Sin este puente la interfaz seguiría mostrando a alguien cuya
    # sesión ya no existe.
    def puente():
        def al_cambiar(nueva):
            poner_sesion(nueva)
            if nueva is None:
                poner_datos_yo({"empresa": None, "permisos": (), "cargados": False})
                poner_motivo("La sesión expiró. Vuelva a entrar.")
                app.almacen.vaciar()

        app.api.al_cambiar_sesion = al_cambiar
        # Los eventos no siempre traen el dato (el primero de brillo llega sin
        # él): se lee de la página, que siempre lo tiene al día.
        pagina.on_resize = lambda e: poner_ancho(getattr(e, "width", None) or pagina.width or 1280)
        pagina.on_platform_brightness_change = lambda e: poner_brillo(
            getattr(e, "brightness", None) or pagina.platform_brightness
        )
        # El cliente solo envía los eventos de la página que tienen manejador, y
        # se entera de que lo tienen con la siguiente actualización de la página.
        pagina.update()
        poner_ancho(pagina.width or 1280)

    ft.use_effect(puente, [])

    # Los datos de la empresa y los permisos se piden al servidor una vez por
    # sesión, no se guardan en el token: cambiar el nombre de la empresa o un
    # rol surte efecto sin volver a entrar.
    async def cargar_yo():
        if not sesion:
            return
        try:
            datos = await app.api.yo()
            poner_datos_yo(
                {"empresa": datos.get("empresa"), "permisos": tuple(datos.get("permisos") or ()), "cargados": True}
            )
        except Exception:  # noqa: BLE001
            # Sin esto la interfaz funciona igual, con menos ofrecido; se dan
            # por cargados para que ninguna pantalla espere para siempre.
            poner_datos_yo(lambda d: {**d, "cargados": True})

    ft.use_effect(cargar_yo, [sesion["token"] if sesion else None])

    async def entrar(correo: str, clave: str):
        nueva = await app.api.entrar(correo.strip(), clave)
        poner_motivo(None)
        poner_sesion(nueva)
        return nueva

    async def salir(motivo_salida: str | None = None, todas: bool = False):
        await app.api.salir(todas)
        app.almacen.vaciar()
        poner_sesion(None)
        poner_datos_yo({"empresa": None, "permisos": (), "cargados": False})
        poner_motivo(motivo_salida)
        app.ir("/acceso", reemplazar=True)

    estado_sesion = EstadoSesion(
        sesion=sesion,
        empresa=datos_yo["empresa"],
        permisos=datos_yo["permisos"],
        permisos_cargados=datos_yo["cargados"],
        motivo_de_salida=motivo,
        entrar=entrar,
        salir=salir,
    )

    async def cambiar_tema(nuevo: str):
        poner_tema(nuevo)
        pagina.theme_mode = {"claro": ft.ThemeMode.LIGHT, "oscuro": ft.ThemeMode.DARK}.get(nuevo, ft.ThemeMode.SYSTEM)
        pagina.update()
        try:
            await app.preferencias.set(CLAVE_TEMA, nuevo)
        except Exception:  # noqa: BLE001 - sin almacenamiento, el tema dura la sesión
            pass

    app.cambiar_tema = cambiar_tema
    app.tema = tema
    efectivo = tema if tema in ("claro", "oscuro") else ("oscuro" if brillo == ft.Brightness.DARK else "claro")

    return ui.Paleta(
        diseno.colores("rastro", efectivo),
        lambda: AppContexto(
            app,
            lambda: SesionContexto(
                estado_sesion,
                lambda: AnchoContexto(ancho, lambda: ft.Router(RUTAS, not_found=NoEncontrado)),
            ),
        ),
    )


async def principal(pagina: ft.Page):
    configuracion, origen = cargar("rastro", POR_OMISION)
    preferencias = ft.SharedPreferences()

    # La dirección fijada en el dispositivo gana sobre la empaquetada: es lo
    # que permite apuntar un APK instalado a otra cuenta sin reconstruirlo.
    try:
        propia = await preferencias.get(CLAVE_URL_API)
        tema = await preferencias.get(CLAVE_TEMA) or "sistema"
    except Exception:  # noqa: BLE001
        propia, tema = None, "sistema"
    if propia:
        configuracion = {**configuracion, "url_publica_api": propia}
        origen = "dirección fijada en este dispositivo"

    pagina.title = "Rastro · Trazabilidad de envíos"
    pagina.fonts = diseno.FUENTES
    pagina.theme = diseno.tema_flet("rastro", "claro")
    pagina.dark_theme = diseno.tema_flet("rastro", "oscuro")
    pagina.theme_mode = {"claro": ft.ThemeMode.LIGHT, "oscuro": ft.ThemeMode.DARK}.get(tema, ft.ThemeMode.SYSTEM)
    pagina.padding = 0
    pagina.spacing = 0

    app = Aplicacion(pagina=pagina, api=ClienteRastro(configuracion), preferencias=preferencias, origen_configuracion=origen)
    app.historial.append(pagina.route or "/")

    # El botón «atrás» del teléfono recorre lo navegado dentro de la aplicación
    # antes de cerrarla, como haría en un navegador.
    async def al_confirmar_salida(_e):
        if len(app.historial) > 1:
            app.volver()
            await pagina.views[0].confirm_pop(False)
        else:
            await pagina.views[0].confirm_pop(True)

    pagina.views[0].can_pop = False
    pagina.views[0].on_confirm_pop = al_confirmar_salida
    pagina.render(Raiz, app, tema)
