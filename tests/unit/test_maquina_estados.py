"""Pruebas de la maquina de estados (Figura 2 del documento, REQ-03)."""

from __future__ import annotations

import pytest

from rastro_core.errors import TransicionInvalidaError
from rastro_core.state_machine import (
    CATALOGO,
    FLUJO_PRINCIPAL,
    POR_ESTADO,
    Estado,
    catalogo_publico,
    codigo_de,
    definicion,
    es_transicion_valida,
    estado_de_codigo,
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
    assert permitidas == frozenset({Estado.EN_TRANSITO, Estado.EN_REPARTO, Estado.DEVUELTO})


def test_sin_estado_previo_la_incidencia_solo_ofrece_la_devolucion():
    """Si no se sabe de donde venia el envio, no se adivina hacia donde sigue.

    Lo unico que se puede hacer con un envio detenido cuyo origen se desconoce
    es devolverlo: cerrarlo por devolucion no exige saber en que punto del flujo
    estaba, y dejarlo sin ninguna salida lo convertiria en un envio atascado
    para siempre.
    """
    assert transiciones_permitidas(Estado.INCIDENCIA) == frozenset({Estado.DEVUELTO})


def test_la_reanudacion_exige_autorizacion_del_despachador():
    assert requiere_autorizacion_despachador(Estado.INCIDENCIA)
    assert not requiere_autorizacion_despachador(Estado.EN_TRANSITO)


def test_un_estado_inexistente_se_rechaza_como_transicion_invalida():
    with pytest.raises(TransicionInvalidaError):
        validar_transicion(Estado.CREADO, "EXTRAVIADO")


# --------------------------------------------------------------------------- #
# Catalogo de estados con codigo numerico
# --------------------------------------------------------------------------- #


def test_cada_estado_tiene_un_codigo_unico():
    """El codigo viaja en los archivos de intercambio: si se repite, el archivo
    deja de poder interpretarse."""
    codigos = [d.codigo for d in CATALOGO]
    assert len(codigos) == len(set(codigos))
    assert set(POR_ESTADO) == set(Estado)


def test_los_codigos_estan_en_un_rango_compacto_y_ordenado():
    """Ordenados por avance del proceso y con hueco para intercalar.

    Los saltos de diez dejan sitio para anadir estados sin renumerar los
    existentes, que obligaria a reprocesar todo el historico."""
    codigos = [d.codigo for d in CATALOGO]
    assert codigos == sorted(codigos)
    assert all(10 <= c <= 90 for c in codigos)
    assert all(c % 10 == 0 for c in codigos)


def test_el_codigo_traduce_en_los_dos_sentidos():
    for definicion_estado in CATALOGO:
        assert estado_de_codigo(definicion_estado.codigo) is definicion_estado.estado
        assert codigo_de(definicion_estado.estado) == definicion_estado.codigo


def test_un_codigo_inexistente_se_rechaza_indicando_los_validos():
    with pytest.raises(TransicionInvalidaError) as error:
        estado_de_codigo(999)
    assert 10 in error.value.detalle["codigos_validos"]


def test_el_catalogo_publico_lleva_todo_lo_que_la_interfaz_necesita():
    """Para que la interfaz no duplique el catalogo y se desincronice."""
    for entrada in catalogo_publico():
        assert entrada["codigo"] and entrada["estado"] and entrada["fase"]
        assert entrada["etiqueta"] and entrada["descripcion"]


# --------------------------------------------------------------------------- #
# Cierres por excepcion
# --------------------------------------------------------------------------- #


def test_un_envio_solo_se_cancela_antes_de_recogerlo():
    """Una vez el paquete esta en poder de alguien, lo que corresponde es
    devolverlo: el paquete existe y anularlo no lo hace desaparecer."""
    assert es_transicion_valida(Estado.CREADO, Estado.CANCELADO)
    assert es_transicion_valida(Estado.ASIGNADO, Estado.CANCELADO)
    assert not es_transicion_valida(Estado.RECOLECTADO, Estado.CANCELADO)
    assert not es_transicion_valida(Estado.EN_REPARTO, Estado.CANCELADO)


def test_un_envio_que_ya_salio_se_devuelve_pero_no_se_cancela():
    for origen in (Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO):
        assert es_transicion_valida(origen, Estado.DEVUELTO)
        assert not es_transicion_valida(origen, Estado.CANCELADO)


@pytest.mark.parametrize("estado", [Estado.ENTREGADO, Estado.DEVUELTO, Estado.CANCELADO])
def test_los_tres_cierres_son_finales(estado):
    assert transiciones_permitidas(estado) == frozenset()
    assert definicion(estado).final


def test_solo_la_entrega_cuenta_como_cierre_exitoso():
    exitosos = [d.estado for d in CATALOGO if d.exitoso]
    assert exitosos == [Estado.ENTREGADO]


def test_cerrar_por_devolucion_o_cancelacion_exige_despachador():
    """Tienen efecto comercial sobre el cliente: no las decide el mensajero."""
    assert requiere_autorizacion_despachador(Estado.EN_REPARTO, Estado.DEVUELTO)
    assert requiere_autorizacion_despachador(Estado.CREADO, Estado.CANCELADO)
    assert not requiere_autorizacion_despachador(Estado.ASIGNADO, Estado.RECOLECTADO)
