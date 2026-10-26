"""Piezas propias de Cotejo, sobre las comunes de `comun/ui.py`.

Regla de redacción de toda esta interfaz, la misma que en la web: primero la
frase que se entiende sin haber estudiado auditoría, y pegado a ella el término
del oficio. El término técnico es lo que un tercero espera leer en un informe;
la frase llana es lo que permite que alguien decida sobre un hallazgo sin
necesitar un traductor.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from comun import diseno as d
from comun import ui

# Cada conclusión, en la palabra que se entiende sin diccionario. El servidor
# manda la suya con cada papel y esa es la que manda; esto es el respaldo para
# cuando todavía no hay papel —el catálogo, por ejemplo— y la fuente del color y
# el icono, que no viajan por la API.
RESPUESTAS = {
    "CONFORME": {
        "palabra": "BIEN",
        "explicacion": "Se probó y cumplió la regla que estaba escrita de antemano.",
        "icono": ft.Icons.VERIFIED_OUTLINED,
        "ficha": "exito",
    },
    "DESVIADO": {
        "palabra": "MAL",
        "explicacion": "Se probó y no cumplió. Esto se convierte en un hallazgo.",
        "icono": ft.Icons.WARNING_AMBER_OUTLINED,
        "ficha": "peligro",
    },
    "NO_EJECUTADA": {
        "palabra": "SIN REVISAR",
        "explicacion": "Ni bien ni mal: no se pudo probar aquí. Queda pendiente, no aprobado.",
        "icono": ft.Icons.SCHEDULE,
        "ficha": "texto-suave",
    },
}

# La severidad en palabra llana; el término del oficio va al lado.
SEVERIDADES = {"alta": ("grave", "peligro"), "media": ("importante", "alerta"), "baja": ("menor", "texto-suave")}


def colores_de_ficha(p: dict[str, str], ficha: str) -> tuple[str, str, str]:
    """Color, fondo y borde de una ficha. Lo que no es un aviso —sin revisar,
    severidad baja— va en gris: el rojo tiene que seguir significando «actuar»."""
    if ficha in ("texto-suave", "texto-tenue"):
        return p[ficha], p["fondo-sutil"], p["borde-fuerte"]
    return p[ficha], p[f"{ficha}-suave"], p[f"{ficha}-borde"]


@ft.component
def Tecnicismo(texto: str) -> ft.Control:
    """El término del oficio, pegado a la frase que lo explica."""
    p = ui.paleta()
    return ft.Text(f"· {texto}", size=d.T_XS, italic=True, color=p["texto-tenue"], selectable=True)


@ft.component
def ConTecnicismo(texto: str, tecnicismo: str, tono: str = "texto-suave", tamano: float = d.T_SM) -> ft.Control:
    """Una frase llana seguida de su término técnico, en el mismo párrafo."""
    p = ui.paleta()
    return ft.Text(
        spans=[
            ft.TextSpan(texto + " "),
            ft.TextSpan(
                f"· {tecnicismo}",
                ft.TextStyle(size=d.T_XS, italic=True, color=p["texto-tenue"]),
            ),
        ],
        size=tamano,
        color=p.get(tono, p["texto"]),
        selectable=True,
    )


@ft.component
def Respuesta(conclusion: str, palabra: str | None = None, grande: bool = False) -> ft.Control:
    """La respuesta de un control: palabra llana grande, término técnico al lado."""
    p = ui.paleta()
    base = RESPUESTAS.get(conclusion, RESPUESTAS["NO_EJECUTADA"])
    color, fondo, borde = colores_de_ficha(p, base["ficha"])
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(base["icono"], size=20 if grande else 15, color=color),
                ft.Text(palabra or base["palabra"], size=d.T_SM if grande else d.T_XS, weight=ft.FontWeight.W_800, color=color),
                ft.Text(
                    f"· {conclusion.replace('_', ' ').lower()}",
                    size=d.T_XS,
                    italic=True,
                    color=p["texto-tenue"],
                ),
            ],
            spacing=d.E2,
            tight=True,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E4 if grande else d.E3, vertical=d.E2 if grande else d.E1),
        bgcolor=fondo,
        border=ft.Border.all(1, borde),
        border_radius=999,
        tooltip=base["explicacion"],
    )


@ft.component
def EtiquetaSeveridad(severidad: str, solo_dos: bool = False) -> ft.Control:
    """`solo_dos`: el catálogo solo distingue grave e importante, como la web."""
    p = ui.paleta()
    palabra, ficha = SEVERIDADES.get(severidad, ("menor", "texto-suave"))
    if solo_dos and severidad != "alta":
        palabra = "importante"
    color, fondo, _ = colores_de_ficha(p, ficha)
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(palabra, size=d.T_XS, weight=ft.FontWeight.W_700, color=color),
                ft.Text(f"· severidad {severidad}", size=d.T_XS, italic=True, color=p["texto-tenue"]),
            ],
            spacing=d.E1,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=d.E2, vertical=2),
        bgcolor=fondo,
        border_radius=999,
    )


def CampoHallazgo(termino: str, valor: Any) -> ft.Control:
    contenido = valor if isinstance(valor, ft.BaseControl) else ft.Text(str(valor or "—"), size=d.T_SM, selectable=True)
    return ft.Column(
        [ft.Text(termino.upper(), size=d.T_XS, weight=ft.FontWeight.W_700, opacity=0.6), contenido],
        spacing=2,
        tight=True,
    )


@ft.component
def DetalleTecnico(contenido: list[ft.Control], resumen: str = "Ver el registro técnico") -> ft.Control:
    """Bloque plegado con el registro técnico. Cerrado por omisión: quien lo
    necesita sabe que existe, y quien no, no tropieza con él."""
    p = ui.paleta()
    abierto, poner_abierto = ft.use_state(False)
    cabecera = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.EXPAND_LESS if abierto else ft.Icons.EXPAND_MORE, size=18, color=p["acento"]),
                ft.Text(resumen, size=d.T_SM, weight=ft.FontWeight.W_600, color=p["acento"]),
            ],
            spacing=d.E1,
            tight=True,
        ),
        height=d.TACTIL,
        on_click=lambda _e: poner_abierto(not abierto),
        ink=True,
        border_radius=d.R_SM,
    )
    partes: list[ft.Control] = [cabecera]
    if abierto:
        partes.append(
            ft.Container(
                content=ft.Column(contenido, spacing=d.E3, tight=True),
                padding=d.E3,
                bgcolor=p["superficie-hundida"],
                border=ft.Border.all(1, p["borde"]),
                border_radius=d.R_MD,
            )
        )
    return ft.Column(partes, spacing=d.E1, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


@ft.component
def Bloque(titulo: str, contenido: list[ft.Control]) -> ft.Control:
    """Un apartado del papel de trabajo: «Qué se hizo», «Qué contestó Rastro»..."""
    p = ui.paleta()
    return ft.Container(
        content=ft.Column(
            [ft.Text(titulo, size=d.T_MD, weight=ft.FontWeight.W_700), *contenido],
            spacing=d.E2,
            tight=True,
        ),
        padding=d.E4,
        bgcolor=p["superficie-hundida"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_MD,
    )


@ft.component
def TextoMono(texto: str, tamano: float = d.T_XS, tono: str = "texto") -> ft.Control:
    p = ui.paleta()
    return ft.Text(texto, size=tamano, font_family=d.FUENTE_MONO, color=p.get(tono, p["texto"]), selectable=True)


@ft.component
def Preformateado(texto: str, alto_maximo: float = 448) -> ft.Control:
    """Texto tal cual, en monoespaciado. Si no cabe, se desplaza dentro de su
    caja —vertical y horizontalmente— y no empuja la página."""
    p = ui.paleta()
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [ft.Text(texto, size=d.T_XS, font_family=d.FUENTE_MONO, selectable=True, no_wrap=True)],
                    scroll=ft.ScrollMode.AUTO,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=d.E3,
        height=alto_maximo if texto.count("\n") > 24 else None,
        bgcolor=p["superficie"],
        border=ft.Border.all(1, p["borde"]),
        border_radius=d.R_MD,
    )
