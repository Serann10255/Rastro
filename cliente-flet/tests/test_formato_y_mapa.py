"""Fechas legibles y encuadre del mapa."""

from datetime import datetime, timezone

from comun.formato import antiguedad, fecha_relativa
from rastro_app.mapa import ZOOM_DE_UN_PUNTO, encuadrar

AHORA = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def test_fecha_relativa():
    assert fecha_relativa("2026-10-26T11:59:58Z", AHORA) == "ahora"
    assert fecha_relativa("2026-10-26T11:55:00Z", AHORA) == "hace 5 minutos"
    assert fecha_relativa("2026-10-25T12:00:00Z", AHORA) == "ayer"
    assert fecha_relativa("2026-10-20T12:00:00Z", AHORA) == "hace 6 días"
    assert fecha_relativa("no es una fecha", AHORA) == ""


def test_antiguedad_en_segundos():
    assert antiguedad(None) == "sin datos"
    assert antiguedad(3) == "ahora"
    assert antiguedad(12) == "hace 12 s"
    assert antiguedad(185) == "hace 3 min"
    assert antiguedad(3 * 3600 + 120) == "hace 3 h 2 min"


def test_un_punto_se_muestra_de_cerca():
    centro, zoom = encuadrar([(4.65, -74.08)], 600, 340)
    assert centro == (4.65, -74.08) and zoom == ZOOM_DE_UN_PUNTO


def test_dos_puntos_quedan_en_el_centro_y_caben():
    centro, zoom = encuadrar([(4.60, -74.10), (4.70, -74.00)], 600, 340)
    assert abs(centro[0] - 4.65) < 0.01 and abs(centro[1] + 74.05) < 1e-9
    # A ese zoom, 0,1° de longitud tiene que caber en el ancho útil (600 - 72).
    assert 0.1 / 360 * 256 * 2**zoom <= 600 - 72 + 1


def test_puntos_lejanos_alejan_la_vista():
    _c, cerca = encuadrar([(4.60, -74.10), (4.61, -74.09)], 600, 340)
    _c, lejos = encuadrar([(4.60, -74.10), (6.25, -75.56)], 600, 340)
    assert lejos < cerca
