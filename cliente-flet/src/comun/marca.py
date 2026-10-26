"""Logotipos de Rastro y Cotejo, dibujados con el lienzo de Flet.

Son los trazados de `design/marca/rastro.tsx` y `design/marca/cotejo.tsx`, en el
mismo sistema de coordenadas (48 × 48) y con el mismo degradado de la marca.
Se dibujan en lugar de cargarse como imagen para que tomen el color del tema
vigente, como el SVG de la web.
"""

from __future__ import annotations

import flet as ft
import flet.canvas as cv

from comun import ui


def _pintura(p: dict[str, str], s: float, grosor: float = 0, relleno: bool = False, opacidad: float = 1.0) -> ft.Paint:
    colores = [p["marca-1"], p["marca-2"]]
    if opacidad < 1:
        colores = [ft.Colors.with_opacity(opacidad, c) for c in colores]
    return ft.Paint(
        gradient=ft.PaintLinearGradient(begin=(0, 0), end=(48 * s, 48 * s), colors=colores),
        stroke_width=grosor * s,
        style=ft.PaintingStyle.FILL if relleno else ft.PaintingStyle.STROKE,
        stroke_cap=ft.StrokeCap.ROUND,
        stroke_join=ft.StrokeJoin.ROUND,
    )


def _esquinas(s: float) -> list[cv.Path.PathElement]:
    """La caja de Rastro: esquinas marcadas y lados abiertos."""
    e: list[cv.Path.PathElement] = []
    for (x0, y0), (cx, cy), (x1, y1) in (
        ((14, 5), (5, 5), (5, 14)),
        ((34, 5), (43, 5), (43, 14)),
        ((14, 43), (5, 43), (5, 34)),
        ((34, 43), (43, 43), (43, 34)),
    ):
        # Recta hasta 4 unidades de la esquina y curva hasta el otro lado.
        ax = cx + (4 if x0 > cx else -4)
        ay = cy + (4 if y1 > cy else -4)
        e += [
            cv.Path.MoveTo(x0 * s, y0 * s),
            cv.Path.LineTo(ax * s, cy * s),
            cv.Path.QuadraticTo(cx * s, cy * s, cx * s, ay * s),
            cv.Path.LineTo(x1 * s, y1 * s),
        ]
    return e


@ft.component
def LogotipoRastro(tamano: float = 32) -> ft.Control:
    p = ui.paleta()
    s = tamano / 48
    return cv.Canvas(
        width=tamano,
        height=tamano,
        shapes=[
            cv.Path(_esquinas(s), paint=_pintura(p, s, 3)),
            cv.Path(
                [cv.Path.MoveTo(13 * s, 33 * s), cv.Path.LineTo(24 * s, 24 * s), cv.Path.LineTo(35 * s, 15 * s)],
                paint=_pintura(p, s, 3, opacidad=0.35),
            ),
            cv.Circle(13 * s, 33 * s, 3.4 * s, paint=_pintura(p, s, 2.6)),
            cv.Circle(24 * s, 24 * s, 3.4 * s, paint=_pintura(p, s, relleno=True, opacidad=0.55)),
            cv.Circle(35 * s, 15 * s, 5.6 * s, paint=_pintura(p, s, relleno=True)),
            cv.Path(
                [
                    cv.Path.MoveTo(32.6 * s, 15.1 * s),
                    cv.Path.LineTo(34.4 * s, 16.9 * s),
                    cv.Path.LineTo(37.6 * s, 13.3 * s),
                ],
                paint=ft.Paint(
                    color=p["marca-contraste"],
                    stroke_width=1.8 * s,
                    style=ft.PaintingStyle.STROKE,
                    stroke_cap=ft.StrokeCap.ROUND,
                    stroke_join=ft.StrokeJoin.ROUND,
                ),
            ),
        ],
    )


@ft.component
def LogotipoCotejo(tamano: float = 32) -> ft.Control:
    """Dos papeles de trabajo, el de delante con su lista cotejada."""
    p = ui.paleta()
    s = tamano / 48
    return cv.Canvas(
        width=tamano,
        height=tamano,
        shapes=[
            cv.Rect(8 * s, 6 * s, 22 * s, 28 * s, border_radius=3 * s, paint=_pintura(p, s, 2.4, opacidad=0.4)),
            cv.Rect(16 * s, 12 * s, 22 * s, 28 * s, border_radius=3 * s, paint=ft.Paint(color=p["superficie"])),
            cv.Rect(16 * s, 12 * s, 22 * s, 28 * s, border_radius=3 * s, paint=_pintura(p, s, 2.4)),
            cv.Path(
                [
                    cv.Path.MoveTo(21 * s, 20 * s),
                    cv.Path.LineTo(33 * s, 20 * s),
                    cv.Path.MoveTo(21 * s, 25 * s),
                    cv.Path.LineTo(33 * s, 25 * s),
                    cv.Path.MoveTo(21 * s, 30 * s),
                    cv.Path.LineTo(28 * s, 30 * s),
                ],
                paint=_pintura(p, s, 2, opacidad=0.45),
            ),
            cv.Path(
                [cv.Path.MoveTo(20.5 * s, 26.5 * s), cv.Path.LineTo(25.5 * s, 31.5 * s), cv.Path.LineTo(35 * s, 20.5 * s)],
                paint=_pintura(p, s, 3.4),
            ),
            cv.Circle(9 * s, 41 * s, 2.6 * s, paint=_pintura(p, s, 2)),
            cv.Circle(17 * s, 41 * s, 2.6 * s, paint=_pintura(p, s, 2)),
            cv.Path([cv.Path.MoveTo(11.6 * s, 41 * s), cv.Path.LineTo(14.4 * s, 41 * s)], paint=_pintura(p, s, 2)),
        ],
    )
