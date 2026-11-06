"""Transmisión de la ubicación: cuándo se encola, cuándo se envía y qué se
descarta. Las reglas de `web/src/api/transmision.ts`."""

import asyncio

from comun.http import ErrorApi
from rastro_app import ubicacion
from rastro_app.ubicacion import Transmisor, distancia_metros


class PaginaFalsa:
    def __init__(self):
        self.tareas = []

    def run_task(self, funcion):
        self.tareas.append(funcion)


class ApiFalsa:
    def __init__(self, fallo=None):
        self.fallo = fallo
        self.lotes = []

    async def reportar_posiciones(self, ruta_id, lote):
        if self.fallo:
            raise self.fallo
        self.lotes.append(list(lote))
        return {"recibidas": len(lote)}


def transmisor(api=None):
    terminadas = []
    pagina = PaginaFalsa()
    t = Transmisor(pagina, api or ApiFalsa(), None, "ruta-1", lambda _estado: None, lambda: terminadas.append(True))
    return t, pagina, terminadas


def lectura(lat, lon, precision=8.0):
    return {"lat": lat, "lon": lon, "precision_m": precision, "capturada_en": "2026-10-26T12:00:00Z"}


def test_distancia_en_metros():
    # Un grado de latitud son unos 111 km.
    assert 110_000 < distancia_metros({"lat": 4.0, "lon": -74.0}, {"lat": 5.0, "lon": -74.0}) < 112_000


def test_la_primera_lectura_se_encola_y_las_siguientes_esperan(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(ubicacion.time, "monotonic", lambda: reloj[0])
    t, pagina, _ = transmisor()

    t.al_leer(lectura(4.65, -74.08))
    assert len(t.cola) == 1 and len(pagina.tareas) == 1

    reloj[0] += 6  # seis segundos, casi quieto: no se envía todavía
    t.al_leer(lectura(4.65001, -74.08))
    assert len(t.cola) == 1

    reloj[0] += 10  # ya pasaron quince segundos desde la última encolada
    t.al_leer(lectura(4.65002, -74.08))
    assert len(t.cola) == 2


def test_un_movimiento_grande_adelanta_el_envio(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(ubicacion.time, "monotonic", lambda: reloj[0])
    t, _pagina, _ = transmisor()
    t.al_leer(lectura(4.65, -74.08))
    reloj[0] += 6
    t.al_leer(lectura(4.6515, -74.08))  # unos 166 m en seis segundos
    assert len(t.cola) == 2


def test_una_lectura_imprecisa_no_se_envia(monkeypatch):
    monkeypatch.setattr(ubicacion.time, "monotonic", lambda: 1000.0)
    t, _pagina, _ = transmisor()
    t.al_leer(lectura(4.65, -74.08, precision=1500))
    assert t.cola == []
    assert t.estado["posicion"]["precision_m"] == 1500


def test_sin_conexion_se_conserva_la_cola():
    t, _pagina, _ = transmisor(ApiFalsa(fallo=ErrorApi(0, "SIN_CONEXION", "sin red")))
    t.cola = [lectura(4.65, -74.08)]
    asyncio.run(t.enviar())
    assert len(t.cola) == 1 and t.estado["sin_conexion"] is True


def test_una_ruta_cerrada_detiene_la_transmision():
    t, _pagina, terminadas = transmisor(ApiFalsa(fallo=ErrorApi(409, "CONFLICTO", "La ruta ya terminó.")))
    t.cola = [lectura(4.65, -74.08)]
    asyncio.run(t.enviar())
    assert t.cola == [] and t.estado["estado"] == "detenida" and terminadas == [True]


def test_un_lote_rechazado_se_descarta_para_no_bloquear_los_siguientes():
    t, _pagina, _ = transmisor(ApiFalsa(fallo=ErrorApi(400, "SOLICITUD_INVALIDA", "Lectura inválida.")))
    t.cola = [lectura(4.65, -74.08)]
    asyncio.run(t.enviar())
    assert t.cola == []


def test_se_envia_en_lotes_de_sesenta():
    api = ApiFalsa()
    t, _pagina, _ = transmisor(api)
    t.cola = [lectura(4.65, -74.08)] * 130
    asyncio.run(t.enviar())
    assert len(api.lotes[0]) == 60 and len(t.cola) == 70
