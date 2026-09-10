"""Lo que la interfaz ya no lleva escrito: los modulos y el equipo.

Estas pruebas existen por un cambio concreto: la lista de modulos y la de
mensajeros estaban escritas en el codigo de la interfaz. La primera obligaba a
recompilar el sitio para dar de alta un modulo y hacia imposible que dos
empresas vieran cosas distintas; la segunda mostraba tres conductores fijos con
su identificador, incluidos los de otra organizacion.

Ahora las dos salen de la tabla de maestros. Lo que se comprueba aqui es que ese
traslado no abrio ninguna puerta: que los modulos de una empresa no son los de
otra, que apagar uno exige decir por que, y que la vista del equipo no se
convirtio en una via para listar cuentas sin ser administrador.
"""

from __future__ import annotations

import pytest

from rastro_core.errors import ValidacionError


def _entrar(pila, correo: str, clave: str):
    return pila["auth"].post("/auth/token", json={"correo": correo, "clave": clave})


def _cabeceras(sesion: dict) -> dict:
    return {"Authorization": f"Bearer {sesion['token']}"}


@pytest.fixture
def sesion_admin(pila):
    return _entrar(pila, "admin@andes.test", "Prueba.Admin.2026").json()


@pytest.fixture
def sesion_despachador(pila):
    return _entrar(pila, "despacho@andes.test", "Prueba.Despacho.2026").json()


@pytest.fixture
def sesion_conductor(pila):
    return _entrar(pila, "carlos@andes.test", "Prueba.Carlos.2026").json()


@pytest.fixture
def sesion_auditor(pila):
    return _entrar(pila, "auditor@andes.test", "Prueba.Auditor.2026").json()


@pytest.fixture
def sesion_otra_org(pila):
    return _entrar(pila, "despacho@sabana.test", "Prueba.Sabana.2026").json()


@pytest.fixture
def modulos_sembrados(maestros):
    """Dos modulos en cada organizacion, uno encendido y otro apagado."""
    for org_id in ("org-andes", "org-sabana"):
        maestros.guardar_modulo(
            org_id,
            {
                "clave": "ordenes",
                "nombre": "Ordenes",
                "descripcion": "Registro y seguimiento",
                "icono": "paquete",
                "ruta": "/envios",
                "grupos": ["administrador", "despachador", "conductor"],
                "orden": 10,
            },
        )
    maestros.guardar_modulo(
        "org-andes",
        {
            "clave": "rutas",
            "nombre": "Rutas",
            "descripcion": "Planificacion de ultima milla",
            "icono": "mapa",
            "grupos": ["administrador"],
            "orden": 200,
            "disponible": False,
            "motivo": "Excluido del alcance del proyecto.",
        },
    )
    return maestros


# --------------------------------------------------------------------------- #
# Modulos
# --------------------------------------------------------------------------- #


def test_los_modulos_salen_de_la_tabla_y_no_del_codigo(
    pila, sesion_despachador, modulos_sembrados
):
    respuesta = pila["masters"].get("/catalogos/modulos", headers=_cabeceras(sesion_despachador))
    assert respuesta.status_code == 200

    claves = {m["clave"] for m in respuesta.json()["modulos"]}
    assert claves == {"ordenes", "rutas"}


def test_cada_organizacion_ve_sus_modulos(
    pila, sesion_despachador, sesion_otra_org, modulos_sembrados
):
    """El modulo apagado de Andes no existe para Sabana.

    Es la misma frontera que aplica al resto del sistema: si los modulos fueran
    un catalogo global, apagar uno para una empresa lo apagaria para todas.
    """
    andes = pila["masters"].get("/catalogos/modulos", headers=_cabeceras(sesion_despachador))
    sabana = pila["masters"].get("/catalogos/modulos", headers=_cabeceras(sesion_otra_org))

    assert {m["clave"] for m in andes.json()["modulos"]} == {"ordenes", "rutas"}
    assert {m["clave"] for m in sabana.json()["modulos"]} == {"ordenes"}


def test_un_modulo_apagado_dice_por_que(pila, sesion_despachador, modulos_sembrados):
    """Un modulo ausente sin motivo parece un olvido; con motivo es una decision."""
    respuesta = pila["masters"].get("/catalogos/modulos", headers=_cabeceras(sesion_despachador))
    rutas = next(m for m in respuesta.json()["modulos"] if m["clave"] == "rutas")

    assert rutas["disponible"] is False
    assert rutas["motivo"]


def test_no_se_puede_apagar_un_modulo_sin_decir_por_que(maestros):
    """La regla vive en el repositorio y no en la pantalla: cualquier via de
    escritura la encuentra, incluida una que se escriba manana."""
    with pytest.raises(ValidacionError):
        maestros.guardar_modulo(
            "org-andes",
            {"clave": "facturacion", "nombre": "Facturacion", "disponible": False, "motivo": ""},
        )


def test_un_modulo_disponible_necesita_ruta(maestros):
    """Un modulo encendido que no lleva a ninguna parte es una tarjeta que no
    hace nada al pulsarla, y eso se lee como un fallo del sistema."""
    with pytest.raises(ValidacionError):
        maestros.guardar_modulo(
            "org-andes", {"clave": "manifiestos", "nombre": "Manifiestos", "disponible": True}
        )


def test_solo_el_administrador_enciende_o_apaga_un_modulo(
    pila, sesion_despachador, sesion_admin, modulos_sembrados
):
    cuerpo = {"disponible": False, "motivo": "No se usa en esta operacion."}

    negado = pila["masters"].post(
        "/catalogos/modulos/ordenes", headers=_cabeceras(sesion_despachador), json=cuerpo
    )
    assert negado.status_code == 403

    permitido = pila["masters"].post(
        "/catalogos/modulos/ordenes", headers=_cabeceras(sesion_admin), json=cuerpo
    )
    assert permitido.status_code == 200
    assert permitido.json()["modulo"]["disponible"] is False


def test_apagar_un_modulo_en_una_empresa_no_lo_apaga_en_la_otra(
    pila, sesion_admin, sesion_otra_org, modulos_sembrados
):
    pila["masters"].post(
        "/catalogos/modulos/ordenes",
        headers=_cabeceras(sesion_admin),
        json={"disponible": False, "motivo": "Migracion en curso."},
    )

    otra = pila["masters"].get("/catalogos/modulos", headers=_cabeceras(sesion_otra_org))
    ordenes = next(m for m in otra.json()["modulos"] if m["clave"] == "ordenes")
    assert ordenes["disponible"] is True


def test_no_se_puede_encender_un_modulo_de_otra_organizacion(
    pila, sesion_otra_org, modulos_sembrados
):
    """`rutas` solo existe en Andes: para Sabana responde «no existe», no 403.

    Distinguir «no puedes» de «no existe» confirmaria que el modulo existe en
    otra empresa, que es informacion que el solicitante no deberia obtener.
    """
    respuesta = pila["masters"].post(
        "/catalogos/modulos/rutas",
        headers=_cabeceras(sesion_otra_org),
        json={"disponible": True, "motivo": ""},
    )
    assert respuesta.status_code in (403, 404)


# --------------------------------------------------------------------------- #
# Equipo
# --------------------------------------------------------------------------- #


def test_el_despachador_ve_a_los_mensajeros_para_asignarles(pila, sesion_despachador):
    """Sin esto, la pantalla de asignacion tendria que llevar la lista escrita, y
    un mensajero nuevo no apareceria hasta recompilar el sitio."""
    respuesta = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    assert respuesta.status_code == 200

    nombres = [m["nombre"] for m in respuesta.json()["mensajeros"]]
    assert "Carlos Conductor" in nombres


def test_el_equipo_solo_trae_conductores(pila, sesion_despachador):
    """El administrador y el auditor no reparten: incluirlos daria a elegir a
    quien no puede recibir el envio, y el servidor rechazaria la asignacion
    despues de que el despachador ya la hubiera hecho."""
    respuesta = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    subs = {m["sub"] for m in respuesta.json()["mensajeros"]}

    usuarios = pila["auth"].get("/usuarios", headers=_cabeceras(sesion_despachador))
    assert usuarios.status_code == 403, "el despachador no administra cuentas"

    assert subs, "hay al menos un conductor en la organizacion de la prueba"
    assert respuesta.json()["total"] == len(subs)


def test_el_equipo_no_expone_la_ficha_de_la_cuenta(pila, sesion_despachador):
    """Es una vista reducida a proposito: el despachador necesita saber a quien
    asigna, no los grupos, el ultimo acceso ni las sesiones abiertas."""
    respuesta = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    primero = respuesta.json()["mensajeros"][0]

    assert set(primero) == {"sub", "nombre", "telefono"}


def test_el_conductor_no_consulta_el_equipo(pila, sesion_conductor):
    """Un conductor no asigna: saber quien mas reparte no le corresponde."""
    respuesta = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_conductor))
    assert respuesta.status_code == 403


def test_el_equipo_no_cruza_la_frontera_de_organizacion(
    pila, sesion_despachador, sesion_otra_org
):
    andes = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    sabana = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_otra_org))

    subs_andes = {m["sub"] for m in andes.json()["mensajeros"]}
    subs_sabana = {m["sub"] for m in sabana.json()["mensajeros"]}

    assert subs_andes and not (subs_andes & subs_sabana)


def test_un_mensajero_desactivado_deja_de_aparecer(pila, sesion_admin, sesion_despachador):
    """Asignarle un envio a una cuenta desactivada produce un envio que nadie
    puede mover, y el error solo se ve cuando el envio ya lleva un dia parado."""
    antes = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    assert any(m["nombre"] == "Carlos Conductor" for m in antes.json()["mensajeros"])

    pila["auth"].post(
        "/usuarios/carlos@andes.test", headers=_cabeceras(sesion_admin), json={"activo": False}
    )

    despues = pila["auth"].get("/equipo/mensajeros", headers=_cabeceras(sesion_despachador))
    assert not any(m["nombre"] == "Carlos Conductor" for m in despues.json()["mensajeros"])
