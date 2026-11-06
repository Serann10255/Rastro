"""Piezas de interfaz compartidas por Rastro y Cotejo.

Son las de `web/src/componentes/ui.tsx` —tarjeta, métrica, aviso, botón, campo,
vacío, esqueleto— con el mismo nombre y el mismo papel, para que una pantalla
se pueda leer junto a su par web. No se usa una biblioteca de componentes de
terceros por la razón de siempre: el proyecto se audita a sí mismo y conviene
que lo que se empaqueta sea código propio y revisable.

Los colores llegan por contexto (`Paleta`): cada pieza es un componente y lee la
paleta del tema vigente. Una función suelta que la leyera sería un «hook»
llamado de forma condicional, y Flet, como React, exige que los hooks se llamen
siempre en el mismo orden.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Sequence

import flet as ft

from comun import diseno as d
from comun.formato import texto_estado

Paleta = ft.create_context(d.colores("rastro", "claro"))

Accion = Callable[..., Any] | None
Contenido = ft.Control | Sequence[ft.Control] | str | None


def paleta() -> dict[str, str]:
    return ft.use_context(Paleta)


def manejador(funcion: Accion) -> Accion:
    """Un manejador de evento sin argumentos que espera lo que devuelva
    `funcion`. Flet solo espera las funciones `async def`: una lambda que
    devuelve una corrutina se quedaría sin ejecutar, en silencio."""
    if funcion is None or inspect.iscoroutinefunction(funcion):
        return funcion

    async def envoltura():
        resultado = funcion()
        if inspect.isawaitable(resultado):
            await resultado

    return envoltura


def _controles(contenido: Contenido) -> list[ft.Control]:
    if contenido is None:
        return []
    if isinstance(contenido, str):
        return [ft.Text(contenido, size=d.T_SM, selectable=True)]
    if isinstance(contenido, ft.BaseControl):
        return [contenido]
    return [c for c in contenido if c is not None]


# --------------------------------------------------------------------------- #
# Texto
# --------------------------------------------------------------------------- #


def Titulo(texto: str, nivel: int = 1) -> ft.Text:
    tamano = {1: d.T_2XL, 2: d.T_LG, 3: d.T_MD}.get(nivel, d.T_MD)
    return ft.Text(texto, size=tamano, weight=ft.FontWeight.W_700, selectable=True)


@ft.component
def Texto(
    texto: str,
    tono: str = "texto",
    tamano: float = d.T_SM,
    negrita: bool = False,
    mono: bool = False,
    seleccionable: bool = True,
    maximo_lineas: int | None = None,
) -> ft.Control:
    """Texto con el color de una ficha («texto-suave», «texto-tenue»...)."""
    p = paleta()
    return ft.Text(
        texto,
        size=tamano,
        color=p.get(tono, p["texto"]),
        weight=ft.FontWeight.W_600 if negrita else None,
        font_family=d.FUENTE_MONO if mono else None,
        selectable=seleccionable,
        max_lines=maximo_lineas,
        overflow=ft.TextOverflow.ELLIPSIS if maximo_lineas else None,
    )


# --------------------------------------------------------------------------- #
# Superficies
# --------------------------------------------------------------------------- #


@ft.component
def Tarjeta(
    contenido: Contenido = None,
    titulo: str | None = None,
    ayuda: str | None = None,
    acciones: Sequence[ft.Control] | None = None,
    pie: Contenido = None,
    expandir: bool = False,
) -> ft.Control:
    p = paleta()
    cabecera: list[ft.Control] = []
    if titulo or acciones:
        textos: list[ft.Control] = []
        if titulo:
            textos.append(ft.Text(titulo, size=d.T_MD, weight=ft.FontWeight.W_700))
        if ayuda:
            textos.append(ft.Text(ayuda, size=d.T_XS, color=p["texto-suave"]))
        # Título y acciones lado a lado desde 640 px; por debajo, las acciones
        # bajan. Una fila con salto de línea no admite hijos que se estiren.
        cabecera.append(
            ft.ResponsiveRow(
                [
                    ft.Column(textos, spacing=2, col={"xs": 12, "sm": 7 if acciones else 12}),
                    *(
                        [
                            ft.Row(
                                list(acciones),
                                wrap=True,
                                spacing=d.E2,
                                run_spacing=d.E2,
                                alignment=ft.MainAxisAlignment.END,
                                col={"xs": 12, "sm": 5},
                            )
                        ]
                        if acciones
                        else []
                    ),
                ],
                breakpoints=d.PUNTOS_DE_CORTE,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=d.E3,
                run_spacing=d.E2,
            )
        )
    cuerpo = _controles(contenido)
    partes = [*cabecera, *cuerpo]
    if pie is not None:
        partes += [ft.Divider(height=1, color=p["borde"]), *_controles(pie)]
    return ft.Container(
        content=ft.Column(partes, spacing=d.E3, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        padding=d.E4,
        bgcolor=p["superficie"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_LG,
        expand=True if expandir else None,
    )


@ft.component
def Metrica(etiqueta: str, valor: Any, nota: str | None = None, color: str | None = None) -> ft.Control:
    """Un indicador. `color` es el nombre de una ficha («exito», «peligro»...)."""
    p = paleta()
    tono = p.get(color, p["texto"]) if color else p["texto"]
    valor_control = valor if isinstance(valor, ft.BaseControl) else ft.Text(
        str(valor), size=d.T_2XL, weight=ft.FontWeight.W_700, color=tono
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(etiqueta.upper(), size=d.T_XS, weight=ft.FontWeight.W_700, color=p["texto-suave"]),
                valor_control,
                *([ft.Text(nota, size=d.T_XS, color=p["texto-tenue"])] if nota else []),
            ],
            spacing=d.E1,
            tight=True,
        ),
        padding=d.E4,
        bgcolor=p["superficie"],
        border=ft.Border(
            left=ft.BorderSide(4, tono if color else p["borde-fuerte"]),
            top=ft.BorderSide(1, p["borde"]),
            right=ft.BorderSide(1, p["borde"]),
            bottom=ft.BorderSide(1, p["borde"]),
        ),
        border_radius=d.R_MD,
    )


# --------------------------------------------------------------------------- #
# Avisos y estados vacíos
# --------------------------------------------------------------------------- #

_TONOS = {
    "info": ("info", "info-suave", "acento-borde", ft.Icons.INFO_OUTLINE),
    "exito": ("exito", "exito-suave", "exito-borde", ft.Icons.CHECK_CIRCLE_OUTLINE),
    "alerta": ("alerta", "alerta-suave", "alerta-borde", ft.Icons.WARNING_AMBER_OUTLINED),
    "error": ("peligro", "peligro-suave", "peligro-borde", ft.Icons.ERROR_OUTLINE),
}


@ft.component
def Aviso(
    contenido: Contenido = None,
    tono: str = "info",
    titulo: str | None = None,
    acciones: Sequence[ft.Control] | None = None,
) -> ft.Control:
    p = paleta()
    color, fondo, borde, icono = _TONOS.get(tono, _TONOS["info"])
    partes: list[ft.Control] = []
    if titulo:
        partes.append(ft.Text(titulo, size=d.T_SM, weight=ft.FontWeight.W_700, color=p["texto"]))
    partes += _controles(contenido)
    if acciones:
        partes.append(ft.Row(list(acciones), wrap=True, spacing=d.E2))
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icono, color=p[color], size=20),
                ft.Column(partes, spacing=d.E1, expand=True, tight=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=d.E3,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E4, vertical=d.E3),
        bgcolor=p[fondo],
        border=ft.Border.all(1, p[borde]),
        border_radius=d.R_MD,
    )


@ft.component
def Vacio(titulo: str, descripcion: str | None = None, accion: ft.Control | None = None) -> ft.Control:
    p = paleta()
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(titulo, size=d.T_MD, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                *(
                    [ft.Text(descripcion, size=d.T_SM, color=p["texto-suave"], text_align=ft.TextAlign.CENTER)]
                    if descripcion
                    else []
                ),
                *([accion] if accion else []),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=d.E2,
            tight=True,
        ),
        padding=ft.Padding.symmetric(vertical=d.E6, horizontal=d.E4),
        alignment=ft.Alignment.CENTER,
    )


@ft.component
def Esqueleto(alto: float = 16, ancho: float | None = None) -> ft.Control:
    p = paleta()
    return ft.Container(height=alto, width=ancho, bgcolor=p["fondo-sutil"], border_radius=d.R_SM, expand=True if ancho is None else None)


def ListaEsqueleto(filas: int = 4) -> ft.Control:
    return ft.Column([ft.Row([Esqueleto(alto=72)]) for _ in range(filas)], spacing=d.E2)


def Cargando(texto: str = "Cargando…") -> ft.Control:
    return ft.Row(
        [ft.ProgressRing(width=18, height=18, stroke_width=2), ft.Text(texto, size=d.T_SM)],
        spacing=d.E2,
    )


# --------------------------------------------------------------------------- #
# Botones
# --------------------------------------------------------------------------- #


def Boton(
    texto: str,
    al_pulsar: Accion = None,
    variante: str = "primario",
    cargando: bool = False,
    deshabilitado: bool = False,
    bloque: bool = False,
    grande: bool = False,
    icono: ft.IconData | None = None,
    ayuda: str | None = None,
) -> ft.Control:
    """Botón con las cuatro variantes de la web. Alto mínimo de 44 px: es el
    área táctil que exige el proyecto, y el mensajero lo pulsa con guantes."""
    contenido: ft.Control | str = texto
    if cargando:
        contenido = ft.Row(
            [ft.ProgressRing(width=16, height=16, stroke_width=2), ft.Text(texto)],
            spacing=d.E2,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )
    estilo = ft.ButtonStyle(
        padding=ft.Padding.symmetric(horizontal=d.E4, vertical=d.E3 if grande else d.E2),
        shape=ft.RoundedRectangleBorder(radius=d.R_MD),
        text_style=ft.TextStyle(size=d.T_MD if grande else d.T_SM, weight=ft.FontWeight.W_600),
    )
    comun = dict(
        content=contenido,
        icon=icono if not cargando else None,
        on_click=manejador(al_pulsar),
        disabled=deshabilitado or cargando,
        style=estilo,
        height=52 if grande else d.TACTIL,
        # `expand=False` explícito no equivale a omitirlo: Flet lo envuelve
        # igual, y dentro de una fila con salto de línea rompe el dibujo.
        expand=True if bloque else None,
        tooltip=ayuda,
    )
    if variante == "secundario":
        return ft.OutlinedButton(**comun)
    if variante == "sutil":
        return ft.TextButton(**comun)
    if variante == "peligro":
        estilo.bgcolor = ft.Colors.ERROR
        estilo.color = ft.Colors.ON_ERROR
        return ft.FilledButton(**comun)
    return ft.FilledButton(**comun)


def BotonIcono(icono: ft.IconData, al_pulsar: Accion, ayuda: str) -> ft.Control:
    return ft.IconButton(icono, on_click=manejador(al_pulsar), tooltip=ayuda, width=d.TACTIL, height=d.TACTIL)


@ft.component
def BotonCopiar(texto: str, etiqueta: str = "Copiar") -> ft.Control:
    copiado, set_copiado = ft.use_state(False)

    async def copiar():
        await ft.Clipboard().set(texto)
        set_copiado(True)

    return Boton("Copiado" if copiado else etiqueta, copiar, variante="secundario", icono=ft.Icons.COPY)


# --------------------------------------------------------------------------- #
# Formularios
# --------------------------------------------------------------------------- #


def Campo(
    etiqueta: str,
    valor: str,
    al_cambiar: Callable[[str], Any],
    ayuda: str | None = None,
    error: str | None = None,
    opcional: bool = False,
    contrasena: bool = False,
    teclado: ft.KeyboardType | None = None,
    sugerencia: str | None = None,
    multilinea: bool = False,
    filas: int = 3,
    al_enviar: Accion = None,
    autofoco: bool = False,
    solo_lectura: bool = False,
    autocompletar: Any = None,
) -> ft.Control:
    return ft.TextField(
        label=f"{etiqueta} (opcional)" if opcional else etiqueta,
        value=valor,
        on_change=lambda e: al_cambiar(e.control.value),
        on_submit=manejador(al_enviar),
        helper=None if error else ayuda,
        error=error,
        password=contrasena,
        can_reveal_password=contrasena,
        keyboard_type=teclado,
        hint_text=sugerencia,
        multiline=multilinea,
        min_lines=filas if multilinea else None,
        max_lines=filas + 3 if multilinea else 1,
        autofocus=autofoco,
        read_only=solo_lectura,
        autofill_hints=autocompletar,
        border_radius=d.R_MD,
        helper_max_lines=3,
        error_max_lines=3,
    )


def Selector(
    etiqueta: str,
    valor: str,
    opciones: Sequence[tuple[str, str]],
    al_cambiar: Callable[[str], Any],
    ayuda: str | None = None,
) -> ft.Control:
    """Desplegable. `opciones` son pares (valor, texto); el valor vacío se
    admite como «ninguno» y se muestra con su propio texto."""
    clave_vacia = "__ninguno__"
    # Va dentro de una fila para que `expand` lo estire a lo ancho: suelto en
    # una columna que se desplaza, se estiraría a lo alto sin límite.
    return ft.Row([ft.Dropdown(
        label=etiqueta,
        value=valor or clave_vacia,
        options=[ft.DropdownOption(key=v or clave_vacia, text=t) for v, t in opciones],
        on_select=lambda e: al_cambiar("" if e.control.value == clave_vacia else (e.control.value or "")),
        helper_text=ayuda,
        expand=True,
        border_radius=d.R_MD,
        menu_height=320,
    )])


@ft.component
def GrupoSegmentado(
    valor: str,
    opciones: Sequence[tuple[str, str]],
    al_cambiar: Callable[[str], Any],
    etiqueta: str | None = None,
) -> ft.Control:
    """Opciones excluyentes como botones, no como desplegable: un toque en lugar
    de tres. Se parten en varias líneas si no caben, en vez de desbordar."""
    p = paleta()
    botones = []
    for clave, texto in opciones:
        activo = clave == valor
        botones.append(
            ft.Container(
                content=ft.Text(
                    texto,
                    size=d.T_SM,
                    weight=ft.FontWeight.W_600,
                    color=p["acento-fuerte"] if activo else p["texto-suave"],
                ),
                padding=ft.Padding.symmetric(horizontal=d.E3, vertical=11),
                bgcolor=p["acento-suave"] if activo else p["superficie"],
                border=ft.Border.all(1, p["acento-borde"] if activo else p["borde"]),
                border_radius=d.R_MD,
                height=d.TACTIL - 4,
                on_click=lambda _e, c=clave: al_cambiar(c),
                ink=True,
            )
        )
    fila = ft.Row(botones, wrap=True, spacing=d.E1, run_spacing=d.E1)
    if not etiqueta:
        return fila
    return ft.Column(
        [ft.Text(etiqueta, size=d.T_XS, weight=ft.FontWeight.W_700, color=p["texto-suave"]), fila],
        spacing=d.E1,
        tight=True,
    )


def Casilla(etiqueta: str, valor: bool, al_cambiar: Callable[[bool], Any], ayuda: str | None = None) -> ft.Control:
    casilla = ft.Checkbox(value=valor, on_change=lambda e: al_cambiar(bool(e.control.value)))
    textos: list[ft.Control] = [ft.Text(etiqueta, size=d.T_SM, weight=ft.FontWeight.W_600)]
    if ayuda:
        textos.append(ft.Text(ayuda, size=d.T_XS, opacity=0.75))
    return ft.Container(
        content=ft.Row(
            [casilla, ft.Column(textos, spacing=2, expand=True, tight=True)],
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        on_click=lambda _e: al_cambiar(not valor),
    )


# --------------------------------------------------------------------------- #
# Etiquetas de estado
# --------------------------------------------------------------------------- #


@ft.component
def EtiquetaEstado(estado: str, codigo: int | None = None, con_punto: bool = False) -> ft.Control:
    """El estado con su código numérico: es lo que viaja en los archivos de
    intercambio, y quien concilia necesita ver el mismo número que en ellos.
    Nunca solo color: siempre lleva el texto."""
    p = paleta()
    color = d.color_de_estado(p, estado)
    partes: list[ft.Control] = []
    if con_punto:
        partes.append(ft.Container(width=8, height=8, bgcolor=color, border_radius=4))
    if codigo is not None:
        partes.append(ft.Text(str(codigo), size=d.T_XS, color=color, opacity=0.75, weight=ft.FontWeight.W_700))
    partes.append(ft.Text(texto_estado(estado), size=d.T_XS, color=color, weight=ft.FontWeight.W_700))
    return ft.Container(
        content=ft.Row(partes, spacing=d.E1, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=d.E2, vertical=2),
        bgcolor=d.fondo_de_estado(p, estado),
        border_radius=999,
    )


@ft.component
def Insignia(texto: str, tono: str = "acento") -> ft.Control:
    p = paleta()
    color = p.get(tono, p["acento"])
    fondo = p.get(f"{tono}-suave", p["fondo-sutil"])
    return ft.Container(
        content=ft.Text(texto, size=d.T_XS, color=color, weight=ft.FontWeight.W_700),
        padding=ft.Padding.symmetric(horizontal=d.E2, vertical=2),
        bgcolor=fondo,
        border_radius=999,
    )


def EtiquetaResultado(resultado: str) -> ft.Control:
    return Insignia(resultado, {"ALLOW": "exito", "DENY": "peligro", "ERROR": "alerta"}.get(resultado, "acento"))


# --------------------------------------------------------------------------- #
# Estructura de página
# --------------------------------------------------------------------------- #


@ft.component
def Encabezado(titulo: str, descripcion: str | None = None, acciones: Sequence[ft.Control] | None = None) -> ft.Control:
    p = paleta()
    textos: list[ft.Control] = [Titulo(titulo)]
    if descripcion:
        textos.append(ft.Text(descripcion, size=d.T_SM, color=p["texto-suave"], selectable=True))
    return ft.ResponsiveRow(
        [
            ft.Column(textos, spacing=d.E1, col={"xs": 12, "md": 8 if acciones else 12}, tight=True),
            *(
                [
                    ft.Row(
                        list(acciones),
                        wrap=True,
                        spacing=d.E2,
                        run_spacing=d.E2,
                        alignment=ft.MainAxisAlignment.END,
                        col={"xs": 12, "md": 4},
                    )
                ]
                if acciones
                else []
            ),
        ],
        breakpoints=d.PUNTOS_DE_CORTE,
        vertical_alignment=ft.CrossAxisAlignment.END,
        run_spacing=d.E3,
    )


def Rejilla(
    controles: Sequence[ft.Control],
    columnas: dict[str, int] | None = None,
    espacio: float = d.E3,
) -> ft.Control:
    """Rejilla responsive con los puntos de corte del proyecto. `columnas` dice
    cuántas de doce ocupa cada pieza en cada ancho."""
    columnas = columnas or {"xs": 12, "sm": 6, "lg": 3}
    return ft.ResponsiveRow(
        [ft.Container(content=c, col=columnas) for c in controles if c is not None],
        breakpoints=d.PUNTOS_DE_CORTE,
        spacing=espacio,
        run_spacing=espacio,
    )


def DoblePanel(izquierda: Sequence[ft.Control], derecha: Sequence[ft.Control]) -> ft.Control:
    """Dos columnas desde 1024 px; una sola, una debajo de otra, por debajo."""
    return ft.ResponsiveRow(
        [
            ft.Column(list(izquierda), spacing=d.E4, col={"xs": 12, "lg": 7}),
            ft.Column(list(derecha), spacing=d.E4, col={"xs": 12, "lg": 5}),
        ],
        breakpoints=d.PUNTOS_DE_CORTE,
        spacing=d.E4,
        run_spacing=d.E4,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


def Dato(termino: str, valor: str) -> ft.Control:
    return ft.Column(
        [
            ft.Text(termino.upper(), size=d.T_XS, weight=ft.FontWeight.W_700, opacity=0.6),
            ft.Text(valor, size=d.T_SM, selectable=True),
        ],
        spacing=2,
        tight=True,
    )


@ft.component
def TablaDesplazable(columnas: Sequence[str], filas: Sequence[Sequence[Any]], ancho_minimo: float = 560) -> ft.Control:
    """Una tabla que, si no cabe, se desplaza dentro de su contenedor y no
    empuja la página: no puede haber desplazamiento horizontal en la página."""
    p = paleta()
    tabla = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=d.T_XS, weight=ft.FontWeight.W_700)) for c in columnas],
        rows=[
            ft.DataRow(
                cells=[
                    # Un valor suelto (número, fecha, código) no se parte en
                    # varias líneas; el texto largo llega ya como control con su
                    # propio ancho.
                    ft.DataCell(c if isinstance(c, ft.BaseControl) else ft.Text(str(c), size=d.T_SM, selectable=True, no_wrap=True))
                    for c in fila
                ]
            )
            for fila in filas
        ],
        heading_row_height=40,
        data_row_min_height=40,
        column_spacing=d.E4,
        horizontal_lines=ft.BorderSide(1, p["borde"]),
    )
    return ft.Row([ft.Container(tabla, width=max(ancho_minimo, 0) or None)], scroll=ft.ScrollMode.AUTO)


# --------------------------------------------------------------------------- #
# Diálogos
# --------------------------------------------------------------------------- #


def use_modal(
    abierto: bool,
    titulo: str,
    contenido: Contenido,
    al_cerrar: Callable[[], Any],
    acciones: Sequence[ft.Control] | None = None,
    ayuda: str | None = None,
    ancho: float = 560,
    bloqueado: bool = False,
) -> None:
    """Un diálogo que se muestra mientras `abierto` sea cierto. Es un hook: se
    llama en cada render, abierto o no, para que el orden de los hooks no cambie.

    `bloqueado` impide cerrarlo tocando fuera mientras hay una operación en
    curso: cerrar a mitad de una carga dejaría la evidencia subida y sin
    registrar."""
    cabecera: list[ft.Control] = [ft.Text(titulo, size=d.T_LG, weight=ft.FontWeight.W_700)]
    if ayuda:
        cabecera.append(ft.Text(ayuda, size=d.T_SM, opacity=0.75))
    dialogo = None
    if abierto:
        dialogo = ft.AlertDialog(
            title=ft.Column(cabecera, spacing=d.E1, tight=True),
            content=ft.Container(
                ft.Column(
                    _controles(contenido),
                    spacing=d.E3,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                # A 360 px el diálogo no cabe con su ancho de escritorio: se
                # recorta al de la pantalla menos los márgenes del diálogo.
                width=max(240, min(ancho, (ft.context.page.width or ancho) - 64)),
            ),
            actions=list(acciones or []),
            modal=bloqueado,
            on_dismiss=lambda _e: al_cerrar(),
            scrollable=True,
        )
    ft.use_dialog(dialogo)


def use_confirmacion(
    abierto: bool,
    titulo: str,
    descripcion: str,
    texto_confirmar: str,
    al_confirmar: Accion,
    al_cancelar: Callable[[], Any],
    cargando: bool = False,
    peligro: bool = False,
) -> None:
    use_modal(
        abierto,
        titulo,
        ft.Text(descripcion, size=d.T_SM),
        al_cancelar,
        acciones=[
            Boton("Cancelar", al_cancelar, variante="secundario", deshabilitado=cargando),
            Boton(texto_confirmar, al_confirmar, variante="peligro" if peligro else "primario", cargando=cargando),
        ],
        ancho=440,
        bloqueado=cargando,
    )
