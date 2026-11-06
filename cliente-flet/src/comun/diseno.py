"""Sistema de diseño para Flet: colores, tema y medidas.

Los colores salen de `fichas.py`, que se genera desde `design/tokens.css`: el
sistema de diseño sigue siendo uno solo (ADR-008) y estas aplicaciones lo
traducen, no lo copian. Cada aplicación solo aporta su marca —Rastro el azul y
el cian del recorrido, Cotejo el índigo del examen—, igual que en la web.

Las medidas responsive son las del proyecto (`CLAUDE.md`): sm 640, md 768,
lg 1024, xl 1280. Flet trae otras por omisión (576, 768, 992, 1200); se
sustituyen para que una pantalla cambie de forma en el mismo ancho en la web y
aquí.
"""

from __future__ import annotations

import flet as ft

from comun.fichas import BASE, COLOR_POR_ESTADO, MARCAS

PUNTOS_DE_CORTE = {"xs": 0, "sm": 640, "md": 768, "lg": 1024, "xl": 1280, "xxl": 1536}

# Área táctil mínima exigida por las reglas del proyecto.
TACTIL = 44

# Escala de espacio: múltiplos de 4 px, como `--e-1` … `--e-7`.
E1, E2, E3, E4, E5, E6, E7 = 4, 8, 12, 16, 24, 32, 48

# Tipografía, como `--t-xs` … `--t-2xl` (1 rem = 16 px).
T_XS, T_SM, T_BASE, T_MD, T_LG, T_XL, T_2XL = 12, 13, 15, 16, 18, 22, 28

R_SM, R_MD, R_LG = 6, 10, 14

# Monoespaciada para identificadores, huellas y código. Va empaquetada en
# `assets/fuentes` (licencia OFL): en Flutter un nombre de familia no admite
# lista de respaldo como en CSS, y sin fuente propia el texto «mono» salía
# proporcional en la web.
FUENTE_MONO = "RobotoMono"
FUENTES = {FUENTE_MONO: "fuentes/RobotoMono.ttf"}


def colores(aplicacion: str, tema: str) -> dict[str, str]:
    """Las fichas de un tema («claro» u «oscuro») con la marca de la aplicación."""
    return {**BASE["claro"], **BASE[tema], **MARCAS[aplicacion][tema]}


def color_de_estado(paleta: dict[str, str], estado: str) -> str:
    return paleta[COLOR_POR_ESTADO.get(estado, "texto-tenue")]


def fondo_de_estado(paleta: dict[str, str], estado: str) -> str:
    ficha = COLOR_POR_ESTADO.get(estado, "texto-tenue")
    # Los estados de cierre que no son entrega usan el fondo sutil, no un tono
    # de alarma: un envío devuelto es un desenlace previsto, no un fallo.
    if ficha in ("texto-suave", "texto-tenue"):
        return paleta["fondo-sutil"]
    return paleta[f"{ficha}-suave"]


def tema_flet(aplicacion: str, tema: str) -> ft.Theme:
    c = colores(aplicacion, tema)
    esquema = ft.ColorScheme(
        primary=c["acento"],
        on_primary=c["texto-invertido"],
        primary_container=c["acento-suave"],
        on_primary_container=c["acento-fuerte"],
        secondary=c["marca-2"],
        on_secondary=c["marca-contraste"],
        error=c["peligro"],
        on_error=c["texto-invertido"],
        error_container=c["peligro-suave"],
        on_error_container=c["peligro"],
        surface=c["superficie"],
        on_surface=c["texto"],
        on_surface_variant=c["texto-suave"],
        surface_container_lowest=c["superficie"],
        surface_container_low=c["superficie-hundida"],
        surface_container=c["superficie"],
        surface_container_high=c["superficie-elevada"],
        surface_container_highest=c["fondo-sutil"],
        outline=c["borde-fuerte"],
        outline_variant=c["borde"],
        surface_tint=ft.Colors.TRANSPARENT,
    )
    return ft.Theme(
        color_scheme=esquema,
        scaffold_bgcolor=c["fondo"],
        card_bgcolor=c["superficie"],
        divider_color=c["borde"],
        visual_density=ft.VisualDensity.STANDARD,
    )
