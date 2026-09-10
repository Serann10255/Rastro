"""Pruebas de la maquina de estados (Figura 2 del documento, REQ-03)."""

from __future__ import annotations

import pytest

from rastro_core.errors import TransicionInvalidaError
from rastro_core.state_machine import (
    FLUJO_PRINCIPAL,
    Estado,
    es_transicion_valida,
    requiere_autorizacion_despachador,
    transiciones_permitidas,
    validar_transicion,
)


def test_el_flujo_principal_completo_es_valido():
    for origen, destino in zip(FLUJO_PRINCIPAL, FLUJO_PRINCIPAL[1:]):
        assert es_transicion_valida(origen, destino), f"{origen} -> {destino} deberia permitirse"


def test_no_se_puede_saltar_de_creado_a_entregado():
    """Criterio de aceptacion literal de REQ-03."""
    with pytest.raises(TransicionInvalidaError) as error:
        validar_transicion(Estado.CREADO, Estado.ENTREGADO)
    assert "ASIGNADO" in error.value.detalle["permitidas"]


@pytest.mark.parametrize("origen", [e for e in FLUJO_PRINCIPAL if e is not Estado.ENTREGADO])
def test_la_incidencia_se_alcanza_desde_cualquier_estado_previo_a_la_entrega(origen):
    assert es_transicion_valida(origen, Estado.INCIDENCIA)


def test_el_estado_entregado_no_admite_salidas():
    assert transiciones_permitidas(Estado.ENTREGADO) == frozenset()
    assert not es_transicion_valida(Estado.ENTREGADO, Estado.INCIDENCIA)


def test_no_se_retrocede_en_el_flujo_principal():
    assert not es_transicion_valida(Estado.EN_TRANSITO, Estado.RECOLECTADO)
    assert not es_transicion_valida(Estado.EN_REPARTO, Estado.CREADO)


def test_la_reanudacion_vuelve_al_estado_previo_o_avanza_al_siguiente():
    permitidas = transiciones_permitidas(Estado.INCIDENCIA, estado_previo=Estado.EN_TRANSITO)
    assert permitidas == frozenset({Estado.EN_TRANSITO, Estado.EN_REPARTO})


def test_sin_estado_previo_la_incidencia_no_ofrece_salida():
    """Si no se sabe de donde venia el envio, no se adivina hacia donde sigue."""
    assert transiciones_permitidas(Estado.INCIDENCIA) == frozenset()


def test_la_reanudacion_exige_autorizacion_del_despachador():
    assert requiere_autorizacion_despachador(Estado.INCIDENCIA)
    assert not requiere_autorizacion_despachador(Estado.EN_TRANSITO)


def test_un_estado_inexistente_se_rechaza_como_transicion_invalida():
    with pytest.raises(TransicionInvalidaError):
        validar_transicion(Estado.CREADO, "EXTRAVIADO")
