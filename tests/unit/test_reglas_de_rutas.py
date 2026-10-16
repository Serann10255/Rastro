"""Reglas de las rutas de entrega que no dependen de los servicios.

Fijan lo que ninguna pantalla deja ver: por que caminos sale un envio a ruta,
que hora vale para una posicion, que ve el destinatario y como un rol guardado
antes de que existieran las rutas recibe los permisos nuevos sin perder lo que
la empresa decidio.
"""

from __future__ import annotations

import datetime as dt

import pytest

from rastro_core.authz import (
    CATALOGO_FUNDACIONAL,
    ROLES_INTEGRADOS,
    Operacion,
    operaciones_nuevas_para,
)
from rastro_core.errors import ValidacionError
from rastro_core.rutas import (
    ESTADOS_APTOS_PARA_RUTA,
    VIGENCIA_PUBLICA_SEGUNDOS,
    camino_a_reparto,
    normalizar_posicion,
    posterior_a,
    resumen,
    senal,
    ubicacion_publica,
)
from rastro_core.state_machine import Estado, es_transicion_valida

AHORA = dt.datetime(2026, 10, 16, 15, 0, 0, tzinfo=dt.timezone.utc)


def _iso(hora: dt.datetime) -> str:
    return hora.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _hace(segundos: int) -> str:
    return _iso(AHORA - dt.timedelta(seconds=segundos))


# --------------------------------------------------------------------------- #
# Camino a reparto
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("origen", "esperado"),
    [
        (Estado.RECOLECTADO, (Estado.EN_TRANSITO, Estado.EN_REPARTO)),
        (Estado.EN_TRANSITO, (Estado.EN_REPARTO,)),
        (Estado.EN_REPARTO, ()),
    ],
)
def test_cada_envio_apto_llega_a_reparto_por_transiciones_validas(origen, esperado):
    camino = camino_a_reparto(origen)

    assert camino == esperado
    actual = origen
    for siguiente in camino:
        assert es_transicion_valida(actual, siguiente), f"{actual} -> {siguiente}"
        actual = siguiente


@pytest.mark.parametrize(
    "estado", [e for e in Estado if e not in ESTADOS_APTOS_PARA_RUTA], ids=str
)
def test_lo_que_el_conductor_no_tiene_en_su_poder_no_sale_a_ruta(estado):
    with pytest.raises(ValidacionError):
        camino_a_reparto(estado)


def test_dos_eventos_seguidos_nunca_comparten_marca_de_tiempo():
    marcas = []
    previa = None
    for _ in range(200):
        previa = posterior_a(previa)
        marcas.append(previa)

    assert marcas == sorted(marcas)
    assert len(set(marcas)) == len(marcas)


# --------------------------------------------------------------------------- #
# Posiciones
# --------------------------------------------------------------------------- #


def test_la_hora_del_telefono_se_respeta_si_es_verosimil():
    posicion = normalizar_posicion(
        {"lat": 4.6, "lon": -74.1, "precision_m": 12.345, "capturada_en": _hace(30)},
        iniciada_en=_hace(600),
        ahora=AHORA,
    )

    assert posicion["capturada_en"] == _hace(30)
    assert posicion["recibida_en"] == _iso(AHORA)
    assert posicion["hora_de"] == "dispositivo"
    assert posicion["precision_m"] == 12.3


@pytest.mark.parametrize(
    "capturada_en",
    [
        _iso(AHORA + dt.timedelta(hours=2)),  # adelantada
        _hace(7200),  # anterior al inicio de la ruta
        "ayer por la tarde",  # ilegible
        "2026-10-16T15:00:00",  # sin zona horaria: ambigua
        None,
    ],
)
def test_una_hora_inverosimil_se_sustituye_por_la_de_recepcion(capturada_en):
    posicion = normalizar_posicion(
        {"lat": 4.6, "lon": -74.1, "capturada_en": capturada_en},
        iniciada_en=_hace(600),
        ahora=AHORA,
    )

    assert posicion["capturada_en"] == _iso(AHORA)
    assert posicion["hora_de"] == "servidor"


def test_un_leve_adelanto_del_reloj_se_recorta_a_la_hora_del_servidor():
    posicion = normalizar_posicion(
        {"lat": 4.6, "lon": -74.1, "capturada_en": _iso(AHORA + dt.timedelta(seconds=30))},
        iniciada_en=_hace(600),
        ahora=AHORA,
    )

    assert posicion["hora_de"] == "dispositivo"
    assert posicion["capturada_en"] == _iso(AHORA), "nunca una posicion del futuro"


# --------------------------------------------------------------------------- #
# Senal y resumen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("edad", "estado"),
    [(10, "en_linea"), (61, "atrasada"), (299, "atrasada"), (301, "sin_senal")],
)
def test_la_senal_se_clasifica_por_la_antiguedad_de_la_ultima_posicion(edad, estado):
    ruta = {"estado": "ACTIVA", "ultima_posicion": {"capturada_en": _hace(edad)}}

    assert senal(ruta, AHORA) == {"estado": estado, "edad_segundos": edad}


def test_una_ruta_sin_posiciones_o_cerrada_no_tiene_senal():
    assert senal({"estado": "ACTIVA", "ultima_posicion": None}, AHORA)["estado"] == "sin_datos"
    assert senal({"estado": "FINALIZADA"}, AHORA)["estado"] == "cerrada"


def test_la_incidencia_no_cierra_la_parada():
    ruta = {
        "paradas": [
            {"estado": "ENTREGADO"},
            {"estado": "INCIDENCIA"},
            {"estado": "EN_REPARTO"},
            {"estado": "DEVUELTO"},
        ]
    }

    assert resumen(ruta) == {
        "total": 4,
        "entregadas": 1,
        "incidencias": 1,
        "cerradas": 2,
        "pendientes": 2,
    }


# --------------------------------------------------------------------------- #
# Lo que ve el destinatario
# --------------------------------------------------------------------------- #


def _ruta(edad: int = 20, estado: str = "ACTIVA") -> dict:
    return {
        "estado": estado,
        "conductor_nombre": "Carlos Nieto",
        "paradas": [{"envio_id": "e-1"}, {"envio_id": "e-2"}],
        "ultima_posicion": {
            "lat": 4.6531294,
            "lon": -74.0836712,
            "precision_m": 4,
            "capturada_en": _hace(edad),
        },
    }


def test_el_destinatario_ve_la_posicion_redondeada_y_nada_mas():
    vista = ubicacion_publica({"envio_id": "e-1", "estado": "EN_REPARTO"}, _ruta(), AHORA)

    assert vista == {
        "disponible": True,
        "posicion": {"lat": 4.6531, "lon": -74.0837, "precision_m": 15},
        "actualizada_en": _hace(20),
        "edad_segundos": 20,
    }


@pytest.mark.parametrize(
    ("envio", "ruta", "motivo"),
    [
        ({"envio_id": "e-1", "estado": "EN_TRANSITO"}, _ruta(), "no_en_reparto"),
        ({"envio_id": "e-1", "estado": "ENTREGADO"}, _ruta(), "no_en_reparto"),
        ({"envio_id": "e-1", "estado": "EN_REPARTO"}, None, "sin_ruta_activa"),
        ({"envio_id": "e-1", "estado": "EN_REPARTO"}, _ruta(estado="FINALIZADA"), "sin_ruta_activa"),
        ({"envio_id": "otro", "estado": "EN_REPARTO"}, _ruta(), "sin_ruta_activa"),
        (
            {"envio_id": "e-1", "estado": "EN_REPARTO"},
            _ruta(edad=VIGENCIA_PUBLICA_SEGUNDOS + 1),
            "sin_senal",
        ),
    ],
)
def test_fuera_del_reparto_en_curso_la_posicion_no_se_muestra(envio, ruta, motivo):
    vista = ubicacion_publica(envio, ruta, AHORA)

    assert vista["disponible"] is False
    assert vista["motivo"] == motivo
    assert "posicion" not in vista


# --------------------------------------------------------------------------- #
# Roles guardados antes de las rutas
# --------------------------------------------------------------------------- #


def test_el_catalogo_fundacional_es_el_anterior_a_las_rutas():
    """Si alguien lo ampliara, los roles antiguos dejarian de recibir lo nuevo."""
    assert CATALOGO_FUNDACIONAL <= {str(o) for o in Operacion}
    assert Operacion.RUTA_OPERAR not in CATALOGO_FUNDACIONAL
    assert Operacion.RUTA_SEGUIR not in CATALOGO_FUNDACIONAL


def test_un_rol_de_fabrica_guardado_sin_catalogo_recibe_las_operaciones_nuevas():
    assert operaciones_nuevas_para("conductor", None) == {Operacion.RUTA_OPERAR}
    assert operaciones_nuevas_para("despachador", None) == {Operacion.RUTA_SEGUIR}
    assert operaciones_nuevas_para("auditor", None) == frozenset()


def test_lo_que_la_empresa_vio_y_quito_sigue_quitado():
    catalogo_actual = [str(o) for o in Operacion]
    assert operaciones_nuevas_para("conductor", catalogo_actual) == frozenset()


def test_un_rol_propio_de_la_empresa_no_hereda_nada():
    assert operaciones_nuevas_para("supervisor-nocturno", None) == frozenset()


def test_el_auditor_no_sigue_rutas_ni_sale_a_ellas():
    """Mirar la ubicacion de una persona no es revisar lo que se opero."""
    auditor = ROLES_INTEGRADOS["auditor"].operaciones
    assert Operacion.RUTA_SEGUIR not in auditor
    assert Operacion.RUTA_OPERAR not in auditor
