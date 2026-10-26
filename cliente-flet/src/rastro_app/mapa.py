"""Mapa de posiciones: conductores en ruta, su recorrido y la posición pública.

En la web el mapa es Leaflet (ADR-014); aquí es `flet-map`, que envuelve
`flutter_map`. La razón es la misma: dibujar teselas, arrastrar, hacer zoom con
dos dedos y proyectar coordenadas es un problema resuelto, y resolverlo de nuevo
sería código propio, sí, pero peor y sin revisar. Las teselas son las mismas
(OpenStreetMap, o las que diga `teselas` en la configuración).

El mapa no es la única forma de leer la información: cada pantalla que lo usa
dice también con texto quién está dónde y hace cuánto.

Comportamiento, igual que en la web:
- Al cambiar `encuadre` se vuelve a encuadrar todo (por ejemplo, al elegir otra
  ruta).
- Con `seguir`, la vista acompaña a ese marcador mientras el usuario no mueva el
  mapa; si lo mueve, aparece «Centrar» y la vista deja de moverse sola.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import flet as ft
import flet_map as fm

from comun import diseno as d
from comun import ui

ZOOM_DE_UN_PUNTO = 16
TESELAS_POR_OMISION = {
    "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "atribucion": "© OpenStreetMap",
}


@dataclass(frozen=True)
class Marcador:
    id: str
    lat: float
    lon: float
    etiqueta: str | None = None
    tono: str = "acento"
    precision: float | None = None
    seleccionado: bool = False


@dataclass(frozen=True)
class Trazo:
    id: str
    puntos: tuple[tuple[float, float], ...]
    tono: str = "acento"


def encuadrar(puntos: list[tuple[float, float]], ancho_px: float, alto_px: float, margen_px: float = 36) -> tuple[tuple[float, float], float]:
    """Centro y zoom para que todos los puntos quepan en el mapa.

    `flutter_map` ofrece un encuadre automático, pero con él las teselas no
    se dibujan en el cliente de Flet; se calcula aquí con la proyección de
    Mercator, que es la de las teselas, y se entrega como centro y zoom."""
    if len(puntos) == 1:
        return puntos[0], ZOOM_DE_UN_PUNTO

    def y_mercator(lat: float) -> float:
        lat = max(min(lat, 85.0), -85.0)
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    lats = [lat for lat, _lon in puntos]
    lons = [lon for _lat, lon in puntos]
    y_min, y_max = y_mercator(min(lats)), y_mercator(max(lats))
    centro_y = (y_min + y_max) / 2
    centro = (math.degrees(2 * math.atan(math.exp(centro_y)) - math.pi / 2), (min(lons) + max(lons)) / 2)

    util_x = max(ancho_px - 2 * margen_px, 64)
    util_y = max(alto_px - 2 * margen_px, 64)
    # A zoom z el mundo mide 256·2^z píxeles: 360° de longitud y 2π en y.
    zoom_x = math.log2(util_x * 360 / (256 * max(max(lons) - min(lons), 1e-6)))
    zoom_y = math.log2(util_y * 2 * math.pi / (256 * max(y_max - y_min, 1e-9)))
    return centro, max(2.0, min(zoom_x, zoom_y, ZOOM_DE_UN_PUNTO))


def _color(p: dict[str, str], tono: str) -> str:
    return {"exito": p["exito"], "alerta": p["alerta"], "tenue": p["texto-tenue"]}.get(tono, p["acento"])


@ft.component
def Mapa(
    marcadores: tuple[Marcador, ...],
    trazos: tuple[Trazo, ...] = (),
    encuadre: str = "inicial",
    seguir: str | None = None,
    teselas: dict | None = None,
    alto: float = 340,
    ancho: float = 640,
    al_seleccionar=None,
) -> ft.Control:
    """`ancho` es el ancho aproximado que tendrá el mapa en pantalla; solo se
    usa para elegir el zoom del encuadre inicial."""
    p = ui.paleta()
    libre, poner_libre = ft.use_state(False)
    # Volver a encuadrar es volver a montar el mapa con su encuadre inicial: la
    # cuenta cambia la clave del control y Flutter lo crea de nuevo.
    reencuadres, poner_reencuadres = ft.use_state(0)
    referencia = ft.use_ref(None)
    teselas = teselas or TESELAS_POR_OMISION

    puntos = [(m.lat, m.lon) for m in marcadores] + [punto for t in trazos for punto in t.puntos]
    if not puntos:
        return ft.Container(
            ui.Texto("El mapa aparece con la primera posición.", tono="texto-suave"),
            height=alto,
            alignment=ft.Alignment.CENTER,
            border_radius=d.R_LG,
            bgcolor=p["fondo-sutil"],
        )

    objetivo = next((m for m in marcadores if m.id == seguir), None) if seguir else None

    async def acompanar():
        # Solo los gestos del usuario sueltan la vista; los movimientos que hace
        # el propio componente no traen gesto.
        mapa = referencia.current
        if objetivo is None or libre or mapa is None:
            return
        try:
            await mapa.move_to(fm.MapLatitudeLongitude(objetivo.lat, objetivo.lon), animation_duration=ft.Duration(milliseconds=600))
        except Exception:  # noqa: BLE001 - el mapa puede no estar montado todavía
            pass

    ft.use_effect(acompanar, [objetivo.lat if objetivo else None, objetivo.lon if objetivo else None, libre], cleanup=lambda: None)

    def al_mover(evento):
        if getattr(evento, "has_gesture", False) and not libre:
            poner_libre(True)

    halos = [
        fm.CircleMarker(
            radius=m.precision,
            coordinates=fm.MapLatitudeLongitude(m.lat, m.lon),
            color=ft.Colors.with_opacity(0.12, _color(p, m.tono)),
            border_color=ft.Colors.with_opacity(0.4, _color(p, m.tono)),
            border_stroke_width=1,
            use_radius_in_meter=True,
        )
        for m in marcadores
        if m.precision
    ]
    lineas = [
        fm.PolylineMarker(
            coordinates=[fm.MapLatitudeLongitude(lat, lon) for lat, lon in t.puntos],
            color=_color(p, t.tono),
            stroke_width=4,
        )
        for t in trazos
        if len(t.puntos) > 1
    ]
    capas: list = [
        fm.TileLayer(url_template=teselas["url"], user_agent_package_name="co.rastro.cliente", max_native_zoom=19),
        fm.CircleLayer(circles=halos),
        fm.PolylineLayer(polylines=lineas),
        fm.MarkerLayer(markers=[_marcador(p, m, al_seleccionar) for m in marcadores]),
        fm.SimpleAttribution(text=teselas.get("atribucion", "© OpenStreetMap")),
    ]
    centro, zoom = encuadrar(puntos, ancho, alto)
    camara = {"initial_center": fm.MapLatitudeLongitude(*centro), "initial_zoom": zoom}

    mapa = fm.Map(
        layers=capas,
        on_position_change=al_mover,
        bgcolor=p["fondo-sutil"],
        expand=True,
        ref=referencia,
        key=f"{encuadre}-{reencuadres}",
        **camara,
    )

    def recentrar():
        poner_libre(False)
        poner_reencuadres(reencuadres + 1)

    return ft.Container(
        content=ft.Stack(
            [
                mapa,
                *(
                    [ft.Container(ui.Boton("Centrar", recentrar, variante="secundario", icono=ft.Icons.CENTER_FOCUS_STRONG), right=8, top=8)]
                    if libre
                    else []
                ),
            ],
            expand=True,
        ),
        height=alto,
        border_radius=d.R_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        border=ft.Border.all(1, p["borde"]),
    )


def _marcador(p: dict[str, str], m: Marcador, al_seleccionar) -> fm.Marker:
    color = _color(p, m.tono)
    punto = ft.Container(
        width=18 if m.seleccionado else 14,
        height=18 if m.seleccionado else 14,
        bgcolor=color,
        border=ft.Border.all(3, "#ffffff"),
        border_radius=10,
        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.4, "#000000")),
    )
    if not m.etiqueta:
        return fm.Marker(content=ft.Container(punto, tooltip=m.id), coordinates=fm.MapLatitudeLongitude(m.lat, m.lon), width=24, height=24)
    # Con rótulo, el marcador va por encima del punto: rótulo arriba y el punto
    # en el borde inferior, sobre la coordenada.
    contenido = ft.Column(
        [
            ft.Container(
                ft.Text(m.etiqueta, size=11, weight=ft.FontWeight.W_700, color=p["texto"], no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                bgcolor=p["superficie"],
                border=ft.Border.all(1, color),
                border_radius=6,
            ),
            punto,
        ],
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    return fm.Marker(
        content=ft.Container(contenido, on_click=(lambda _e: al_seleccionar(m.id)) if al_seleccionar else None),
        coordinates=fm.MapLatitudeLongitude(m.lat, m.lon),
        width=160,
        height=48,
        alignment=ft.Alignment.TOP_CENTER,
    )
