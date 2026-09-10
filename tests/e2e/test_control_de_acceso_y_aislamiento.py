"""Control de acceso por rol (REQ-07) y aislamiento entre organizaciones (REQ-06).

Son las dos pruebas que el documento identifica como las mas importantes del
plan: la primera comprueba la separacion de funciones, la segunda comprueba que
la infraestructura compartida no filtra datos entre empresas. En ambas se
verifica no solo el codigo de respuesta, sino tambien que el intento haya
quedado registrado en la bitacora con resultado DENY.
"""

from __future__ import annotations

import pytest

from rastro_core.state_machine import Estado


def _bitacora(repositorio, org_id: str = "org-andes") -> list[dict]:
    return repositorio.listar_bitacora(org_id, limite=1000)


def _hay_deny(repositorio, org_id: str, accion: str) -> bool:
    return any(
        r["resultado"] == "DENY" and r["accion"] == accion for r in _bitacora(repositorio, org_id)
    )


# --------------------------------------------------------------------------- #
# REQ-07: autorizacion por grupo
# --------------------------------------------------------------------------- #


def test_req07_el_conductor_no_puede_crear_envios_y_el_intento_queda_registrado(
    pila, conductor, repositorio
):
    """Criterio de aceptacion literal de REQ-07."""
    respuesta = pila["shipments"].post(
        "/envios",
        headers=conductor,
        json={
            "origen": {"linea": "Calle 1 #1-1"},
            "destino": {"linea": "Calle 2 #2-2"},
            "destinatario": {"nombre": "Quien Sea"},
        },
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "NO_AUTORIZADO"

    registros = [r for r in _bitacora(repositorio) if r["resultado"] == "DENY"]
    assert len(registros) == 1
    registro = registros[0]
    assert registro["accion"] == "envio:crear"
    assert registro["actor_sub"] == "u-cond-a"
    assert registro["actor_grupos"] == ["conductor"]
    assert registro["detalle"]["motivo"] == "grupo_no_autorizado"


def test_req07_las_operaciones_permitidas_tambien_quedan_registradas(
    pila, despachador, envio_creado, repositorio
):
    permitidas = [r for r in _bitacora(repositorio) if r["resultado"] == "ALLOW"]
    assert any(r["accion"] == "envio:crear" for r in permitidas)
    assert permitidas[0]["recurso"].startswith("envio/")


def test_solo_el_auditor_consulta_la_bitacora(pila, despachador, conductor, auditor, repositorio):
    assert pila["audit"].get("/bitacora", headers=auditor).status_code == 200
    assert pila["audit"].get("/bitacora", headers=despachador).status_code == 403
    assert pila["audit"].get("/bitacora", headers=conductor).status_code == 403
    assert _hay_deny(repositorio, "org-andes", "bitacora:consultar")


def test_el_auditor_no_puede_escribir_en_el_sistema(pila, auditor, envio_creado):
    """El rol de revision no modifica lo que revisa."""
    crear = pila["shipments"].post(
        "/envios",
        headers=auditor,
        json={
            "origen": {"linea": "Calle 1 #1-1"},
            "destino": {"linea": "Calle 2 #2-2"},
            "destinatario": {"nombre": "Quien Sea"},
        },
    )
    evento = pila["tracking"].post(
        f"/envios/{envio_creado['envio_id']}/eventos",
        headers=auditor,
        json={"estado": Estado.ASIGNADO.value},
    )
    assert crear.status_code == 403
    assert evento.status_code == 403


def test_el_conductor_no_descarga_evidencias(pila, conductor, envio_creado):
    """Carga la prueba de entrega; consultarla corresponde a otros roles."""
    respuesta = pila["evidence"].get(
        f"/envios/{envio_creado['envio_id']}/evidencias", headers=conductor
    )
    assert respuesta.status_code == 403


def test_el_conductor_solo_ve_los_envios_que_tiene_asignados(
    pila, despachador, conductor, cabeceras, envio_creado
):
    envio_id = envio_creado["envio_id"]
    pila["shipments"].post(
        f"/envios/{envio_id}/asignacion",
        headers=despachador,
        json={"conductor_sub": "u-cond-a", "conductor_nombre": "Carlos Nieto"},
    )

    propios = pila["shipments"].get("/envios", headers=conductor).json()
    ajenos = pila["shipments"].get(
        "/envios", headers=cabeceras("u-cond-otro", "org-andes", ["conductor"])
    ).json()

    assert [e["envio_id"] for e in propios["envios"]] == [envio_id]
    assert ajenos["envios"] == []


def test_el_conductor_no_registra_eventos_de_un_envio_ajeno(
    pila, despachador, cabeceras, envio_creado
):
    envio_id = envio_creado["envio_id"]
    pila["shipments"].post(
        f"/envios/{envio_id}/asignacion",
        headers=despachador,
        json={"conductor_sub": "u-cond-a"},
    )

    respuesta = pila["tracking"].post(
        f"/envios/{envio_id}/eventos",
        headers=cabeceras("u-cond-otro", "org-andes", ["conductor"]),
        json={"estado": Estado.RECOLECTADO.value},
    )

    # No se responde 403 sino 404: no se confirma que el envio exista.
    assert respuesta.status_code == 404


# --------------------------------------------------------------------------- #
# REQ-06: aislamiento entre organizaciones
# --------------------------------------------------------------------------- #


def test_req06_un_usuario_de_otra_organizacion_recibe_recurso_inexistente(
    pila, despachador_otra_org, envio_creado, repositorio
):
    """Criterio de aceptacion literal de REQ-06."""
    respuesta = pila["shipments"].get(
        f"/envios/{envio_creado['envio_id']}", headers=despachador_otra_org
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "NO_ENCONTRADO"

    # El intento queda en la bitacora de quien lo hizo, no en la del titular.
    ajena = _bitacora(repositorio, "org-sabana")
    assert any(
        r["resultado"] == "DENY"
        and r["detalle"].get("motivo") == "fuera_de_organizacion_o_inexistente"
        for r in ajena
    )
    propia = _bitacora(repositorio, "org-andes")
    assert all(r["resultado"] != "DENY" for r in propia)


@pytest.mark.parametrize(
    "servicio,metodo,ruta",
    [
        ("shipments", "get", "/envios/{envio_id}"),
        ("tracking", "get", "/envios/{envio_id}/transiciones"),
        ("evidence", "get", "/envios/{envio_id}/evidencias"),
    ],
)
def test_req06_ninguna_ruta_de_lectura_cruza_la_frontera_de_organizacion(
    pila, despachador_otra_org, envio_creado, servicio, metodo, ruta
):
    """Se prueba cada ruta: basta una sin filtrar para que el aislamiento falle."""
    respuesta = getattr(pila[servicio], metodo)(
        ruta.format(envio_id=envio_creado["envio_id"]), headers=despachador_otra_org
    )
    assert respuesta.status_code == 404


def test_req06_no_se_pueden_escribir_eventos_en_un_envio_de_otra_organizacion(
    pila, cabeceras, envio_creado
):
    respuesta = pila["tracking"].post(
        f"/envios/{envio_creado['envio_id']}/eventos",
        headers=cabeceras("u-cond-b", "org-sabana", ["conductor"]),
        json={"estado": Estado.ASIGNADO.value},
    )
    assert respuesta.status_code == 404


def test_req06_el_listado_solo_devuelve_envios_de_la_propia_organizacion(
    pila, despachador, despachador_otra_org, envio_creado
):
    pila["shipments"].post(
        "/envios",
        headers=despachador_otra_org,
        json={
            "origen": {"linea": "Autopista Norte km 20"},
            "destino": {"linea": "Calle 80 #90-10"},
            "destinatario": {"nombre": "Destino Sabana"},
        },
    )

    andes = pila["shipments"].get("/envios", headers=despachador).json()
    sabana = pila["shipments"].get("/envios", headers=despachador_otra_org).json()

    assert andes["total"] == 1
    assert sabana["total"] == 1
    assert andes["envios"][0]["envio_id"] != sabana["envios"][0]["envio_id"]


def test_req06_la_bitacora_de_una_organizacion_no_contiene_registros_de_otra(
    pila, despachador, despachador_otra_org, auditor, cabeceras, envio_creado
):
    pila["shipments"].post(
        "/envios",
        headers=despachador_otra_org,
        json={
            "origen": {"linea": "Autopista Norte km 20"},
            "destino": {"linea": "Calle 80 #90-10"},
            "destinatario": {"nombre": "Destino Sabana"},
        },
    )

    andes = pila["audit"].get("/bitacora", headers=auditor).json()
    sabana = pila["audit"].get(
        "/bitacora", headers=cabeceras("u-audit-b", "org-sabana", ["auditor"])
    ).json()

    assert {r["org_id"] for r in andes["registros"]} == {"org-andes"}
    assert {r["org_id"] for r in sabana["registros"]} == {"org-sabana"}


# --------------------------------------------------------------------------- #
# Autenticacion
# --------------------------------------------------------------------------- #


def test_sin_token_ninguna_operacion_autenticada_responde(pila):
    assert pila["shipments"].get("/envios").status_code == 401
    assert pila["audit"].get("/bitacora").status_code == 401


def test_un_token_firmado_con_otro_secreto_se_rechaza(pila):
    import jwt

    falso = jwt.encode(
        {
            "sub": "intruso",
            "custom:org_id": "org-andes",
            "cognito:groups": ["administrador"],
            "iss": "http://auth.pruebas",
            "aud": "rastro-web",
            "exp": 4102444800,
        },
        "secreto-que-no-es-el-del-sistema-largo",
        algorithm="HS256",
    )
    respuesta = pila["shipments"].get("/envios", headers={"Authorization": f"Bearer {falso}"})
    assert respuesta.status_code == 401


def test_un_token_sin_organizacion_no_produce_identidad(pila, token):
    import jwt

    from rastro_core.config import cargar_config

    config = cargar_config()
    sin_org = jwt.encode(
        {
            "sub": "u-sin-org",
            "cognito:groups": ["despachador"],
            "iss": config.jwt_emisor,
            "aud": config.jwt_audiencia,
            "exp": 4102444800,
        },
        config.jwt_secreto_local,
        algorithm="HS256",
    )
    respuesta = pila["shipments"].get("/envios", headers={"Authorization": f"Bearer {sin_org}"})
    assert respuesta.status_code == 401
