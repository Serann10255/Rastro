"""La consola del auditor: armazón, navegación y la revisión en curso.

Cuatro pantallas, que son los cuatro momentos del trabajo: ver contra qué
criterio se va a juzgar (catálogo), ejecutar y leer el resultado (revisión),
comprobar que otro obtiene lo mismo (repetición) y entender las palabras
(diccionario). En la web son pestañas; aquí son rutas, para que el botón
«atrás» del teléfono vuelva a la anterior en lugar de cerrar la aplicación.

Por debajo de 1024 px el armazón es una barra superior con el menú plegado
detrás de un botón; desde 1024 px, una columna lateral, como en Rastro.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from comun.datos import use_consulta
from comun.marca import LogotipoCotejo
from cotejo_app.contexto import EstadoConsola, use_ancho, use_app, use_sesion
from cotejo_app.piezas import ConTecnicismo

ANCHO_LATERAL = 240
ANCHO_CONTENIDO = 1248

ENTRADAS = [
    ("/revision", "Revisión", ft.Icons.VERIFIED_OUTLINED),
    ("/catalogo", "Qué se revisa", ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED),
    ("/repetir", "Repetir", ft.Icons.LINK),
    ("/diccionario", "Diccionario", ft.Icons.DESCRIPTION_OUTLINED),
]


@ft.component
def Redirigir(destino: str):
    app = use_app()
    ft.use_effect(lambda: app.ir(destino, reemplazar=True), [destino])
    return ui.Cargando("Abriendo…")


@ft.component
def Inicio():
    return Redirigir("/revision")


@ft.component
def Consola():
    """La parte con sesión: sin ella, al acceso."""
    sesion = use_sesion()
    salida = ft.use_route_outlet()
    if not sesion.autenticado:
        return Redirigir("/acceso")
    return Estructura(salida)


def use_estado_consola(app, autenticado: bool) -> EstadoConsola:
    """La revisión elegida y la que se ejecuta. Se llama desde la raíz, por
    encima del enrutador, y no desde `Consola`: el enrutador crea la pantalla
    hija con los contextos que hay por encima de él, así que un contexto puesto
    dentro de la ruta de diseño no le llegaría. Vivir arriba tiene además el
    efecto buscado: cambiar de pantalla a mitad de una revisión no la pierde."""
    ejecucion_id, poner_ejecucion_id = ft.use_state(None)
    ejecutando, poner_ejecutando = ft.use_state(False)
    error_ejecucion, poner_error = ft.use_state(None)

    catalogo = use_consulta(app.almacen, ("catalogo",), app.api.catalogo, habilitada=autenticado, vigencia=3600)
    ejecuciones = use_consulta(app.almacen, ("ejecuciones",), app.api.ejecuciones, habilitada=autenticado)

    # Al abrir, se muestra la última ejecución almacenada: es lo que el auditor
    # quiere ver primero al volver, y evita una pantalla vacía sin razón.
    lista = (ejecuciones.datos or {}).get("ejecuciones", []) if autenticado else []
    primera = lista[0]["ejecucion_id"] if lista else None

    def elegir_la_ultima():
        if not autenticado:
            poner_ejecucion_id(None)
        elif not ejecucion_id and primera:
            poner_ejecucion_id(primera)

    ft.use_effect(elegir_la_ultima, [primera, ejecucion_id, autenticado])

    async def ejecutar():
        poner_error(None)
        poner_ejecutando(True)
        try:
            datos = await app.api.ejecutar()
            if datos.get("estado") == "en_curso":
                await app.api.esperar_ejecucion(datos["ejecucion_id"])
            poner_ejecucion_id(datos["ejecucion_id"])
            app.almacen.invalidar("ejecuciones", "ejecucion")
        except Exception as fallo:  # noqa: BLE001 - se muestra en la pantalla de revisión
            poner_error(fallo)
        finally:
            poner_ejecutando(False)

    return EstadoConsola(
        ejecucion_id=ejecucion_id,
        elegir=poner_ejecucion_id,
        ejecutar=ejecutar,
        ejecutando=ejecutando,
        error_ejecucion=error_ejecucion,
        catalogo=catalogo,
        ejecuciones=ejecuciones,
    )


@ft.component
def SelectorTema() -> ft.Control:
    app = use_app()
    siguiente = {"sistema": "claro", "claro": "oscuro", "oscuro": "sistema"}
    rotulo = {"sistema": "Tema del sistema", "claro": "Tema claro", "oscuro": "Tema oscuro"}
    simbolo = {"sistema": ft.Icons.BRIGHTNESS_6, "claro": ft.Icons.LIGHT_MODE, "oscuro": ft.Icons.DARK_MODE}

    async def cambiar():
        if app.cambiar_tema:
            await app.cambiar_tema(siguiente.get(app.tema, "sistema"))

    return ui.BotonIcono(simbolo.get(app.tema, ft.Icons.BRIGHTNESS_6), cambiar, f"{rotulo.get(app.tema)}. Pulse para cambiar.")


@ft.component
def Marca(compacta: bool = False) -> ft.Control:
    app = use_app()
    p = ui.paleta()
    textos: list[ft.Control] = [ft.Text("Cotejo", size=d.T_LG, weight=ft.FontWeight.W_800)]
    if not compacta:
        textos.append(ft.Text("Revisa a Rastro", size=d.T_XS, color=p["texto-suave"]))
    return ft.Container(
        content=ft.Row([LogotipoCotejo(26), ft.Column(textos, spacing=0, tight=True)], spacing=d.E2, tight=True),
        on_click=lambda _e: app.ir("/revision"),
        height=d.TACTIL,
    )


@ft.component
def BotonEntrada(ruta: str, texto: str, icono: ft.IconData, activa: bool, al_elegir) -> ft.Control:
    p = ui.paleta()
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icono, size=18, color=p["acento"] if activa else p["texto-suave"]),
                ft.Text(
                    texto,
                    size=d.T_SM,
                    weight=ft.FontWeight.W_600,
                    color=p["acento-fuerte"] if activa else p["texto"],
                    expand=True,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=d.E3,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E3),
        height=d.TACTIL,
        border_radius=d.R_MD,
        bgcolor=p["acento-suave"] if activa else None,
        on_click=lambda _e: al_elegir(ruta),
        ink=True,
    )


@ft.component
def Identidad() -> ft.Control:
    sesion = use_sesion()
    p = ui.paleta()
    usuario = sesion.usuario
    return ft.Column(
        [
            ui.Insignia(usuario.get("org_id", ""), "acento"),
            ft.Column(
                [
                    ft.Text(usuario.get("nombre", ""), size=d.T_SM, weight=ft.FontWeight.W_600),
                    ft.Text("auditor", size=d.T_XS, color=p["texto-suave"]),
                ],
                spacing=0,
                tight=True,
            ),
        ],
        spacing=d.E2,
        tight=True,
    )


@ft.component
def AvisoAutorrevision() -> ft.Control:
    return ui.Aviso(
        ConTecnicismo(
            "Es el mismo equipo, así que esto no es una revisión de fuera. Se compensa como se puede: "
            "el programa da el mismo resultado lo ejecute quien lo ejecute, y otra persona puede "
            "repetirlo y comparar. Aun así se dice en cada pantalla, porque callarlo sería lo grave.",
            "en auditoría: amenaza de autorrevisión",
            tono="texto",
        ),
        tono="alerta",
        titulo="Quien revisa aquí es quien construyó",
    )


@ft.component
def PieDePagina() -> ft.Control:
    app = use_app()
    p = ui.paleta()
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(f"Entorno {app.configuracion.get('entorno', 'local')}", size=d.T_XS, color=p["texto-tenue"]),
                ft.Text(
                    "Las pruebas guardadas no se editan nunca: su valor depende justamente de eso.",
                    size=d.T_XS,
                    color=p["texto-tenue"],
                ),
            ],
            wrap=True,
            spacing=d.E4,
            run_spacing=d.E1,
        ),
        padding=ft.Padding.only(top=d.E4),
        border=ft.Border(top=ft.BorderSide(1, p["borde"])),
    )


@ft.component
def Estructura(salida: ft.Control) -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    ancho = use_ancho()
    p = ui.paleta()
    menu_abierto, poner_menu = ft.use_state(False)
    ruta_actual = (app.pagina.route or "/revision").split("?")[0]

    def elegir(ruta: str):
        poner_menu(False)
        app.ir(ruta)

    lista = [
        BotonEntrada(ruta, texto, icono, ruta_actual == ruta, elegir, key=ruta) for ruta, texto, icono in ENTRADAS
    ]
    boton_salir = ui.Boton("Salir", sesion.salir, variante="secundario", icono=ft.Icons.LOGOUT)
    lateral = ancho >= d.PUNTOS_DE_CORTE["lg"]

    disponible = ancho - (ANCHO_LATERAL if lateral else 0) - 2 * d.E4
    contenido = ft.Column(
        [
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column([AvisoAutorrevision(), salida, PieDePagina()], spacing=d.E5),
                        width=min(disponible, ANCHO_CONTENIDO),
                        padding=ft.Padding.symmetric(vertical=d.E5),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
    cuerpo = ft.Container(contenido, expand=True, padding=ft.Padding.symmetric(horizontal=d.E4))

    if lateral:
        columna = ft.Container(
            content=ft.Column(
                [
                    ft.Container(Marca(), padding=ft.Padding.only(bottom=d.E3)),
                    ft.Column(lista, spacing=2, scroll=ft.ScrollMode.AUTO, expand=True),
                    ft.Divider(height=1, color=p["borde"]),
                    Identidad(),
                    ft.Row([SelectorTema(), boton_salir], spacing=d.E2),
                ],
                spacing=d.E3,
            ),
            width=ANCHO_LATERAL,
            padding=d.E4,
            bgcolor=p["superficie"],
            border=ft.Border(right=ft.BorderSide(1, p["borde"])),
        )
        return ft.SafeArea(ft.Row([columna, cuerpo], spacing=0, expand=True), expand=True)

    barra = ft.Container(
        content=ft.Row(
            [
                Marca(compacta=True),
                ft.Container(expand=True),
                SelectorTema(),
                ui.BotonIcono(
                    ft.Icons.CLOSE if menu_abierto else ft.Icons.MENU,
                    lambda: poner_menu(not menu_abierto),
                    "Cerrar el menú" if menu_abierto else "Abrir el menú",
                ),
            ],
            spacing=d.E1,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E3, vertical=d.E1),
        bgcolor=p["superficie"],
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
    )
    # El menú ocupa siempre su sitio, vacío cuando está cerrado: si apareciera y
    # desapareciera de la lista, el contenido cambiaría de posición y Flet lo
    # volvería a montar entero, perdiendo lo que la pantalla tenía.
    menu = ft.Container(
        content=ft.Column(
            [*lista, ft.Divider(height=1, color=p["borde"]), Identidad(), ft.Row([boton_salir])],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        )
        if menu_abierto
        else None,
        padding=d.E3 if menu_abierto else 0,
        height=None if menu_abierto else 0,
        bgcolor=p["superficie"],
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])) if menu_abierto else None,
    )
    return ft.SafeArea(ft.Column([barra, menu, cuerpo], spacing=0, expand=True), expand=True)
