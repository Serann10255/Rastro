"""Consulta publica (REQ-04), bitacora y verificacion de integridad (REQ-08).

La consulta publica es el unico punto que responde sin token y por eso es el
mas expuesto: se comprueba que devuelve el historico completo, que no filtra
datos de operacion y que no admite enumeracion.
"""

from __future__ import annotations

from rastro_core.state_machine import Estado


def _avanzar(pila, despachador, conductor, envio_id, hasta=Estado.EN_REPARTO):
    pila["shipments"].post(
        f"/envios/{envio_id}/asignacion",
        headers=despachador,
        json={"conductor_sub": "u-cond-a", "conductor_nombre": "Carlos Nieto"},
    )
    for estado in (Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO):
        pila["tracking"].post(
            f"/envios/{envio_id}/eventos", headers=conductor, json={"estado": estado.value}
        )
        if estado is hasta:
            break


# --------------------------------------------------------------------------- #
# REQ-04
# --------------------------------------------------------------------------- #


def test_req04_el_historico_completo_se_consulta_sin_autenticacion(
    pila, despachador, conductor, envio_creado
):
    """Criterio de aceptacion literal de REQ-04."""
    envio_id = envio_creado["envio_id"]
    _avanzar(pila, despachador, conductor, envio_id)

    respuesta = pila["public"].get(f"/publico/envios/{envio_id}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["envio"]["envio_id"] == envio_id
    assert cuerpo["envio"]["estado"] == Estado.EN_REPARTO.value

    estados = [e["estado"] for e in cuerpo["eventos"]]
    assert estados == [
        Estado.CREADO.value,
        Estado.ASIGNADO.value,
        Estado.RECOLECTADO.value,
        Estado.EN_TRANSITO.value,
        Estado.EN_REPARTO.value,
    ]

    marcas = [e["ts"] for e in cuerpo["eventos"]]
    assert marcas == sorted(marcas), "Los eventos deben venir en orden cronologico"


def test_req04_la_vista_publica_no_expone_la_operacion_de_la_empresa(
    pila, despachador, conductor, envio_creado
):
    """El destinatario ve el avance de su envio, no el interior de la empresa."""
    envio_id = envio_creado["envio_id"]
    _avanzar(pila, despachador, conductor, envio_id)

    cuerpo = pila["public"].get(f"/publico/envios/{envio_id}").json()
    plano = str(cuerpo)

    assert "u-cond-a" not in plano, "No debe aparecer la identidad del mensajero"
    assert "org-andes" not in plano, "No debe aparecer el identificador de organizacion"
    assert "Calle 100" not in plano, "No debe aparecer la direccion de origen"
    assert "actor_sub" not in plano
    assert cuerpo["envio"]["destinatario_nombre"] == "Laura M. R."


def test_req04_un_identificador_inexistente_responde_no_encontrado(pila):
    respuesta = pila["public"].get("/publico/envios/00000000-0000-4000-8000-000000000000")
    assert respuesta.status_code == 404


def test_el_punto_publico_no_admite_identificadores_que_no_sean_aleatorios(pila):
    """Rechazar formatos ajenos al UUID encarece cualquier intento de enumeracion.

    Un consecutivo se recorre en minutos; un UUID v4, no. El formato se valida
    antes de consultar el almacenamiento, de modo que el sondeo ni siquiera
    llega a producir una lectura.
    """
    for candidato in ("1", "0001", "envio-1", "org-andes", "ORG-ANDES-ENV-1"):
        respuesta = pila["public"].get(f"/publico/envios/{candidato}")
        assert respuesta.status_code == 422, candidato

    # Un recorrido de directorios no llega siquiera a resolver contra la ruta.
    for candidato in ("../../etc/passwd", "%2e%2e%2fetc%2fpasswd"):
        assert pila["public"].get(f"/publico/envios/{candidato}").status_code == 404, candidato


def test_la_consulta_publica_no_escribe_en_la_bitacora(
    pila, despachador, envio_creado, repositorio
):
    """Sin sesion no hay actor al que atribuir el evento, y un registro sin
    actor no cumple la cuadrupla minima de Kent y Souppaya (2006). La actividad
    del punto publico se observa en la capa de infraestructura."""
    antes = len(repositorio.listar_bitacora("org-andes", limite=1000))
    pila["public"].get(f"/publico/envios/{envio_creado['envio_id']}")
    despues = len(repositorio.listar_bitacora("org-andes", limite=1000))
    assert antes == despues


# --------------------------------------------------------------------------- #
# REQ-08: bitacora y verificacion
# --------------------------------------------------------------------------- #


def test_la_bitacora_registra_la_cuadrupla_minima(pila, despachador, auditor, envio_creado):
    registros = pila["audit"].get("/bitacora", headers=auditor).json()["registros"]
    assert registros

    for registro in registros:
        assert registro["actor_sub"], "quien"
        assert registro["accion"], "que accion"
        assert registro["recurso"], "sobre que recurso"
        assert registro["ts"], "en que momento"
        assert registro["resultado"] in {"ALLOW", "DENY", "ERROR"}
        assert len(registro["hash"]) == 64


def test_req08_la_cadena_verifica_sobre_una_bitacora_integra(
    pila, despachador, conductor, auditor, envio_creado
):
    _avanzar(pila, despachador, conductor, envio_creado["envio_id"])

    verificacion = pila["audit"].get("/bitacora/verificacion", headers=auditor).json()

    assert verificacion["cadena_valida"] is True
    assert verificacion["registros_verificados"] > 0
    assert verificacion["punto_de_ruptura"] is None


def test_req08_tras_una_alteracion_controlada_el_verificador_senala_la_ruptura(
    pila, despachador, conductor, auditor, envio_creado, repositorio
):
    """Criterio de aceptacion literal de REQ-08.

    Se modifica un registro directamente en el almacen, sin pasar por la
    aplicacion, que es exactamente el escenario que el control debe detectar.
    """
    _avanzar(pila, despachador, conductor, envio_creado["envio_id"])
    assert pila["audit"].get("/bitacora/verificacion", headers=auditor).json()["cadena_valida"]

    repositorio.alterar_registro_bitacora("org-andes", 2, "resultado", "ALLOW")
    repositorio.alterar_registro_bitacora("org-andes", 2, "accion", "envio:borrar")

    verificacion = pila["audit"].get("/bitacora/verificacion", headers=auditor).json()

    assert verificacion["cadena_valida"] is False
    assert verificacion["punto_de_ruptura"]["seq"] == 2
    assert verificacion["punto_de_ruptura"]["tipo"] == "CONTENIDO_ALTERADO"


def test_la_bitacora_no_expone_ninguna_ruta_de_escritura(pila, auditor):
    """Los eslabones los escriben los servicios; ningun usuario los anade."""
    rutas = pila["audit"].get("/openapi.json").json()["paths"]
    metodos = {m.upper() for ruta in rutas.values() for m in ruta}
    assert metodos <= {"GET"}


def test_la_consulta_del_auditor_tambien_deja_rastro(pila, auditor, envio_creado, repositorio):
    pila["audit"].get("/bitacora", headers=auditor)
    registros = repositorio.listar_bitacora("org-andes", limite=1000)
    assert any(
        r["accion"] == "bitacora:consultar" and r["actor_sub"] == "u-audit-a" for r in registros
    )


# --------------------------------------------------------------------------- #
# Emisor de tokens del entorno local
# --------------------------------------------------------------------------- #


def test_el_inicio_de_sesion_entrega_un_token_utilizable_en_los_demas_servicios(pila):
    respuesta = pila["auth"].post(
        "/auth/token", json={"correo": "despacho@andes.test", "clave": "Prueba.Despacho.2026"}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["grupos"] == ["despachador"]
    assert cuerpo["usuario"]["org_id"] == "org-andes"
    # La respuesta no filtra el hash de la contrasena por ninguna via.
    assert "hash_clave" not in str(cuerpo)

    cabecera = {"Authorization": f"Bearer {cuerpo['token']}"}
    assert pila["shipments"].get("/envios", headers=cabecera).status_code == 200


def test_las_credenciales_invalidas_no_distinguen_usuario_de_clave(pila):
    """Distinguirlas permitiria enumerar las cuentas del sistema."""
    inexistente = pila["auth"].post(
        "/auth/token", json={"correo": "nadie@andes.test", "clave": "clave-que-no-sirve"}
    )
    clave_mala = pila["auth"].post(
        "/auth/token", json={"correo": "despacho@andes.test", "clave": "clave-que-no-sirve"}
    )
    assert inexistente.status_code == clave_mala.status_code == 401
    assert inexistente.json()["mensaje"] == clave_mala.json()["mensaje"]


def test_todos_los_servicios_responden_su_estado(pila):
    for nombre, cliente in pila.items():
        respuesta = cliente.get("/salud")
        assert respuesta.status_code == 200, nombre
        assert respuesta.json()["servicio"].startswith("rastro-")
