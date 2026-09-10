"""Pruebas de la matriz de autorizacion (REQ-07) y de las claves (REQ-06)."""

from __future__ import annotations

import pytest

from rastro_core.authz import (
    MATRIZ,
    Grupo,
    Operacion,
    esta_autorizado,
    exige_envio_propio,
    normalizar_grupos,
)
from rastro_core.claves import pk_bitacora, pk_envio
from rastro_core.errors import ValidacionError
from rastro_core.ids import nuevo_id_envio


# --------------------------------------------------------------------------- #
# Matriz de autorizacion
# --------------------------------------------------------------------------- #


def test_toda_operacion_declara_sus_grupos():
    """Lo que no esta en la matriz se rechaza; la matriz debe cubrir todo."""
    assert set(MATRIZ) == set(Operacion)
    assert all(grupos for grupos in MATRIZ.values())


def test_el_conductor_no_puede_crear_envios():
    """Criterio de aceptacion literal de REQ-07."""
    assert not esta_autorizado(["conductor"], Operacion.ENVIO_CREAR)


def test_solo_el_auditor_alcanza_la_bitacora():
    for grupo in Grupo:
        esperado = grupo is Grupo.AUDITOR
        assert esta_autorizado([grupo], Operacion.BITACORA_CONSULTAR) is esperado
        assert esta_autorizado([grupo], Operacion.BITACORA_VERIFICAR) is esperado


def test_el_auditor_no_aparece_en_ninguna_operacion_de_escritura():
    escritura = {
        Operacion.ENVIO_CREAR,
        Operacion.ENVIO_ASIGNAR,
        Operacion.EVENTO_REGISTRAR,
        Operacion.EVENTO_REANUDAR,
        Operacion.EVIDENCIA_CARGAR,
    }
    for operacion in escritura:
        assert Grupo.AUDITOR not in MATRIZ[operacion], operacion


def test_la_reanudacion_tras_incidencia_excluye_al_conductor():
    """Separacion de funciones: reporta el conductor, autoriza el despachador."""
    assert esta_autorizado(["conductor"], Operacion.EVENTO_REGISTRAR)
    assert not esta_autorizado(["conductor"], Operacion.EVENTO_REANUDAR)
    assert esta_autorizado(["despachador"], Operacion.EVENTO_REANUDAR)


def test_un_grupo_desconocido_no_concede_permisos():
    assert normalizar_grupos(["superusuario", "root"]) == frozenset()
    assert not esta_autorizado(["superusuario"], Operacion.ENVIO_CREAR)


def test_un_token_sin_grupos_no_autoriza_nada():
    for operacion in Operacion:
        assert not esta_autorizado([], operacion)


def test_el_conductor_queda_restringido_a_sus_propios_envios():
    assert exige_envio_propio(["conductor"], Operacion.EVENTO_REGISTRAR)
    assert exige_envio_propio(["conductor"], Operacion.ENVIO_LISTAR)
    assert not exige_envio_propio(["despachador"], Operacion.ENVIO_LISTAR)


# --------------------------------------------------------------------------- #
# Claves: aislamiento entre organizaciones
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("org_vacia", ["", "   ", None])
def test_no_se_puede_construir_una_clave_sin_organizacion(org_vacia):
    """Riesgo R-05: la consulta sin filtro no debe poder ni escribirse."""
    with pytest.raises(ValidacionError):
        pk_envio(org_vacia, nuevo_id_envio())
    with pytest.raises(ValidacionError):
        pk_bitacora(org_vacia)


def test_no_se_puede_inyectar_un_separador_en_la_organizacion():
    """Sin esta comprobacion, 'a#ENV#x' permitiria alcanzar otra particion."""
    with pytest.raises(ValidacionError):
        pk_envio("org-andes#ENV#robado", "envio-1")


def test_dos_organizaciones_producen_particiones_distintas():
    envio_id = nuevo_id_envio()
    assert pk_envio("org-andes", envio_id) != pk_envio("org-sabana", envio_id)


def test_el_identificador_de_envio_no_es_predecible():
    """Control contra la referencia directa insegura a objetos (OWASP A01:2021)."""
    identificadores = {nuevo_id_envio() for _ in range(500)}
    assert len(identificadores) == 500
    assert all(len(i) == 36 and i.count("-") == 4 for i in identificadores)
