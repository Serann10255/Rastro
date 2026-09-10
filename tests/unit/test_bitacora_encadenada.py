"""Pruebas del encadenamiento por funciones hash de la bitacora (REQ-08).

Una prueba que solo comprueba que el verificador informa "cadena valida" sobre
una bitacora integra no demuestra nada: un verificador que siempre responda que
si tambien la pasaria. Por eso cada forma de alteracion se prueba en los dos
sentidos.
"""

from __future__ import annotations

from rastro_core.audit import (
    HASH_GENESIS,
    calcular_hash,
    construir_registro,
    contenido_canonico,
    verificar_cadena,
)
from rastro_core.repository import RepositorioMemoria


def _bitacora_con(n: int, org_id: str = "org-andes") -> RepositorioMemoria:
    repositorio = RepositorioMemoria()
    for i in range(n):
        repositorio.registrar_bitacora(
            org_id=org_id,
            actor_sub=f"u{i}",
            actor_email=f"u{i}@pruebas.test",
            actor_grupos=["despachador"],
            accion="envio:crear",
            recurso=f"envio/{i}",
            resultado="ALLOW",
            detalle={"indice": i},
        )
    return repositorio


def test_una_cadena_intacta_verifica():
    verificacion = _bitacora_con(5).verificar_bitacora("org-andes")
    assert verificacion.cadena_valida
    assert verificacion["registros_verificados"] == 5
    assert verificacion["rupturas"] == []


def test_el_primer_registro_enlaza_con_el_hash_genesis():
    registros = _bitacora_con(1).listar_bitacora("org-andes")
    assert registros[0]["hash_previo"] == HASH_GENESIS
    assert registros[0]["seq"] == 1


def test_modificar_el_contenido_de_un_registro_rompe_la_cadena():
    repositorio = _bitacora_con(5)
    repositorio.alterar_registro_bitacora("org-andes", 3, "resultado", "ALLOW_FALSO")

    verificacion = repositorio.verificar_bitacora("org-andes")
    assert not verificacion.cadena_valida
    assert verificacion["punto_de_ruptura"]["tipo"] == "CONTENIDO_ALTERADO"
    assert verificacion["punto_de_ruptura"]["seq"] == 3


def test_recalcular_el_hash_de_un_registro_alterado_rompe_el_enlace_siguiente():
    """El atacante que corrige el hash del registro que edito no queda cubierto.

    Es la propiedad que da valor al encadenamiento: reparar un eslabon obliga a
    recalcular todos los posteriores.
    """
    repositorio = _bitacora_con(5)
    registros = repositorio.listar_bitacora("org-andes")
    alterado = dict(registros[2])
    alterado["resultado"] = "ALLOW_FALSO"

    repositorio.alterar_registro_bitacora("org-andes", 3, "resultado", "ALLOW_FALSO")
    repositorio.alterar_registro_bitacora(
        "org-andes", 3, "hash", calcular_hash(alterado["hash_previo"], alterado)
    )

    verificacion = repositorio.verificar_bitacora("org-andes")
    assert not verificacion.cadena_valida
    assert verificacion["punto_de_ruptura"]["tipo"] == "ENCADENAMIENTO_ROTO"
    assert verificacion["punto_de_ruptura"]["seq"] == 4


def test_eliminar_un_registro_intermedio_se_detecta_como_salto_de_secuencia():
    repositorio = _bitacora_con(5)
    registros = repositorio.listar_bitacora("org-andes")
    sin_el_tercero = [r for r in registros if r["seq"] != 3]

    verificacion = verificar_cadena(sin_el_tercero)
    assert not verificacion.cadena_valida
    tipos = {r["tipo"] for r in verificacion["rupturas"]}
    assert "SECUENCIA_INCOMPLETA" in tipos


def test_cada_organizacion_tiene_su_propia_cadena():
    repositorio = RepositorioMemoria()
    for org in ("org-andes", "org-sabana"):
        for i in range(3):
            repositorio.registrar_bitacora(
                org_id=org,
                actor_sub="u",
                actor_email="u@pruebas.test",
                actor_grupos=["despachador"],
                accion="envio:crear",
                recurso=f"envio/{i}",
                resultado="ALLOW",
            )

    for org in ("org-andes", "org-sabana"):
        verificacion = repositorio.verificar_bitacora(org)
        assert verificacion.cadena_valida
        assert verificacion["registros_verificados"] == 3
        assert repositorio.listar_bitacora(org)[0]["seq"] == 1


def test_el_contenido_canonico_no_depende_del_orden_de_las_claves():
    base = {
        "org_id": "org-andes",
        "seq": 1,
        "ts": "2026-09-10T10:00:00.000Z",
        "actor_sub": "u1",
        "actor_email": "u1@pruebas.test",
        "actor_grupos": ["conductor", "despachador"],
        "accion": "envio:crear",
        "recurso": "envio/1",
        "resultado": "ALLOW",
        "detalle": {"b": 2, "a": 1},
    }
    invertido = dict(reversed(list(base.items())))
    invertido["actor_grupos"] = ["despachador", "conductor"]

    assert contenido_canonico(base) == contenido_canonico(invertido)


def test_el_hash_depende_del_registro_anterior():
    comun = {
        "org_id": "org-andes",
        "actor_sub": "u1",
        "actor_email": "u1@pruebas.test",
        "actor_grupos": ["despachador"],
        "accion": "envio:crear",
        "recurso": "envio/1",
        "resultado": "ALLOW",
        "ts": "2026-09-10T10:00:00.000Z",
    }
    uno = construir_registro(seq=2, hash_previo="a" * 64, **comun)
    otro = construir_registro(seq=2, hash_previo="b" * 64, **comun)
    assert uno["hash"] != otro["hash"]
