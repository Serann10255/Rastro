"""Registro masivo, guias y exportacion.

Son las tres operaciones que un cliente corporativo hace a diario y que no
tienen sentido de una en una. Lo que se comprueba, ademas de que funcionen, es
que ninguna abre una via para saltarse el filtro por organizacion: hacer algo en
lote es exactamente donde se cuela un identificador ajeno sin que nadie lo mire.
"""

from __future__ import annotations

import csv
import io


def _entrar(pila, correo: str, clave: str) -> dict:
    return pila["auth"].post("/auth/token", json={"correo": correo, "clave": clave}).json()


def _cabeceras(sesion: dict) -> dict:
    return {"Authorization": f"Bearer {sesion['token']}"}


def _envio(indice: int, **extra) -> dict:
    return {
        "origen": {"linea": "Calle 100 #15-20", "ciudad": "Bogota"},
        "destino": {"linea": f"Calle {40 + indice} #10-{indice}", "ciudad": "Bogota"},
        "destinatario": {"nombre": f"Destinatario Lote {indice}", "telefono": "3000000000"},
        "descripcion": "Envio de lote",
        "orden_compra": f"OC-{indice:04d}",
        "bultos": 1,
        "peso_kg": 1.5,
        **extra,
    }


# --------------------------------------------------------------------------- #
# Registro masivo
# --------------------------------------------------------------------------- #


def test_un_lote_registra_todos_los_envios(pila, despachador):
    respuesta = pila["shipments"].post(
        "/envios/lote", headers=despachador, json={"envios": [_envio(i) for i in range(1, 11)]}
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["resumen"] == {"solicitados": 10, "creados": 10, "rechazados": 0}
    identificadores = {e["envio_id"] for e in cuerpo["creados"]}
    assert len(identificadores) == 10, "cada envio recibe su propio identificador"


def test_una_fila_mala_no_tumba_el_lote(pila, despachador):
    """Abortar el lote entero por una fila obligaria a corregir el archivo y
    reenviarlo completo, y quien despacha doscientos acabaria partiendolo a mano
    para encontrar cual falla."""
    envios = [_envio(i) for i in range(1, 6)]
    envios.append(_envio(99, tienda_id="tienda-que-no-existe"))

    cuerpo = pila["shipments"].post(
        "/envios/lote", headers=despachador, json={"envios": envios}
    ).json()

    assert cuerpo["resumen"] == {"solicitados": 6, "creados": 5, "rechazados": 1}
    rechazado = cuerpo["rechazados"][0]
    assert rechazado["indice"] == 5
    assert "tienda" in rechazado["motivo"].lower()
    assert rechazado["orden_compra"] == "OC-0099", "hay que poder localizar la fila"


def test_el_lote_deja_un_solo_eslabon_en_la_bitacora(pila, despachador, repositorio):
    """Doscientos eslabones por un despacho enterrarian el resto del historico."""
    antes = len(repositorio.listar_bitacora("org-andes", limite=2000))

    pila["shipments"].post(
        "/envios/lote", headers=despachador, json={"envios": [_envio(i) for i in range(1, 21)]}
    )

    registros = repositorio.listar_bitacora("org-andes", limite=2000)
    del_lote = [r for r in registros if r["recurso"] == "envio/lote"]

    assert len(del_lote) == 1
    assert del_lote[0]["detalle"] == {"solicitados": 20, "creados": 20, "rechazados": 0}
    assert len(registros) - antes == 1


def test_el_conductor_no_puede_registrar_un_lote(pila, conductor, repositorio):
    respuesta = pila["shipments"].post(
        "/envios/lote", headers=conductor, json={"envios": [_envio(1)]}
    )

    assert respuesta.status_code == 403
    denegados = [
        r for r in repositorio.listar_bitacora("org-andes", limite=100) if r["resultado"] == "DENY"
    ]
    assert denegados, "el intento en lote tambien queda registrado"


def test_los_envios_del_lote_llevan_el_codigo_de_estado(pila, despachador):
    cuerpo = pila["shipments"].post(
        "/envios/lote", headers=despachador, json={"envios": [_envio(1)]}
    ).json()

    assert cuerpo["creados"][0]["codigo_estado"] == 10


# --------------------------------------------------------------------------- #
# Referencias a datos maestros
# --------------------------------------------------------------------------- #


def test_el_envio_conserva_el_nombre_de_la_tienda_y_no_solo_su_identificador(
    pila, despachador
):
    """Un envio es un documento historico: si manana se renombra la tienda, debe
    seguir diciendo de donde salio en su momento."""
    creado = pila["shipments"].post(
        "/envios",
        headers=despachador,
        json=_envio(1, tienda_id="tienda-andes-1", cliente_id="cliente-andes-1"),
    ).json()["envio"]

    assert creado["tienda_nombre"] == "Centro de acopio"
    assert creado["cliente_nombre"] == "Distribuidora Kuma"
    assert creado["estacion_actual"] == "Centro de acopio"


def test_una_tienda_de_otra_organizacion_no_se_puede_referenciar(
    pila, despachador_otra_org
):
    respuesta = pila["shipments"].post(
        "/envios", headers=despachador_otra_org, json=_envio(1, tienda_id="tienda-andes-1")
    )
    assert respuesta.status_code == 404


# --------------------------------------------------------------------------- #
# Guias
# --------------------------------------------------------------------------- #


def test_las_guias_traen_lo_necesario_para_entregar_sin_abrir_el_sistema(
    pila, despachador, envio_creado
):
    respuesta = pila["shipments"].post(
        "/envios/etiquetas", headers=despachador, json={"envios": [envio_creado["envio_id"]]}
    )

    assert respuesta.status_code == 200
    etiqueta = respuesta.json()["etiquetas"][0]
    for campo in ("envio_id", "empresa", "destinatario", "direccion", "ciudad", "bultos"):
        assert campo in etiqueta, campo
    assert etiqueta["empresa"] == "Mensajeria Andes S.A.S."


def test_la_guia_no_lleva_el_valor_declarado(pila, despachador, envio_creado):
    """Pegarlo por fuera de la caja le dice a cualquiera cuanto vale lo de dentro."""
    etiqueta = pila["shipments"].post(
        "/envios/etiquetas", headers=despachador, json={"envios": [envio_creado["envio_id"]]}
    ).json()["etiquetas"][0]

    assert "valor_declarado" not in etiqueta


def test_pedir_guias_en_lote_no_es_una_via_para_ver_envios_ajenos(
    pila, despachador, despachador_otra_org, envio_creado
):
    """Cada envio se carga por el camino unico que aplica el filtro por
    organizacion; el lote no lo esquiva."""
    respuesta = pila["shipments"].post(
        "/envios/etiquetas",
        headers=despachador_otra_org,
        json={"envios": [envio_creado["envio_id"]]},
    )

    cuerpo = respuesta.json()
    assert cuerpo["etiquetas"] == []
    assert cuerpo["no_encontrados"] == [envio_creado["envio_id"]]


def test_se_generan_muchas_guias_de_una_vez(pila, despachador):
    lote = pila["shipments"].post(
        "/envios/lote", headers=despachador, json={"envios": [_envio(i) for i in range(1, 31)]}
    ).json()
    identificadores = [e["envio_id"] for e in lote["creados"]]

    etiquetas = pila["shipments"].post(
        "/envios/etiquetas", headers=despachador, json={"envios": identificadores}
    ).json()["etiquetas"]

    assert len(etiquetas) == 30


def test_hay_un_tope_de_guias_por_peticion(pila, despachador):
    """Sin tope, mil etiquetas agotan la memoria de la funcion y el fallo llega
    sin explicacion."""
    respuesta = pila["shipments"].post(
        "/envios/etiquetas", headers=despachador, json={"envios": [f"id-{i}" for i in range(500)]}
    )
    assert respuesta.status_code == 422


# --------------------------------------------------------------------------- #
# Exportacion
# --------------------------------------------------------------------------- #


def test_la_exportacion_produce_un_csv_legible(pila, despachador, envio_creado):
    respuesta = pila["shipments"].get("/envios/exportar", headers=despachador)

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]
    assert "attachment" in respuesta.headers["content-disposition"]

    filas = list(csv.DictReader(io.StringIO(respuesta.text)))
    assert len(filas) == 1
    fila = filas[0]
    assert fila["envio_id"] == envio_creado["envio_id"]
    assert fila["destinatario"] == "Laura Mejia Rios"
    # El codigo numerico hace interpretable el archivo para un sistema que no
    # habla espanol.
    assert fila["codigo_estado"] == "10"
    assert fila["estado"] == "CREADO"


def test_la_exportacion_no_incluye_envios_de_otra_organizacion(
    pila, despachador_otra_org, envio_creado
):
    respuesta = pila["shipments"].get("/envios/exportar", headers=despachador_otra_org)
    filas = list(csv.DictReader(io.StringIO(respuesta.text)))
    assert filas == []


def test_el_conductor_solo_exporta_sus_envios(pila, despachador, conductor, envio_creado):
    respuesta = pila["shipments"].get("/envios/exportar", headers=conductor)
    filas = list(csv.DictReader(io.StringIO(respuesta.text)))
    assert filas == [], "el envio creado no le fue asignado"
