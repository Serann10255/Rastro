"""Genera los iconos de las aplicaciones (`src/assets/iconos/*.png`).

Dibuja los mismos trazados que `design/marca/rastro.tsx` y `cotejo.tsx` (y que
`comun/marca.py`), sobre el fondo de cada marca, a 1024 × 1024. `flet build`
los usa para el icono del APK y de escritorio. Los PNG se versionan; este
programa solo hace falta si cambia el logotipo.

Uso, desde la raíz del repositorio (requiere Pillow, dependencia de desarrollo):

    cliente-flet/.venv/Scripts/python cliente-flet/herramientas/generar_iconos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from comun.fichas import MARCAS  # noqa: E402

DESTINO = Path(__file__).resolve().parents[1] / "src" / "assets" / "iconos"
LADO = 1024
# El logotipo ocupa el centro: Android recorta el icono adaptable en círculo.
ESCALA = LADO * 0.62 / 48
DESPLAZAMIENTO = (LADO - 48 * ESCALA) / 2


def _hex(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _p(x: float, y: float) -> tuple[float, float]:
    return DESPLAZAMIENTO + x * ESCALA, DESPLAZAMIENTO + y * ESCALA


def _degradado(marca: dict[str, str]) -> Image.Image:
    """El degradado de la marca en diagonal, como el `linearGradient` del SVG."""
    a, b = _hex(marca["marca-1"]), _hex(marca["marca-2"])
    capa = Image.new("RGB", (LADO, LADO))
    pixeles = capa.load()
    for y in range(LADO):
        for x in range(LADO):
            t = (x + y) / (2 * LADO)
            pixeles[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return capa


def _trazo(dibujo: ImageDraw.ImageDraw, puntos, grosor: float, alfa: int = 255) -> None:
    ancho = round(grosor * ESCALA)
    dibujo.line([_p(*p) for p in puntos], fill=alfa, width=ancho, joint="curve")
    for p in (puntos[0], puntos[-1]):
        x, y = _p(*p)
        r = ancho / 2
        dibujo.ellipse((x - r, y - r, x + r, y + r), fill=alfa)


def _circulo(dibujo: ImageDraw.ImageDraw, cx, cy, r, alfa=255, grosor: float | None = None) -> None:
    x, y = _p(cx, cy)
    radio = r * ESCALA
    caja = (x - radio, y - radio, x + radio, y + radio)
    if grosor:
        dibujo.ellipse(caja, outline=alfa, width=round(grosor * ESCALA))
    else:
        dibujo.ellipse(caja, fill=alfa)


def rastro() -> Image.Image:
    marca = MARCAS["rastro"]["claro"]
    mascara = Image.new("L", (LADO, LADO), 0)
    m = ImageDraw.Draw(mascara)
    # La caja: esquinas marcadas, lados abiertos.
    for esquina in (
        [(14, 5), (9, 5), (5, 9), (5, 14)],
        [(34, 5), (39, 5), (43, 9), (43, 14)],
        [(14, 43), (9, 43), (5, 39), (5, 34)],
        [(34, 43), (39, 43), (43, 39), (43, 34)],
    ):
        _trazo(m, esquina, 3)
    _trazo(m, [(13, 33), (24, 24), (35, 15)], 3, alfa=90)
    _circulo(m, 13, 33, 3.4, grosor=2.6)
    _circulo(m, 24, 24, 3.4, alfa=140)
    _circulo(m, 35, 15, 5.6)

    icono = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    icono.paste(_degradado(marca), (0, 0), mascara)
    # La marca de entregado, en blanco sobre el círculo macizo.
    ImageDraw.Draw(icono).line([_p(32.6, 15.1), _p(34.4, 16.9), _p(37.6, 13.3)], fill=(255, 255, 255), width=round(1.8 * ESCALA), joint="curve")
    return icono


def cotejo() -> Image.Image:
    marca = MARCAS["cotejo"]["claro"]
    mascara = Image.new("L", (LADO, LADO), 0)
    m = ImageDraw.Draw(mascara)
    radio = round(3 * ESCALA)
    m.rounded_rectangle((*_p(8, 6), *_p(30, 34)), radius=radio, outline=100, width=round(2.4 * ESCALA))
    # El papel de delante es opaco: tapa al de atrás, como en el SVG.
    m.rounded_rectangle((*_p(16, 12), *_p(38, 40)), radius=radio, fill=0, outline=255, width=round(2.4 * ESCALA))
    for y, x_fin in ((20, 33), (25, 33), (30, 28)):
        _trazo(m, [(21, y), (x_fin, y)], 2, alfa=115)
    _trazo(m, [(20.5, 26.5), (25.5, 31.5), (35, 20.5)], 3.4)
    _circulo(m, 9, 41, 2.6, grosor=2)
    _circulo(m, 17, 41, 2.6, grosor=2)
    _trazo(m, [(11.6, 41), (14.4, 41)], 2)

    icono = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    icono.paste(_degradado(marca), (0, 0), mascara)
    return icono


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, generar in (("rastro", rastro), ("cotejo", cotejo)):
        generar().save(DESTINO / f"{nombre}.png", optimize=True)
        print(f"escrito {DESTINO / (nombre + '.png')}", file=sys.stderr)
