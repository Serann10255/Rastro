"""Ciclo de vida completo del envio sobre la pila de microservicios.

Cubre REQ-01 (registro), REQ-02 (punto de control con autor y marca de tiempo),
REQ-03 (rechazo de transiciones invalidas) y REQ-05 (evidencia cifrada mediante
enlace prefirmado).
"""

from __future__ import annotations

from rastro_core.state_machine import Estado


def _registrar(pila, cabeceras, envio_id: str, estado: str, **extra):
    return pila["tracking"].post(
        f"/envios/{envio_id}/eventos",
        headers=cabeceras,
        json={"estado": estado, **extra},
    )


def _asignar(pila, despachador, envio_id: str, conductor_sub: str = "u-cond-a"):
    return pila["shipments"].post(
        f"/envios/{envio_id}/asignacion",
        headers=despachador,
        json={"conductor_sub": conductor_sub, "conductor_nombre": "Carlos Nieto"},
    )


# --------------------------------------------------------------------------- #
# REQ-01
# --------------------------------------------------------------------------- #


def test_req01_el_envio_se_crea_con_identificador_unico_y_estado_creado(envio_creado):
    assert envio_creado["estado"] == Estado.CREADO.value
    assert len(envio_creado["envio_id"]) == 36
    assert envio_creado["org_id"] == "org-andes"
    assert envio_creado["creado_por"] == "u-desp-a"


def test_req01_dos_envios_no_comparten_identificador(pila, despachador, envio_creado):
    otro = pila["shipments"].post(
        "/envios",
        headers=despachador,
        json={
            "origen": {"linea": "Calle 1 #1-1"},
            "destino": {"linea": "Calle 2 #2-2"},
            "destinatario": {"nombre": "Otro Destinatario"},
        },
    ).json()["envio"]
    assert otro["envio_id"] != envio_creado["envio_id"]


# --------------------------------------------------------------------------- #
# REQ-02 y REQ-03
# --------------------------------------------------------------------------- #


def test_req03_no_se_puede_saltar_de_creado_a_entregado(pila, despachador, conductor, envio_creado):
    """Criterio de aceptacion literal: responde 400 y deja el intento en bitacora."""
    envio_id = envio_creado["envio_id"]
    _asignar(pila, despachador, envio_id)

    respuesta = _registrar(pila, conductor, envio_id, Estado.ENTREGADO.value)

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "TRANSICION_INVALIDA"


def test_req02_el_punto_de_control_conserva_autor_y_marca_de_tiempo_del_servidor(
    pila, despachador, conductor, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _asignar(pila, despachador, envio_id)

    respuesta = _registrar(
        pila,
        conductor,
        envio_id,
        Estado.RECOLECTADO.value,
        ubicacion={"lat": 4.6821, "lon": -74.0451},
        nota="Recogido en porteria",
    )

    assert respuesta.status_code == 201
    evento = respuesta.json()["evento"]
    assert evento["actor_sub"] == "u-cond-a"
    assert evento["estado_anterior"] == Estado.ASIGNADO.value
    assert evento["ubicacion"] == {"lat": 4.6821, "lon": -74.0451}
    assert evento["ts"].endswith("Z")


def test_la_interfaz_solo_ofrece_las_transiciones_alcanzables(
    pila, despachador, conductor, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _asignar(pila, despachador, envio_id)

    cuerpo = pila["tracking"].get(f"/envios/{envio_id}/transiciones", headers=conductor).json()

    assert cuerpo["estado_actual"] == Estado.ASIGNADO.value
    assert set(cuerpo["transiciones"]) == {Estado.RECOLECTADO.value, Estado.INCIDENCIA.value}


# --------------------------------------------------------------------------- #
# REQ-05: entrega con evidencia
# --------------------------------------------------------------------------- #


def _avanzar_hasta_reparto(pila, despachador, conductor, envio_id):
    _asignar(pila, despachador, envio_id)
    for estado in (Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO):
        respuesta = _registrar(pila, conductor, envio_id, estado.value)
        assert respuesta.status_code == 201, respuesta.text


def test_req05_ciclo_completo_con_evidencia_cargada_y_confirmada(
    pila, despachador, conductor, almacen, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _avanzar_hasta_reparto(pila, despachador, conductor, envio_id)

    enlace = pila["evidence"].post(
        f"/envios/{envio_id}/evidencias",
        headers=conductor,
        json={"nombre_archivo": "entrega.jpg", "tipo_contenido": "image/jpeg"},
    ).json()

    # El enlace queda acotado al prefijo de la organizacion.
    assert enlace["clave"].startswith("org-andes/")
    assert enlace["vigencia_segundos"] > 0

    # El dispositivo carga contra el enlace; el servicio no ve el archivo.
    almacen.cargar(enlace["clave"])

    confirmacion = pila["evidence"].post(
        f"/envios/{envio_id}/evidencias/{enlace['evidencia_id']}/confirmacion",
        headers=conductor,
    )
    assert confirmacion.status_code == 200
    assert confirmacion.json()["propiedades"]["cifrado"] == "aws:kms"

    entrega = _registrar(
        pila,
        conductor,
        envio_id,
        Estado.ENTREGADO.value,
        evidencia_id=enlace["evidencia_id"],
        nota="Recibido por el destinatario",
    )
    assert entrega.status_code == 201
    assert entrega.json()["envio"]["estado"] == Estado.ENTREGADO.value


def test_req05_no_se_da_por_entregado_un_envio_sin_evidencia_confirmada(
    pila, despachador, conductor, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _avanzar_hasta_reparto(pila, despachador, conductor, envio_id)

    respuesta = _registrar(pila, conductor, envio_id, Estado.ENTREGADO.value)

    assert respuesta.status_code == 400
    assert "evidencia" in respuesta.json()["mensaje"].lower()


def test_una_evidencia_declarada_pero_no_cargada_no_acredita_la_entrega(
    pila, despachador, conductor, envio_creado
):
    """El cliente no puede inventar el identificador de una evidencia."""
    envio_id = envio_creado["envio_id"]
    _avanzar_hasta_reparto(pila, despachador, conductor, envio_id)

    respuesta = _registrar(
        pila, conductor, envio_id, Estado.ENTREGADO.value, evidencia_id="inventada"
    )
    assert respuesta.status_code == 400


# --------------------------------------------------------------------------- #
# Incidencia y separacion de funciones
# --------------------------------------------------------------------------- #


def test_el_conductor_reporta_la_incidencia_pero_no_puede_reanudar(
    pila, despachador, conductor, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _asignar(pila, despachador, envio_id)
    _registrar(pila, conductor, envio_id, Estado.RECOLECTADO.value)

    incidencia = _registrar(
        pila, conductor, envio_id, Estado.INCIDENCIA.value, nota="Direccion no existe"
    )
    assert incidencia.status_code == 201
    assert incidencia.json()["envio"]["estado_previo_incidencia"] == Estado.RECOLECTADO.value

    reanudacion = _registrar(pila, conductor, envio_id, Estado.EN_TRANSITO.value)
    assert reanudacion.status_code == 403


def test_el_despachador_autoriza_la_reanudacion_tras_la_incidencia(
    pila, despachador, conductor, envio_creado
):
    envio_id = envio_creado["envio_id"]
    _asignar(pila, despachador, envio_id)
    _registrar(pila, conductor, envio_id, Estado.RECOLECTADO.value)
    _registrar(pila, conductor, envio_id, Estado.INCIDENCIA.value, nota="Direccion no existe")

    reanudacion = _registrar(
        pila, despachador, envio_id, Estado.EN_TRANSITO.value, nota="Direccion corregida"
    )

    assert reanudacion.status_code == 201
    assert reanudacion.json()["envio"]["estado"] == Estado.EN_TRANSITO.value
    assert reanudacion.json()["envio"]["estado_previo_incidencia"] is None
