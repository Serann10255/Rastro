"""Pruebas del propio programa de auditoria.

El riesgo R-02 del documento de Cotejo es el mas grave: que un defecto del
ejecutor clasifique como conforme un control que no lo esta. Una conclusion
falsa es el peor resultado posible de un trabajo de aseguramiento, peor que no
concluir. Estas pruebas atacan ese riesgo comprobando cada mecanismo en los dos
sentidos: que informa conformidad cuando corresponde y, sobre todo, que informa
desviacion cuando la desviacion existe.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cotejo.ejecutor import PRUEBAS, ErrorCatalogo, cargar_catalogo, cobertura, ejecutar
from cotejo.informe import construir_hallazgos, redactar
from cotejo.modelos import Conclusion, Observacion, ResultadoPrueba, Severidad
from cotejo.papeles import (
    AlmacenPapeles,
    comparar_ejecuciones,
    huella,
    verificar_almacen,
)
from cotejo.pruebas.integridad import _copias_alteradas
from rastro_core.audit import verificar_cadena
from rastro_core.repository import RepositorioMemoria


# --------------------------------------------------------------------------- #
# Catalogo
# --------------------------------------------------------------------------- #


def test_el_catalogo_declara_ocho_controles_con_criterio_y_marco():
    catalogo = cargar_catalogo()
    assert len(catalogo["controles"]) == 8
    for control in catalogo["controles"]:
        assert control.marco, f"{control.id} sin referencia de marco"
        assert control.criterio, f"{control.id} sin criterio de aceptacion"
        assert control.evidencia_esperada, f"{control.id} sin evidencia esperada"
        assert control.prueba in PRUEBAS


def test_el_catalogo_cubre_las_tres_clases_de_prueba():
    tipos = {str(c.tipo) for c in cargar_catalogo()["controles"]}
    assert tipos == {"cumplimiento", "sustantiva", "integridad"}


def test_los_hallazgos_permanentes_declaran_por_que_no_se_automatizan():
    for entrada in cargar_catalogo().get("hallazgos_permanentes", []):
        assert entrada["nota_de_alcance"], f"{entrada['id']} sin nota de alcance"
        assert Severidad(entrada["severidad"])


def test_un_catalogo_que_nombra_una_prueba_inexistente_se_rechaza(tmp_path: Path):
    """El catalogo nombra pruebas; no importa codigo. Un nombre desconocido falla."""
    import yaml

    catalogo = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "catalogo" / "controles.yaml").read_text(
            encoding="utf-8"
        )
    )
    catalogo["controles"][0]["prueba"] = "cumplimiento.inventada"
    ruta = tmp_path / "roto.yaml"
    ruta.write_text(yaml.safe_dump(catalogo), encoding="utf-8")

    with pytest.raises(ErrorCatalogo, match="no esta implementada"):
        cargar_catalogo(ruta)


def test_un_catalogo_con_controles_repetidos_se_rechaza(tmp_path: Path):
    import yaml

    catalogo = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "catalogo" / "controles.yaml").read_text(
            encoding="utf-8"
        )
    )
    catalogo["controles"].append(copy.deepcopy(catalogo["controles"][0]))
    ruta = tmp_path / "duplicado.yaml"
    ruta.write_text(yaml.safe_dump(catalogo), encoding="utf-8")

    with pytest.raises(ErrorCatalogo, match="dos veces"):
        cargar_catalogo(ruta)


# --------------------------------------------------------------------------- #
# Papeles de trabajo
# --------------------------------------------------------------------------- #


class ContextoFalso:
    """Contexto minimo para ejercitar el ejecutor sin sistema auditado."""

    entorno = "prueba"
    url_api = "http://sistema.prueba"
    region = "us-east-1"

    def identidad_de_sesion(self) -> str:
        return "prueba:evaluador"


def _ejecutar_con(resultados: dict[str, ResultadoPrueba], tmp_path: Path, ejecucion_id: str):
    """Ejecuta el catalogo sustituyendo cada prueba por un resultado fijo."""
    catalogo = cargar_catalogo()
    originales = dict(PRUEBAS)
    try:
        for control in catalogo["controles"]:
            fijo = resultados[control.id]
            PRUEBAS[control.prueba] = lambda _ctx, r=fijo: r
        return ejecutar(
            ContextoFalso(), catalogo, ejecucion_id=ejecucion_id, base_papeles=tmp_path
        )
    finally:
        PRUEBAS.clear()
        PRUEBAS.update(originales)


def _conforme(texto="conforme") -> ResultadoPrueba:
    return ResultadoPrueba(Conclusion.CONFORME, [Observacion("procedimiento", "salida")], texto)


def _desviado(texto="desviado") -> ResultadoPrueba:
    return ResultadoPrueba(
        Conclusion.DESVIADO, [Observacion("procedimiento", "salida")], texto, {"fallos": [texto]}
    )


@pytest.fixture
def catalogo():
    return cargar_catalogo()


def test_una_ejecucion_produce_un_papel_por_control_con_su_huella(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-1")

    assert len(almacen.papeles) == 8
    for papel in almacen.papeles:
        ruta = almacen.base / papel.archivo_evidencia
        assert ruta.is_file()
        assert papel.huella_evidencia == huella(ruta.read_bytes())
        assert len(papel.huella_evidencia) == 64


def test_el_papel_conserva_procedimiento_salida_fecha_e_identidad(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-2")

    contenido = json.loads(
        (almacen.base / almacen.papeles[0].archivo_evidencia).read_text(encoding="utf-8")
    )
    for campo in (
        "procedimiento",
        "criterio",
        "observaciones",
        "identidad_ejecucion",
        "iniciado_en",
        "terminado_en",
    ):
        assert contenido[campo], f"el papel no conserva {campo}"
    assert contenido["observaciones"][0]["salida"] == "salida"


def test_el_almacen_verifica_mientras_nadie_edite_la_evidencia(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-3")

    verificacion = verificar_almacen(almacen.base)
    assert verificacion["almacen_integro"]
    assert verificacion["papeles_verificados"] == 8


def test_editar_un_papel_de_trabajo_se_detecta(tmp_path, catalogo):
    """REQ-07 de Cotejo, comprobado en el sentido que importa.

    El almacen no impide la edicion: la hace detectable. Esa diferencia se
    declara, porque prometer prevencion donde solo hay deteccion seria una
    afirmacion que la evidencia no sostiene.
    """
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-4")

    objetivo = almacen.base / almacen.papeles[0].archivo_evidencia
    contenido = json.loads(objetivo.read_text(encoding="utf-8"))
    contenido["conclusion"] = "CONFORME"
    contenido["resumen"] = "resumen sustituido despues del hecho"
    objetivo.write_text(json.dumps(contenido, indent=2), encoding="utf-8")

    verificacion = verificar_almacen(almacen.base)
    assert not verificacion["almacen_integro"]
    assert verificacion["discrepancias"][0]["tipo"] == "HUELLA_DISCORDANTE"


def test_borrar_un_papel_de_trabajo_se_detecta(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-5")
    (almacen.base / almacen.papeles[2].archivo_evidencia).unlink()

    verificacion = verificar_almacen(almacen.base)
    assert not verificacion["almacen_integro"]
    assert verificacion["discrepancias"][0]["tipo"] == "ARCHIVO_AUSENTE"


# --------------------------------------------------------------------------- #
# Reproducibilidad
# --------------------------------------------------------------------------- #


def test_dos_ejecuciones_con_el_mismo_resultado_son_reproducibles(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    a, _ = _ejecutar_con(resultados, tmp_path, "ej-a")
    b, _ = _ejecutar_con(resultados, tmp_path, "ej-b")

    comparacion = comparar_ejecuciones(a.base, b.base)
    assert comparacion["reproducible"]
    assert comparacion["controles_comparados"] == 8


def test_una_clasificacion_distinta_rompe_la_reproducibilidad(tmp_path, catalogo):
    conformes = {c.id: _conforme() for c in catalogo["controles"]}
    distintos = dict(conformes)
    distintos["C-06"] = _desviado("fuga entre organizaciones")

    a, _ = _ejecutar_con(conformes, tmp_path, "ej-c")
    b, _ = _ejecutar_con(distintos, tmp_path, "ej-d")

    comparacion = comparar_ejecuciones(a.base, b.base)
    assert not comparacion["reproducible"]
    assert comparacion["diferencias"][0]["control_id"] == "C-06"


# --------------------------------------------------------------------------- #
# Cobertura e informe
# --------------------------------------------------------------------------- #


def test_un_control_no_ejecutado_no_cuenta_como_conforme(tmp_path, catalogo):
    """Riesgo R-04: el informe no debe transmitir mas cobertura que la real."""
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    resultados["C-01"] = ResultadoPrueba.no_ejecutada("capacidad no disponible")
    resultados["C-02"] = ResultadoPrueba.no_ejecutada("capacidad no disponible")

    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-6")
    resumen = cobertura(almacen, catalogo)

    assert resumen["conformes"] == 6
    assert resumen["no_ejecutados"] == 2
    assert resumen["cobertura"] == "6/8"


def test_cada_desviacion_produce_un_hallazgo_trazado_a_su_papel(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    resultados["C-06"] = _desviado("FUGA: /envios/{id} devolvio datos de otra organizacion")

    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-7")
    hallazgos = construir_hallazgos(almacen.papeles, catalogo)

    propios = [h for h in hallazgos if not h.permanente]
    assert len(propios) == 1
    hallazgo = propios[0]
    assert hallazgo.control_id == "C-06"
    assert hallazgo.severidad is Severidad.ALTA
    assert hallazgo.papel_de_trabajo.endswith("C-06.json")
    assert (almacen.base / hallazgo.papel_de_trabajo).is_file()
    assert hallazgo.huella_evidencia
    for campo in (hallazgo.condicion, hallazgo.criterio, hallazgo.causa, hallazgo.efecto):
        assert campo


def test_los_hallazgos_permanentes_se_reportan_aunque_no_haya_desviaciones(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-8")

    hallazgos = construir_hallazgos(almacen.papeles, catalogo)
    permanentes = [h for h in hallazgos if h.permanente]

    assert {h.id for h in permanentes} == {"H-PERM-01", "H-PERM-02"}
    assert all(h.recomendacion for h in permanentes)


def test_los_hallazgos_se_ordenan_por_severidad(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    resultados["C-04"] = _desviado("versionado desactivado")  # severidad media
    resultados["C-05"] = _desviado("autorizacion no aplicada")  # severidad alta

    almacen, _ = _ejecutar_con(resultados, tmp_path, "ej-9")
    hallazgos = construir_hallazgos(almacen.papeles, catalogo)
    severidades = [h.severidad for h in hallazgos]

    assert severidades == sorted(severidades, key=lambda s: {"alta": 0, "media": 1, "baja": 2}[s])


def test_el_informe_declara_los_controles_que_no_pudo_comprobar(tmp_path, catalogo):
    resultados = {c.id: _conforme() for c in catalogo["controles"]}
    resultados["C-01"] = ResultadoPrueba.no_ejecutada("el registro no existe en este entorno")

    almacen, metadatos = _ejecutar_con(resultados, tmp_path, "ej-10")
    metadatos["ejecucion_id"] = almacen.ejecucion_id
    texto = redactar(
        metadatos,
        cobertura(almacen, catalogo),
        almacen.papeles,
        construir_hallazgos(almacen.papeles, catalogo),
    )

    assert "Un control no ejecutado no es un control conforme" in texto
    assert "el registro no existe en este entorno" in texto
    assert "amenaza de autorrevision" in texto


def test_una_prueba_que_lanza_una_excepcion_no_detiene_la_ejecucion(tmp_path, catalogo):
    """Riesgo R-05: una ejecucion interrumpida produce papeles incompletos."""
    def explota(_ctx):
        raise RuntimeError("el sistema auditado no responde")

    originales = dict(PRUEBAS)
    try:
        for control in catalogo["controles"]:
            PRUEBAS[control.prueba] = (
                explota if control.id == "C-05" else (lambda _c: _conforme())
            )
        almacen, _ = _ejecutar_con(
            {c.id: _conforme() for c in catalogo["controles"]}, tmp_path, "ej-11"
        )
    finally:
        PRUEBAS.clear()
        PRUEBAS.update(originales)

    assert len(almacen.papeles) == 8


# --------------------------------------------------------------------------- #
# Prueba de integridad: validacion en doble sentido
# --------------------------------------------------------------------------- #


def _bitacora_real(n: int = 9) -> list[dict]:
    """Cadena producida por el mismo codigo que la escribe en el sistema auditado."""
    repositorio = RepositorioMemoria()
    for i in range(n):
        repositorio.registrar_bitacora(
            org_id="org-andes",
            actor_sub=f"u{i % 3}",
            actor_email=f"u{i % 3}@pruebas.test",
            actor_grupos=["conductor"],
            accion="evento:registrar",
            recurso=f"envio/{i}",
            resultado="ALLOW" if i % 4 else "DENY",
            detalle={"indice": i},
        )
    return repositorio.listar_bitacora("org-andes")


def test_las_tres_alteraciones_del_catalogo_modifican_realmente_la_copia():
    """El defecto que esta guarda evita: una alteracion que no altera nada.

    Si la copia queda identica al original, el verificador informa cadena
    valida y la prueba concluye que no detecta la manipulacion, cuando en
    realidad nunca se le presento ninguna.
    """
    registros = _bitacora_real()
    objetivo = len(registros) // 2

    for nombre, alterados, _ in _copias_alteradas(registros, objetivo):
        assert alterados != registros, f"la alteracion '{nombre}' no modifico la copia"


@pytest.mark.parametrize(
    "indice,tipo_esperado",
    [(0, "CONTENIDO_ALTERADO"), (1, "ENCADENAMIENTO_ROTO"), (2, "SECUENCIA_INCOMPLETA")],
)
def test_cada_forma_de_alteracion_se_detecta_con_su_tipo(indice, tipo_esperado):
    registros = _bitacora_real()
    objetivo = len(registros) // 2
    copias = list(_copias_alteradas(registros, objetivo))

    _nombre, alterados, esperado = copias[indice]
    resultado = verificar_cadena(alterados)

    assert not resultado["cadena_valida"]
    assert esperado == tipo_esperado
    assert tipo_esperado in {r["tipo"] for r in resultado["rupturas"]}


def test_la_cadena_sin_alterar_verifica():
    """El otro sentido: sin manipulacion, el verificador no debe inventar rupturas."""
    resultado = verificar_cadena(_bitacora_real())
    assert resultado["cadena_valida"]
    assert resultado["rupturas"] == []
