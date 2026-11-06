"""Armazón de la aplicación: marca, navegación por rol e identidad de la sesión.

La navegación **sale de la base de datos**, no de una lista escrita aquí (ADR-009):
cada organización tiene sus módulos en la tabla de maestros, y el armazón los
pinta filtrados por el grupo del usuario. El filtro no es un control de
seguridad —el servidor decide en cada operación— sino de claridad.

Por debajo de 1024 px el armazón es una barra superior con el menú plegado
detrás de un botón; desde 1024 px, una columna lateral. Es la misma lista de
entradas con otra disposición, de modo que no pueden desincronizarse.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from comun import diseno as d
from comun import ui
from comun.marca import LogotipoRastro
from rastro_app.consultas import use_envios, use_estados_finales, use_modulos
from rastro_app.contexto import BarraFija, icono, use_ancho, use_app, use_sesion

ANCHO_LATERAL = 240
ANCHO_CONTENIDO = 1248


def ancho_contenido(ancho_ventana: float) -> float:
    """El ancho útil de las pantallas: la ventana menos la columna lateral (si
    la hay) y los márgenes, con el tope de 78 rem de la web."""
    lateral = ANCHO_LATERAL if ancho_ventana >= d.PUNTOS_DE_CORTE["lg"] else 0
    return min(ancho_ventana - lateral - 2 * d.E4, ANCHO_CONTENIDO)


@dataclass(frozen=True)
class Entrada:
    ruta: str
    texto: str
    icono: str
    exacta: bool = False
    contador: int | None = None


def _activa(ruta_actual: str, entrada: Entrada) -> bool:
    actual = ruta_actual.split("?")[0]
    if entrada.exacta:
        # «Órdenes» es exacta para que «Registrar» (/envios/nuevo) no la marque,
        # pero el detalle de un envío sí pertenece a ella.
        return actual == entrada.ruta or (
            actual.startswith(entrada.ruta + "/") and actual not in ("/envios/nuevo", "/envios/guias")
        )
    return actual == entrada.ruta or actual.startswith(entrada.ruta + "/")


def use_entradas() -> list[Entrada]:
    sesion = use_sesion()
    modulos = use_modulos()
    envios = use_envios(habilitada=sesion.tiene_grupo("administrador", "despachador", "conductor"))
    es_final = use_estados_finales()

    solo_conductor = sesion.tiene_grupo("conductor") and not sesion.tiene_grupo("administrador", "despachador")
    pendientes = sum(1 for e in (envios.datos or {}).get("envios", []) if not es_final(e["estado"]))

    disponibles = [
        m
        for m in (modulos.datos or {}).get("modulos", [])
        if m.get("disponible") and m.get("destacado") and sesion.tiene_grupo(*m.get("grupos", []))
    ]
    secciones = [
        Entrada(
            ruta=m["ruta"],
            # El conductor no ve «Órdenes» sino «Mis envíos»: el servidor solo
            # le devuelve los suyos, y llamarlo igual daría a entender que la
            # empresa mueve seis envíos.
            texto="Mis envíos" if m["clave"] == "ordenes" and solo_conductor else m["nombre"],
            icono=m.get("icono", ""),
            exacta=m["clave"] == "ordenes",
            contador=pendientes if m["clave"] == "ordenes" else None,
        )
        for m in disponibles
    ]
    # Panel y Operaciones no son módulos: son las dos pantallas que enmarcan a
    # los demás. Van siempre, en los extremos.
    centro = (
        [Entrada("/operaciones", "Operaciones", "estados")]
        if sesion.tiene_grupo("administrador", "despachador", "conductor", "auditor")
        else []
    )
    return [Entrada("/panel", "Panel", "panel"), *secciones, *centro]


@ft.component
def BotonEntrada(entrada: Entrada, activa: bool, al_elegir) -> ft.Control:
    p = ui.paleta()
    partes: list[ft.Control] = [
        ft.Icon(icono(entrada.icono), size=18, color=p["acento"] if activa else p["texto-suave"]),
        ft.Text(
            entrada.texto,
            size=d.T_SM,
            weight=ft.FontWeight.W_600,
            color=p["acento-fuerte"] if activa else p["texto"],
            expand=True,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ]
    if entrada.contador:
        partes.append(ui.Insignia(str(entrada.contador)))
    return ft.Container(
        content=ft.Row(partes, spacing=d.E3, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=d.E3),
        height=d.TACTIL,
        border_radius=d.R_MD,
        bgcolor=p["acento-suave"] if activa else None,
        on_click=lambda _e: al_elegir(entrada.ruta),
        ink=True,
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
    textos: list[ft.Control] = [ft.Text("Rastro", size=d.T_LG, weight=ft.FontWeight.W_800)]
    if not compacta:
        textos.append(ft.Text("Trazabilidad de envíos", size=d.T_XS, color=p["texto-suave"]))
    return ft.Container(
        content=ft.Row(
            [LogotipoRastro(26), ft.Column(textos, spacing=0, tight=True)],
            spacing=d.E2,
            tight=True,
        ),
        on_click=lambda _e: app.ir("/panel"),
        height=d.TACTIL,
    )


@ft.component
def Identidad() -> ft.Control:
    sesion = use_sesion()
    p = ui.paleta()
    partes: list[ft.Control] = []
    if sesion.empresa:
        partes.append(ui.Insignia(sesion.empresa.get("nombre", ""), "acento"))
    if sesion.usuario:
        partes.append(
            ft.Column(
                [
                    ft.Text(sesion.usuario.get("nombre", ""), size=d.T_SM, weight=ft.FontWeight.W_600),
                    ft.Text(" · ".join(sesion.grupos), size=d.T_XS, color=p["texto-suave"]),
                ],
                spacing=0,
                tight=True,
            )
        )
    return ft.Column(partes, spacing=d.E2, tight=True)


@ft.component
def PieDePagina() -> ft.Control:
    app = use_app()
    sesion = use_sesion()
    p = ui.paleta()
    configuracion = app.configuracion
    partes = [
        f"Entorno {configuracion.get('entorno', 'local')} · región {configuracion.get('region', '')}",
        *([f"NIT {sesion.empresa['nit']}"] if (sesion.empresa or {}).get("nit") else []),
        "Datos sintéticos: el sistema no trata información de titulares reales.",
    ]
    return ft.Container(
        content=ft.Row(
            [
                *[ft.Text(t, size=d.T_XS, color=p["texto-tenue"]) for t in partes],
                ft.TextButton("Consulta pública de un envío", on_click=lambda: app.ir("/rastreo")),
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
    entradas = use_entradas()
    menu_abierto, poner_menu = ft.use_state(False)
    barra, poner_barra = ft.use_state(None)
    app.poner_barra = poner_barra
    ruta_actual = app.pagina.route or "/panel"

    def elegir(ruta: str):
        poner_menu(False)
        app.ir(ruta)

    lista = [BotonEntrada(e, _activa(ruta_actual, e), elegir, key=e.ruta) for e in entradas]
    boton_salir = ui.Boton("Salir", lambda: sesion.salir(), variante="secundario", icono=ft.Icons.LOGOUT)
    lateral = ancho >= d.PUNTOS_DE_CORTE["lg"]

    contenido = ft.Column(
        [
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column([salida, PieDePagina()], spacing=d.E5),
                        width=ancho_contenido(ancho),
                        padding=ft.Padding.symmetric(vertical=d.E5),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        # Una pantalla nueva empieza arriba, como en la web: con la misma clave,
        # el desplazamiento de la anterior se conservaría.
        key=ruta_actual.split("?")[0],
    )
    cuerpo = ft.Container(contenido, expand=True, padding=ft.Padding.symmetric(horizontal=d.E4))
    # La forma del árbol no cambia al aparecer la barra: si cambiara, Flet
    # volvería a montar la pantalla entera y perdería su estado.
    cuerpo = ft.Column(
        [cuerpo, PieFijo(barra) if barra is not None else ft.Container(visible=False)],
        spacing=0,
        expand=True,
    )

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
    # El menú plegado ocupa siempre su sitio en el árbol y solo cambia de
    # visibilidad: si apareciera y desapareciera, Flet volvería a montar la
    # pantalla de debajo y perdería su estado.
    menu = ft.Container(
        content=ft.Column(
            [*lista, ft.Divider(height=1, color=p["borde"]), Identidad(), ft.Row([boton_salir])],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=d.E3,
        bgcolor=p["superficie"],
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
        visible=menu_abierto,
    )
    return ft.SafeArea(ft.Column([barra, menu, cuerpo], spacing=0, expand=True), expand=True)


@ft.component
def PieFijo(barra: BarraFija) -> ft.Control:
    """La barra de acciones fija bajo el contenido, fuera del desplazamiento."""
    p = ui.paleta()
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(barra.texto, size=d.T_SM, weight=ft.FontWeight.W_600, expand=True),
                *[ui.Boton(texto, accion, variante=variante) for texto, accion, variante in barra.acciones],
            ],
            spacing=d.E2,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E4, vertical=d.E3),
        bgcolor=p["acento-suave"],
        border=ft.Border(top=ft.BorderSide(1, p["acento-borde"])),
    )
