"""Diccionario: las palabras del oficio, explicadas.

No se sustituyen por otras más fáciles —son las que espera leer quien reciba el
informe—, pero nadie debería necesitar aprendérselas para entender lo que dice
una pantalla. Vienen del catálogo, como el resto de las explicaciones.
"""

from __future__ import annotations

import flet as ft

from comun import diseno as d
from comun import ui
from cotejo_app.contexto import mensaje_de_error, use_consola


@ft.component
def Entrada(termino: str, alias: str | None, definicion: str) -> ft.Control:
    p = ui.paleta()
    titulo: list[ft.Control] = [ft.Text(termino, size=d.T_MD, weight=ft.FontWeight.W_700, selectable=True)]
    if alias:
        titulo.append(ft.Text(f"también: {alias}", size=d.T_XS, italic=True, color=p["texto-tenue"]))
    return ft.Container(
        content=ft.Column([*titulo, ft.Text(definicion, size=d.T_SM, color=p["texto-suave"], selectable=True)], spacing=d.E1),
        padding=ft.Padding.symmetric(vertical=d.E3),
        border=ft.Border(bottom=ft.BorderSide(1, p["borde"])),
    )


@ft.component
def VistaGlosario() -> ft.Control:
    consola = use_consola()
    consulta = consola.catalogo
    if consulta is None or (consulta.cargando and not consulta.datos):
        return ui.Esqueleto(alto=320)
    if consulta.error and not consulta.datos:
        return ui.Aviso(mensaje_de_error(consulta.error), tono="error")
    glosario = (consulta.datos or {}).get("glosario", [])

    return ft.Column(
        [
            ui.Encabezado(
                "Diccionario",
                "Las palabras del oficio, explicadas. No se sustituyen por otras más fáciles: son las que espera "
                "leer quien reciba el informe. Pero nadie debería necesitar aprendérselas para entender lo que "
                "dice una pantalla.",
            ),
            ui.Tarjeta(
                [
                    Entrada(e["termino"], e.get("tambien_llamado"), e.get("en_simple", ""), key=e["termino"])
                    for e in glosario
                ]
                or ui.Vacio("El catálogo no trae diccionario")
            ),
        ],
        spacing=d.E4,
    )
