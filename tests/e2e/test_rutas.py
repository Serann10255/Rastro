"""Rutas de entrega: el conductor sale con sus guias y comparte su ubicacion.

Lo que se comprueba es lo que no se ve en la pantalla: que una ruta solo lleva
envios del conductor que la conduce, que la maquina de estados no se salta al
iniciarla, que la ubicacion solo se comparte mientras la ruta esta abierta, que
el destinatario ve la posicion y nada mas, y que mirar la ubicacion de una
persona deja constancia en la bitacora sin llenarla de refrescos.
"""

from __future__ import annotations

import datetime as dt

import pytest

from rastro_core.authz import ROLES_INTEGRADOS
from rastro_core.state_machine import Estado

BOGOTA = {"lat": 4.65312, "lon": -74.08367, "precision_m": 8}


# --------------------------------------------------------------------------- #
# Preparacion
# --------------------------------------------------------------------------- #


def _crear(pila, despachador, destinatario="Laura Mejia Rios") -> str:
    respuesta = pila["shipments"].post(
        "/envios",
        headers=despachador,
        json={
            "origen": {"linea": "Calle 100 #15-20", "ciudad": "Bogota"},
            "destino": {"linea": "Carrera 7 #32-16", "ciudad": "Bogota", "referencia": "Torre 2"},
            "destinatario": {"nombre": destinatario, "telefono": "3000000000"},
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["envio"]["envio_id"]


def _asignar(pila, despachador, envio_id, conductor_sub="u-cond-a", nombre="Carlos Nieto"):
    respuesta = pila["shipments"].post(
        f"/envios/{envio_id}/asignacion",
        headers=despachador,
        json={"conductor_sub": conductor_sub, "conductor_nombre": nombre},
    )
    assert respuesta.status_code == 200, respuesta.text


def _evento(pila, cabeceras, envio_id, estado, **extra):
    return pila["tracking"].post(
        f"/envios/{envio_id}/eventos", headers=cabeceras, json={"estado": estado, **extra}
    )


def _envio_en(pila, despachador, conductor, estado: Estado, **asignacion) -> str:
    """Un envio asignado y avanzado por el flujo principal hasta ``estado``."""
    envio_id = _crear(pila, despachador)
    _asignar(pila, despachador, envio_id, **asignacion)
    if estado is Estado.ASIGNADO:
        return envio_id
    for paso in (Estado.RECOLECTADO, Estado.EN_TRANSITO, Estado.EN_REPARTO):
        assert _evento(pila, conductor, envio_id, paso.value).status_code == 201
        if paso is estado:
            break
    return envio_id


def _entregar(pila, almacen, conductor, envio_id):
    """Carga y confirma la evidencia y registra la entrega, como en la calle."""
    enlace = pila["evidence"].post(
        f"/envios/{envio_id}/evidencias",
        headers=conductor,
        json={"nombre_archivo": "entrega.jpg", "tipo_contenido": "image/jpeg"},
    ).json()
    almacen.cargar(enlace["clave"])
    confirmacion = pila["evidence"].post(
        f"/envios/{envio_id}/evidencias/{enlace['evidencia_id']}/confirmacion",
        headers=conductor,
    )
    assert confirmacion.status_code == 200, confirmacion.text
    entrega = _evento(pila, conductor, envio_id, "ENTREGADO", evidencia_id=enlace["evidencia_id"])
    assert entrega.status_code == 201, entrega.text


def _iniciar(pila, conductor, envios, ubicacion=BOGOTA):
    cuerpo = {"envios": envios}
    if ubicacion:
        cuerpo["ubicacion"] = ubicacion
    return pila["tracking"].post("/rutas", headers=conductor, json=cuerpo)


def _bitacora(pila, auditor) -> list[dict]:
    return pila["audit"].get("/bitacora", headers=auditor).json()["registros"]


def _hace(segundos: int) -> str:
    hora = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=segundos)
    return hora.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@pytest.fixture
def otro_conductor(cabeceras):
    return cabeceras("u-cond-b", "org-andes", ["conductor"])


@pytest.fixture
def conductor_otra_org(cabeceras):
    return cabeceras("u-cond-a", "org-sabana", ["conductor"])


# --------------------------------------------------------------------------- #
# Inicio
# --------------------------------------------------------------------------- #


def test_iniciar_lleva_cada_envio_a_reparto_por_el_flujo_principal(
    pila, despachador, conductor
):
    recolectado = _envio_en(pila, despachador, conductor, Estado.RECOLECTADO)
    en_transito = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)

    respuesta = _iniciar(pila, conductor, [recolectado, en_transito])

    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    ruta = datos["ruta"]
    assert ruta["estado"] == "ACTIVA"
    assert ruta["conductor_sub"] == "u-cond-a"
    assert ruta["conductor_nombre"] == "Carlos Nieto"
    # RECOLECTADO -> EN_TRANSITO -> EN_REPARTO son dos eventos; EN_TRANSITO, uno.
    assert datos["transiciones"] == 3
    assert [p["estado"] for p in ruta["paradas"]] == ["EN_REPARTO", "EN_REPARTO"]
    assert ruta["resumen"] == {
        "total": 2, "entregadas": 0, "incidencias": 0, "cerradas": 0, "pendientes": 2
    }
    assert ruta["ultima_posicion"]["lat"] == BOGOTA["lat"]
    assert ruta["senal"]["estado"] == "en_linea"

    detalle = pila["shipments"].get(f"/envios/{recolectado}", headers=despachador).json()
    assert detalle["envio"]["estado"] == "EN_REPARTO"
    assert detalle["envio"]["ruta_id"] == ruta["ruta_id"]
    ultimos = [e["estado"] for e in detalle["eventos"]][-2:]
    assert ultimos == ["EN_TRANSITO", "EN_REPARTO"], "cada paso queda como su propio evento"
    assert detalle["eventos"][-1]["ubicacion"] == {"lat": BOGOTA["lat"], "lon": BOGOTA["lon"]}
    assert detalle["eventos"][-1]["actor_sub"] == "u-cond-a"


def test_un_envio_que_no_tiene_en_su_poder_no_sale_y_no_sale_ninguno(
    pila, despachador, conductor, auditor
):
    apto = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    sin_recoger = _envio_en(pila, despachador, conductor, Estado.ASIGNADO)

    respuesta = _iniciar(pila, conductor, [apto, sin_recoger])

    assert respuesta.status_code == 400
    assert respuesta.json()["detalle"]["no_aptos"] == [
        {"envio_id": sin_recoger, "estado": "ASIGNADO"}
    ]
    # Ni el apto se movio: la seleccion es un todo.
    apto_ahora = pila["shipments"].get(f"/envios/{apto}", headers=despachador).json()["envio"]
    assert apto_ahora["estado"] == "EN_TRANSITO"
    assert pila["tracking"].get("/rutas/activa", headers=conductor).json()["ruta"] is None

    rechazos = [
        r for r in _bitacora(pila, auditor)
        if r["accion"] == "ruta:operar" and r["resultado"] == "DENY"
    ]
    assert rechazos and rechazos[-1]["detalle"]["motivo"] == "estado_no_apto_para_ruta"


def test_un_envio_de_otro_conductor_responde_como_si_no_existiera(
    pila, despachador, conductor, otro_conductor, auditor
):
    ajeno = _envio_en(
        pila, despachador, otro_conductor, Estado.EN_TRANSITO,
        conductor_sub="u-cond-b", nombre="Camila Rojas",
    )

    respuesta = _iniciar(pila, conductor, [ajeno])

    assert respuesta.status_code == 404
    rechazo = [r for r in _bitacora(pila, auditor) if r["resultado"] == "DENY"][-1]
    assert rechazo["detalle"]["motivo"] == "envio_no_asignado_al_conductor"


def test_quien_ve_toda_la_operacion_tampoco_sale_con_paquetes_de_otro(
    pila, despachador, conductor, administrador
):
    """El administrador tiene todos los permisos, pero una ruta es de quien conduce."""
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)

    respuesta = _iniciar(pila, administrador, [envio_id])

    assert respuesta.status_code == 400
    assert respuesta.json()["detalle"]["envios"] == [envio_id]


def test_un_conductor_no_puede_tener_dos_rutas_abiertas(pila, despachador, conductor):
    primero = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    segundo = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [primero]).json()["ruta"]["ruta_id"]

    respuesta = _iniciar(pila, conductor, [segundo])

    assert respuesta.status_code == 409
    assert respuesta.json()["detalle"]["ruta_id"] == ruta_id


def test_un_testigo_huerfano_no_bloquea_al_conductor(pila, repositorio, despachador, conductor):
    """Si un inicio fallo a medias y dejo el testigo sin ruta, se puede volver a salir."""
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    repositorio.reservar_ruta_activa("org-andes", "u-cond-a", "ruta-que-nunca-se-guardo")
    clave = ("ORG#org-andes#CONDUCTOR#u-cond-a", "RUTA_ACTIVA")
    repositorio._items[clave]["reservada_en"] = _hace(3600)

    respuesta = _iniciar(pila, conductor, [envio_id])

    assert respuesta.status_code == 201, respuesta.text


def test_el_despachador_no_sale_a_ruta(pila, despachador):
    respuesta = pila["tracking"].post("/rutas", headers=despachador, json={"envios": ["x"]})
    assert respuesta.status_code == 403


# --------------------------------------------------------------------------- #
# Posiciones
# --------------------------------------------------------------------------- #


def test_las_posiciones_mueven_la_ultima_conocida_y_quedan_en_el_recorrido(
    pila, despachador, conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    # La lectura con que se sale suele ser de hace un momento: el telefono la
    # tenia en memoria cuando el conductor pulso el boton.
    inicial = {**BOGOTA, "capturada_en": _hace(60)}
    ruta_id = _iniciar(pila, conductor, [envio_id], ubicacion=inicial).json()["ruta"]["ruta_id"]

    lote = [
        {"lat": 4.6540, "lon": -74.0830, "precision_m": 12, "capturada_en": _hace(20)},
        {"lat": 4.6550, "lon": -74.0820, "precision_m": 9, "capturada_en": _hace(5)},
    ]
    respuesta = pila["tracking"].post(
        f"/rutas/{ruta_id}/posiciones", headers=conductor, json={"posiciones": lote}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["recibidas"] == 2
    assert respuesta.json()["ultima_posicion"]["lat"] == 4.6550
    assert "expira_en" not in respuesta.json()["ultima_posicion"]

    detalle = pila["tracking"].get(f"/rutas/{ruta_id}", headers=despachador).json()
    assert detalle["ruta"]["posiciones"] == 3
    assert [p["lat"] for p in detalle["posiciones"]] == [BOGOTA["lat"], 4.6540, 4.6550]
    assert all("expira_en" not in p for p in detalle["posiciones"])

    desde = detalle["posiciones"][1]["capturada_en"]
    incremental = pila["tracking"].get(
        f"/rutas/{ruta_id}", headers=despachador, params={"desde": desde}
    ).json()
    assert [p["lat"] for p in incremental["posiciones"]] == [4.6550]


def test_una_hora_de_dispositivo_inverosimil_se_sustituye_por_la_del_servidor(
    pila, despachador, conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]
    adelantada = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()

    ultima = pila["tracking"].post(
        f"/rutas/{ruta_id}/posiciones",
        headers=conductor,
        json={"posiciones": [{"lat": 4.7, "lon": -74.1, "capturada_en": adelantada}]},
    ).json()["ultima_posicion"]

    assert ultima["hora_de"] == "servidor"
    assert ultima["capturada_en"] == ultima["recibida_en"]


def test_solo_quien_conduce_reporta_posiciones(
    pila, despachador, conductor, otro_conductor, administrador, auditor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]
    posicion = {"posiciones": [{"lat": 4.7, "lon": -74.1}]}

    otro = pila["tracking"].post(f"/rutas/{ruta_id}/posiciones", headers=otro_conductor, json=posicion)
    admin = pila["tracking"].post(f"/rutas/{ruta_id}/posiciones", headers=administrador, json=posicion)
    desp = pila["tracking"].post(f"/rutas/{ruta_id}/posiciones", headers=despachador, json=posicion)

    assert otro.status_code == 404
    assert admin.status_code == 404, "ver toda la operacion no autoriza a poner el paquete en otro sitio"
    assert desp.status_code == 403
    motivos = [r["detalle"].get("motivo") for r in _bitacora(pila, auditor) if r["resultado"] == "DENY"]
    assert motivos.count("ruta_de_otro_conductor") == 2


def test_una_ruta_de_otra_organizacion_no_existe(
    pila, despachador, conductor, conductor_otra_org, despachador_otra_org
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]

    assert pila["tracking"].get(f"/rutas/{ruta_id}", headers=despachador_otra_org).status_code == 404
    reporte = pila["tracking"].post(
        f"/rutas/{ruta_id}/posiciones",
        headers=conductor_otra_org,
        json={"posiciones": [{"lat": 4.7, "lon": -74.1}]},
    )
    assert reporte.status_code == 404
    listado = pila["tracking"].get("/rutas", headers=despachador_otra_org).json()
    assert listado["rutas"] == []


# --------------------------------------------------------------------------- #
# Seguimiento
# --------------------------------------------------------------------------- #


def test_la_empresa_ve_las_rutas_activas_con_su_ultima_posicion(
    pila, despachador, coordinador, administrador, conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]

    for cabeceras in (despachador, coordinador, administrador):
        listado = pila["tracking"].get("/rutas", headers=cabeceras)
        assert listado.status_code == 200, listado.text
        rutas = listado.json()["rutas"]
        assert [r["ruta_id"] for r in rutas] == [ruta_id]
        assert rutas[0]["ultima_posicion"]["lon"] == BOGOTA["lon"]


def test_ni_el_conductor_ni_el_auditor_siguen_a_otros(pila, conductor, auditor):
    assert pila["tracking"].get("/rutas", headers=conductor).status_code == 403
    assert pila["tracking"].get("/rutas", headers=auditor).status_code == 403


def test_el_conductor_lee_su_ruta_y_no_la_de_otro(
    pila, despachador, conductor, otro_conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]

    assert pila["tracking"].get(f"/rutas/{ruta_id}", headers=conductor).status_code == 200
    assert pila["tracking"].get(f"/rutas/{ruta_id}", headers=otro_conductor).status_code == 404
    activa = pila["tracking"].get("/rutas/activa", headers=otro_conductor).json()
    assert activa["ruta"] is None


def test_cada_entrega_se_refleja_en_la_parada_de_la_ruta(
    pila, almacen, despachador, conductor
):
    entregado = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    con_novedad = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [entregado, con_novedad]).json()["ruta"]["ruta_id"]

    _entregar(pila, almacen, conductor, entregado)
    assert _evento(pila, conductor, con_novedad, "INCIDENCIA", nota="Nadie en casa").status_code == 201

    ruta = pila["tracking"].get("/rutas/activa", headers=conductor).json()["ruta"]
    assert ruta["ruta_id"] == ruta_id
    assert {p["envio_id"]: p["estado"] for p in ruta["paradas"]} == {
        entregado: "ENTREGADO",
        con_novedad: "INCIDENCIA",
    }
    assert ruta["resumen"]["entregadas"] == 1
    assert ruta["resumen"]["incidencias"] == 1
    assert ruta["resumen"]["pendientes"] == 1, "la incidencia no cierra la parada"


# --------------------------------------------------------------------------- #
# Cierre
# --------------------------------------------------------------------------- #


def test_finalizar_deja_de_compartir_y_permite_salir_de_nuevo(
    pila, despachador, conductor, auditor
):
    primero = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [primero]).json()["ruta"]["ruta_id"]

    cierre = pila["tracking"].post(
        f"/rutas/{ruta_id}/finalizacion", headers=conductor, json={"nota": "Fin de turno"}
    )

    assert cierre.status_code == 200, cierre.text
    ruta = cierre.json()["ruta"]
    assert ruta["estado"] == "FINALIZADA"
    assert ruta["cierre"] == "manual", "quedo una parada abierta"
    assert ruta["senal"]["estado"] == "cerrada"

    tardia = pila["tracking"].post(
        f"/rutas/{ruta_id}/posiciones",
        headers=conductor,
        json={"posiciones": [{"lat": 4.7, "lon": -74.1}]},
    )
    assert tardia.status_code == 409
    assert pila["tracking"].get("/rutas/activa", headers=conductor).json()["ruta"] is None

    # La parada abierta sigue en reparto y puede salir en otra ruta.
    envio = pila["shipments"].get(f"/envios/{primero}", headers=despachador).json()["envio"]
    assert envio["estado"] == "EN_REPARTO"
    assert _iniciar(pila, conductor, [primero]).status_code == 201

    cierres = [
        r for r in _bitacora(pila, auditor)
        if r["accion"] == "ruta:operar" and r["detalle"].get("operacion") == "finalizar"
    ]
    assert cierres and cierres[0]["detalle"]["pendientes"] == 1


def test_no_se_finaliza_dos_veces(pila, despachador, conductor):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]
    pila["tracking"].post(f"/rutas/{ruta_id}/finalizacion", headers=conductor, json={})

    otra = pila["tracking"].post(f"/rutas/{ruta_id}/finalizacion", headers=conductor, json={})

    assert otra.status_code == 409


def test_las_finalizadas_se_consultan_aparte(pila, despachador, conductor):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]
    pila["tracking"].post(f"/rutas/{ruta_id}/finalizacion", headers=conductor, json={})

    activas = pila["tracking"].get("/rutas", headers=despachador).json()["rutas"]
    finalizadas = pila["tracking"].get(
        "/rutas", headers=despachador, params={"estado": "finalizadas"}
    ).json()["rutas"]

    assert activas == []
    assert [r["ruta_id"] for r in finalizadas] == [ruta_id]


# --------------------------------------------------------------------------- #
# Consulta publica
# --------------------------------------------------------------------------- #


def test_el_destinatario_ve_la_posicion_mientras_su_envio_va_en_reparto(
    pila, despachador, conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    antes = pila["public"].get(f"/publico/envios/{envio_id}/ubicacion").json()
    assert antes == {**antes, "disponible": False, "motivo": "no_en_reparto"}

    _iniciar(pila, conductor, [envio_id], ubicacion={"lat": 4.653129, "lon": -74.083671, "precision_m": 3})
    durante = pila["public"].get(f"/publico/envios/{envio_id}/ubicacion").json()

    assert durante["disponible"] is True
    assert durante["posicion"] == {"lat": 4.6531, "lon": -74.0837, "precision_m": 15}
    # Ni quien conduce ni la ruta: la vista publica es del envio, no de la operacion.
    texto = str(durante)
    for prohibido in ("conductor", "u-cond-a", "Carlos", "ruta_id", "paradas", "org-andes"):
        assert prohibido not in texto


def test_tras_la_entrega_o_el_cierre_la_posicion_deja_de_verse(
    pila, almacen, despachador, conductor
):
    entregado = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    pendiente = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [entregado, pendiente]).json()["ruta"]["ruta_id"]

    _entregar(pila, almacen, conductor, entregado)

    tras_entrega = pila["public"].get(f"/publico/envios/{entregado}/ubicacion").json()
    assert tras_entrega["disponible"] is False
    assert pila["public"].get(f"/publico/envios/{pendiente}/ubicacion").json()["disponible"]

    pila["tracking"].post(f"/rutas/{ruta_id}/finalizacion", headers=conductor, json={})
    tras_cierre = pila["public"].get(f"/publico/envios/{pendiente}/ubicacion").json()
    assert tras_cierre == {**tras_cierre, "disponible": False, "motivo": "sin_ruta_activa"}


def test_una_posicion_vieja_no_se_muestra_al_destinatario(
    pila, repositorio, despachador, conductor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    ruta_id = _iniciar(pila, conductor, [envio_id]).json()["ruta"]["ruta_id"]
    clave = (f"ORG#org-andes#RUTA#{ruta_id}", "META")
    repositorio._items[clave]["ultima_posicion"]["capturada_en"] = _hace(3600)

    respuesta = pila["public"].get(f"/publico/envios/{envio_id}/ubicacion").json()

    assert respuesta["disponible"] is False
    assert respuesta["motivo"] == "sin_senal"


def test_la_consulta_publica_de_ubicacion_valida_el_identificador(pila):
    assert pila["public"].get("/publico/envios/no-es-un-uuid/ubicacion").status_code == 422
    inexistente = "00000000-0000-4000-8000-000000000000"
    assert pila["public"].get(f"/publico/envios/{inexistente}/ubicacion").status_code == 404


# --------------------------------------------------------------------------- #
# Constancia de las consultas
# --------------------------------------------------------------------------- #


def test_mirar_el_mapa_deja_constancia_una_vez_y_no_en_cada_refresco(
    pila, despachador, conductor, auditor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    _iniciar(pila, conductor, [envio_id])

    def consultas():
        return [
            r for r in _bitacora(pila, auditor)
            if r["accion"] == "ruta:seguir" and r["recurso"] == "ruta/lista"
        ]

    primera = pila["tracking"].get("/rutas", headers=despachador).json()
    assert len(consultas()) == 1
    assert consultas()[0]["actor_sub"] == "u-desp-a"

    for _ in range(3):
        refresco = pila["tracking"].get(
            "/rutas", headers=despachador, params={"testigo": primera["testigo"]}
        ).json()
        assert refresco["testigo"] == primera["testigo"]
    assert len(consultas()) == 1, "los refrescos con testigo vigente no se registran"

    pila["tracking"].get("/rutas", headers=despachador)
    assert len(consultas()) == 2, "sin testigo, la consulta se registra"


def test_un_testigo_ajeno_o_falso_no_evita_la_constancia(
    pila, despachador, coordinador, conductor, auditor
):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    _iniciar(pila, conductor, [envio_id])
    testigo_del_despachador = pila["tracking"].get("/rutas", headers=despachador).json()["testigo"]

    pila["tracking"].get("/rutas", headers=coordinador, params={"testigo": testigo_del_despachador})
    pila["tracking"].get("/rutas", headers=coordinador, params={"testigo": "inventado"})

    del_coordinador = [
        r for r in _bitacora(pila, auditor)
        if r["accion"] == "ruta:seguir" and r["actor_sub"] == "u-coord-a"
    ]
    assert len(del_coordinador) == 2


def test_el_testigo_no_sirve_como_token_de_acceso(pila, despachador, conductor):
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    _iniciar(pila, conductor, [envio_id])
    testigo = pila["tracking"].get("/rutas", headers=despachador).json()["testigo"]

    respuesta = pila["tracking"].get("/rutas", headers={"Authorization": f"Bearer {testigo}"})

    assert respuesta.status_code == 401


# --------------------------------------------------------------------------- #
# Empresas aprovisionadas antes de las rutas
# --------------------------------------------------------------------------- #

#: Lo que el conductor tenia guardado en la tabla antes de que existieran las
#: rutas: sin la anotacion del catalogo que conocia.
CONDUCTOR_ANTIGUO = {
    "clave": "conductor",
    "org_id": "org-andes",
    "nombre": "Conductor",
    "descripcion": "Reparte.",
    "operaciones": [
        "envio:consultar",
        "envio:listar",
        "evento:registrar",
        "evidencia:cargar",
        "maestro:consultar",
        "tablero:consultar",
    ],
    "integrado": True,
    "editable": True,
}


def test_un_conductor_de_una_empresa_ya_aprovisionada_puede_salir_a_ruta(
    pila, maestros, despachador, conductor
):
    maestros._guardar("org-andes", "ROL#conductor", dict(CONDUCTOR_ANTIGUO))
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)

    assert _iniciar(pila, conductor, [envio_id]).status_code == 201


def test_renombrar_el_rol_no_le_quita_las_operaciones_nuevas(
    pila, maestros, administrador, despachador, conductor
):
    maestros._guardar("org-andes", "ROL#conductor", dict(CONDUCTOR_ANTIGUO))

    respuesta = pila["auth"].post(
        "/roles/conductor", headers=administrador, json={"nombre": "Mensajero"}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert "ruta:operar" in respuesta.json()["rol"]["operaciones"]
    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    assert _iniciar(pila, conductor, [envio_id]).status_code == 201


def test_si_la_empresa_quita_la_ruta_al_conductor_sigue_quitada(
    pila, maestros, administrador, despachador, conductor
):
    # Aprovisionado como lo hace la siembra: con el catalogo que ya incluye rutas.
    fabrica = ROLES_INTEGRADOS["conductor"]
    maestros.guardar_rol(
        "org-andes",
        {
            "clave": fabrica.clave,
            "nombre": fabrica.nombre,
            "descripcion": fabrica.descripcion,
            "operaciones": sorted(str(o) for o in fabrica.operaciones),
        },
    )
    roles = pila["auth"].get("/roles", headers=administrador).json()["roles"]
    actual = next(r for r in roles if r["clave"] == "conductor")
    sin_ruta = [o for o in actual["operaciones"] if o != "ruta:operar"]

    guardado = pila["auth"].post(
        "/roles/conductor", headers=administrador, json={"operaciones": sin_ruta}
    )
    assert guardado.status_code == 200, guardado.text

    envio_id = _envio_en(pila, despachador, conductor, Estado.EN_TRANSITO)
    assert _iniciar(pila, conductor, [envio_id]).status_code == 403
