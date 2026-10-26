"""Arranque de Cotejo en Flet: configuración, tema, sesión y rutas.

Cotejo es otro proyecto, con otra marca (el índigo del examen) y otro servicio,
pero comparte con Rastro el sistema de diseño y la forma de esta aplicación:
mismo armazón, mismas piezas, mismo manejo de la configuración (REQ-09). Que
se parezcan porque están construidas igual, no porque se hayan copiado.
"""

from __future__ import annotations

import flet as ft

from comun import diseno, ui
from comun.configuracion import cargar
from cotejo_app.api import POR_OMISION, ClienteCotejo
from cotejo_app.claves import CLAVE_AYUDA, CLAVE_TEMA, CLAVE_URL_COTEJO, CLAVE_URL_RASTRO
from cotejo_app.contexto import AnchoContexto, AppContexto, Aplicacion, ConsolaContexto, EstadoSesion, SesionContexto
from cotejo_app.estructura import Consola, Inicio, use_estado_consola
from cotejo_app.paginas.acceso import Acceso
from cotejo_app.paginas.catalogo import VistaCatalogo
from cotejo_app.paginas.diccionario import VistaGlosario
from cotejo_app.paginas.repetir import VistaComparacion
from cotejo_app.paginas.revision import VistaEjecucion



@ft.component
def NoEncontrado():
    app = ft.use_context(AppContexto)
    return ft.Container(
        ui.Tarjeta(
            ui.Vacio(
                "Esa página no existe",
                "Vuelva a la revisión.",
                ui.Boton("Ir a la revisión", lambda: app.ir("/revision")),
            )
        ),
        padding=16,
    )


RUTAS = [
    ft.Route(path="acceso", component=Acceso),
    ft.Route(
        component=Consola,
        children=[
            ft.Route(index=True, component=Inicio),
            ft.Route(path="revision", component=VistaEjecucion),
            ft.Route(path="catalogo", component=VistaCatalogo),
            ft.Route(path="repetir", component=VistaComparacion),
            ft.Route(path="diccionario", component=VistaGlosario),
        ],
    ),
]


@ft.component
def Raiz(app: Aplicacion, tema_inicial: str):
    pagina = app.pagina
    sesion, poner_sesion = ft.use_state(None)
    motivo, poner_motivo = ft.use_state(None)
    tema, poner_tema = ft.use_state(tema_inicial)
    brillo, poner_brillo = ft.use_state(pagina.platform_brightness)
    ancho, poner_ancho = ft.use_state(pagina.width or 1280)

    def puente():
        def al_cambiar(nueva):
            poner_sesion(nueva)
            if nueva is None:
                poner_motivo("La sesión expiró. Vuelva a entrar.")
                app.almacen.vaciar()

        app.api.al_cambiar_sesion = al_cambiar
        # Los eventos no siempre traen el dato: se lee de la página, que
        # siempre lo tiene al día.
        pagina.on_resize = lambda e: poner_ancho(getattr(e, "width", None) or pagina.width or 1280)
        pagina.on_platform_brightness_change = lambda e: poner_brillo(
            getattr(e, "brightness", None) or pagina.platform_brightness
        )
        # El cliente solo envía los eventos de la página que tienen manejador, y
        # se entera de que lo tienen con la siguiente actualización de la página.
        pagina.update()
        poner_ancho(pagina.width or 1280)

    ft.use_effect(puente, [])

    async def entrar(correo: str, clave: str):
        nueva = await app.api.entrar(correo.strip(), clave)
        if "auditor" not in (nueva["usuario"].get("grupos") or []):
            raise PermissionError(
                "Esa cuenta no puede entrar aquí: hace falta ser auditor. Lo que se guarda en este "
                "programa es la lista de puntos débiles del sistema, y por eso solo la ve quien tiene "
                "que revisarlos."
            )
        app.api.sesion = nueva
        poner_motivo(None)
        poner_sesion(nueva)
        return nueva

    async def salir():
        # El token es de Rastro; se revoca allí antes de olvidarlo aquí. Sin
        # conexión, el cierre local sigue teniendo sentido.
        try:
            await app.api.peticion("/auth/salir", metodo="POST", base="rastro")
        except Exception:  # noqa: BLE001
            pass
        app.api.sesion = None
        app.almacen.vaciar()
        poner_sesion(None)
        poner_motivo(None)
        app.ir("/acceso", reemplazar=True)

    estado_sesion = EstadoSesion(sesion=sesion, motivo_de_salida=motivo, entrar=entrar, salir=salir)
    estado_consola = use_estado_consola(app, sesion is not None)

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
        diseno.colores("cotejo", efectivo),
        lambda: AppContexto(
            app,
            lambda: SesionContexto(
                estado_sesion,
                lambda: ConsolaContexto(
                    estado_consola,
                    lambda: AnchoContexto(ancho, lambda: ft.Router(RUTAS, not_found=NoEncontrado)),
                ),
            ),
        ),
    )


async def principal(pagina: ft.Page):
    configuracion, origen = cargar("cotejo", POR_OMISION)
    preferencias = ft.SharedPreferences()

    # Las direcciones fijadas en el dispositivo ganan sobre las empaquetadas: es
    # lo que permite apuntar un APK instalado a otra cuenta sin reconstruirlo.
    try:
        propia_cotejo = await preferencias.get(CLAVE_URL_COTEJO)
        propia_rastro = await preferencias.get(CLAVE_URL_RASTRO)
        tema = await preferencias.get(CLAVE_TEMA) or "sistema"
        ayuda_oculta = bool(await preferencias.get(CLAVE_AYUDA))
    except Exception:  # noqa: BLE001
        propia_cotejo, propia_rastro, tema, ayuda_oculta = None, None, "sistema", False
    if propia_cotejo or propia_rastro:
        configuracion = {
            **configuracion,
            **({"url_cotejo": propia_cotejo} if propia_cotejo else {}),
            **({"url_rastro": propia_rastro} if propia_rastro else {}),
        }
        origen = "direcciones fijadas en este dispositivo"

    pagina.title = "Cotejo · Revisa a Rastro"
    pagina.fonts = diseno.FUENTES
    pagina.theme = diseno.tema_flet("cotejo", "claro")
    pagina.dark_theme = diseno.tema_flet("cotejo", "oscuro")
    pagina.theme_mode = {"claro": ft.ThemeMode.LIGHT, "oscuro": ft.ThemeMode.DARK}.get(tema, ft.ThemeMode.SYSTEM)
    pagina.padding = 0
    pagina.spacing = 0

    app = Aplicacion(
        pagina=pagina,
        api=ClienteCotejo(configuracion),
        preferencias=preferencias,
        origen_configuracion=origen,
        banderas={CLAVE_AYUDA: ayuda_oculta},
    )
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
