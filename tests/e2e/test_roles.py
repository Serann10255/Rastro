"""Roles configurables por organizacion.

Abrir la configuracion de permisos es lo mas delicado que se ha hecho en este
sistema: mal resuelto, convierte la matriz de autorizacion en un formulario que
cualquiera con acceso puede rellenar a su favor. Lo que estas pruebas fijan no
es que la pantalla funcione, sino que las cuatro barreras que la hacen segura
siguen en pie:

1. Un rol solo puede contener operaciones del catalogo del codigo.
2. Nadie puede conceder un permiso que no tiene.
3. El administrador no se edita, y siempre lo tiene todo.
4. Los roles de una organizacion no son los de otra.
"""

from __future__ import annotations

import pytest

from rastro_core.authz import Operacion


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
def sesion_auditor(pila):
    return _entrar(pila, "auditor@andes.test", "Prueba.Auditor.2026").json()


@pytest.fixture
def sesion_otra_org(pila):
    return _entrar(pila, "despacho@sabana.test", "Prueba.Sabana.2026").json()


# --------------------------------------------------------------------------- #
# Catalogo
# --------------------------------------------------------------------------- #


def test_el_catalogo_de_operaciones_cubre_todas_las_que_existen(pila):
    """Si una operacion nueva no aparece en el catalogo, ningun rol puede
    concederla desde la pantalla y nadie sabria que existe."""
    areas = pila["auth"].get("/auth/roles").json()["areas"]
    catalogadas = {o["operacion"] for area in areas for o in area["operaciones"]}

    assert catalogadas == {str(o) for o in Operacion}


def test_cada_operacion_del_catalogo_explica_que_hace(pila):
    """Marcar casillas llamadas `evento:reanudar` sin saber que significan es
    firmar sin leer."""
    areas = pila["auth"].get("/auth/roles").json()["areas"]
    for area in areas:
        for operacion in area["operaciones"]:
            assert operacion["descripcion"].strip()


# --------------------------------------------------------------------------- #
# Lectura
# --------------------------------------------------------------------------- #


def test_el_administrador_ve_los_roles_con_cuantas_cuentas_los_usan(pila, sesion_admin):
    respuesta = pila["auth"].get("/roles", headers=_cabeceras(sesion_admin))
    assert respuesta.status_code == 200

    roles = {r["clave"]: r for r in respuesta.json()["roles"]}
    assert {"administrador", "coordinador", "despachador", "conductor", "auditor"} <= set(roles)
    assert roles["administrador"]["cuentas"] >= 1
    assert roles["administrador"]["editable"] is False


def test_el_despachador_no_consulta_los_roles(pila, sesion_despachador):
    """Ver quien puede hacer que es informacion de administracion."""
    respuesta = pila["auth"].get("/roles", headers=_cabeceras(sesion_despachador))
    assert respuesta.status_code == 403


def test_el_auditor_consulta_los_roles_pero_no_los_cambia(pila, sesion_auditor):
    """El mapa de quien tiene que permiso es objeto de la auditoria."""
    assert pila["auth"].get("/roles", headers=_cabeceras(sesion_auditor)).status_code == 200

    respuesta = pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_auditor),
        json={"clave": "inventado", "nombre": "Inventado", "operaciones": ["envio:crear"]},
    )
    assert respuesta.status_code == 403


# --------------------------------------------------------------------------- #
# Crear y editar
# --------------------------------------------------------------------------- #


def test_un_rol_nuevo_concede_exactamente_lo_que_declara(pila, sesion_admin, maestros):
    creado = pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={
            "clave": "supervisor-turno",
            "nombre": "Supervisor de turno",
            "descripcion": "Ve la operacion y autoriza detenidos, sin registrar envios.",
            "operaciones": ["envio:listar", "envio:consultar", "evento:reanudar"],
        },
    )
    assert creado.status_code == 201

    from rastro_core.authz import operaciones_de

    definiciones = maestros.definiciones_de_rol("org-andes")
    concedidas = operaciones_de(["supervisor-turno"], definiciones)

    assert concedidas == {
        Operacion.ENVIO_LISTAR,
        Operacion.ENVIO_CONSULTAR,
        Operacion.EVENTO_REANUDAR,
    }


def test_un_rol_no_puede_conceder_una_operacion_inventada(pila, sesion_admin):
    """La barrera principal: el catalogo esta en el codigo y es cerrado."""
    respuesta = pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={
            "clave": "dios",
            "nombre": "Dios",
            "operaciones": ["envio:crear", "sistema:todo", "borrar:bitacora"],
        },
    )
    assert respuesta.status_code == 400
    assert "sistema:todo" in respuesta.json()["mensaje"]


def test_un_rol_sin_operaciones_se_rechaza(pila, sesion_admin):
    respuesta = pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={"clave": "vacio", "nombre": "Vacio", "operaciones": []},
    )
    assert respuesta.status_code == 422


def test_el_rol_de_administrador_no_se_edita(pila, sesion_admin):
    """Es el seguro contra que una organizacion se quede sin nadie que entre."""
    respuesta = pila["auth"].post(
        "/roles/administrador",
        headers=_cabeceras(sesion_admin),
        json={"operaciones": ["envio:listar"]},
    )
    assert respuesta.status_code in (400, 404)


def test_editar_un_rol_integrado_cambia_lo_que_concede(pila, sesion_admin, maestros):
    """Personalizar un rol de fabrica: el despachador de esta empresa tambien
    autoriza detenidos."""
    from rastro_core.authz import operaciones_de

    pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={
            "clave": "despachador",
            "nombre": "Despachador",
            "operaciones": ["envio:crear", "envio:listar", "envio:consultar", "evento:reanudar"],
        },
    )

    definiciones = maestros.definiciones_de_rol("org-andes")
    assert Operacion.EVENTO_REANUDAR in operaciones_de(["despachador"], definiciones)
    assert Operacion.ENVIO_ASIGNAR not in operaciones_de(["despachador"], definiciones)


def test_el_administrador_conserva_todo_aunque_la_tabla_diga_otra_cosa(maestros):
    """La tabla no manda sobre el administrador. Si alguien escribiera un
    registro recortandolo -por error o a proposito- el sistema lo ignora."""
    from rastro_core.authz import operaciones_de

    maestros._guardar(
        "org-andes",
        "ROL#administrador",
        {"clave": "administrador", "nombre": "Administrador", "operaciones": ["envio:listar"]},
    )

    definiciones = maestros.definiciones_de_rol("org-andes")
    concedidas = operaciones_de(["administrador"], definiciones)

    assert Operacion.USUARIO_CREAR in concedidas
    assert Operacion.ROL_ADMINISTRAR in concedidas


# --------------------------------------------------------------------------- #
# Escalada de privilegios
# --------------------------------------------------------------------------- #


def test_nadie_concede_un_permiso_que_no_tiene(pila, maestros, cabeceras):
    """La barrera que sostiene todo lo demas.

    Hoy solo el administrador administra roles y las tiene todas, de modo que no
    cambia nada. El dia que se delegue `rol:administrar` en otro rol, esto es lo
    que impide que se promocione a si mismo.
    """
    maestros.guardar_rol(
        "org-andes",
        {
            "clave": "jefe-operaciones",
            "nombre": "Jefe de operaciones",
            "operaciones": ["rol:administrar", "rol:consultar", "envio:listar"],
        },
    )

    jefe = cabeceras("u-jefe", "org-andes", ["jefe-operaciones"])

    permitido = pila["auth"].post(
        "/roles",
        headers=jefe,
        json={"clave": "ayudante", "nombre": "Ayudante", "operaciones": ["envio:listar"]},
    )
    assert permitido.status_code == 201, "puede conceder lo que el mismo tiene"

    negado = pila["auth"].post(
        "/roles",
        headers=jefe,
        json={"clave": "ayudante-plus", "nombre": "Ayudante", "operaciones": ["usuario:crear"]},
    )
    assert negado.status_code == 403
    assert "usuario:crear" in negado.json()["mensaje"]


def test_la_escalada_rechazada_queda_en_la_bitacora(pila, maestros, cabeceras, repositorio):
    """Un intento de concederse permisos es exactamente lo que un auditor busca."""
    maestros.guardar_rol(
        "org-andes",
        {
            "clave": "jefe-turno",
            "nombre": "Jefe de turno",
            "operaciones": ["rol:administrar", "envio:listar"],
        },
    )
    pila["auth"].post(
        "/roles",
        headers=cabeceras("u-jefe2", "org-andes", ["jefe-turno"]),
        json={"clave": "atajo", "nombre": "Atajo", "operaciones": ["bitacora:consultar"]},
    )

    registros = repositorio.listar_bitacora("org-andes", limite=50)
    escaladas = [
        r for r in registros if (r.get("detalle") or {}).get("motivo") == "escalada_de_privilegios"
    ]
    assert escaladas, "el intento tiene que quedar registrado"
    assert escaladas[0]["resultado"] == "DENY"


# --------------------------------------------------------------------------- #
# Aislamiento y consistencia
# --------------------------------------------------------------------------- #


def test_los_roles_de_una_organizacion_no_son_los_de_otra(pila, sesion_admin, maestros):
    pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={"clave": "solo-andes", "nombre": "Solo Andes", "operaciones": ["envio:listar"]},
    )

    assert "solo-andes" in maestros.definiciones_de_rol("org-andes")
    assert "solo-andes" not in maestros.definiciones_de_rol("org-sabana")


def test_no_se_asigna_a_una_cuenta_un_rol_que_no_existe(pila, sesion_admin):
    """Un nombre mal escrito crearia una cuenta sin poder hacer nada, y nadie
    sabria por que esa persona no puede trabajar."""
    respuesta = pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_admin),
        json={
            "correo": "nuevo@andes.test",
            "nombre": "Persona Nueva",
            "clave": "una clave larga de verdad",
            "grupos": ["despachadorr"],
        },
    )
    assert respuesta.status_code == 400
    assert "despachadorr" in respuesta.json()["mensaje"]


def test_un_rol_en_uso_no_se_elimina(pila, sesion_admin, maestros):
    maestros.guardar_rol(
        "org-andes",
        {"clave": "temporal", "nombre": "Temporal", "operaciones": ["envio:listar"]},
    )
    pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_admin),
        json={
            "correo": "temporal@andes.test",
            "nombre": "Cuenta Temporal",
            "clave": "una clave larga de verdad",
            "grupos": ["temporal"],
        },
    )

    respuesta = pila["auth"].post(
        "/roles/temporal/eliminar", headers=_cabeceras(sesion_admin)
    )
    assert respuesta.status_code == 409
    assert "temporal@andes.test" in str(respuesta.json()["detalle"])


def test_un_rol_de_fabrica_no_se_elimina(pila, sesion_admin):
    respuesta = pila["auth"].post("/roles/conductor/eliminar", headers=_cabeceras(sesion_admin))
    assert respuesta.status_code == 400


def test_un_rol_no_puede_operar_y_auditar_a_la_vez(pila, sesion_admin):
    """El control que sostiene el resto: quien revisa el registro de lo que se
    hizo no puede ser quien lo hizo. Se comprueba en el servidor, en el unico
    camino de escritura, y no en la pantalla."""
    respuesta = pila["auth"].post(
        "/roles",
        headers=_cabeceras(sesion_admin),
        json={
            "clave": "controller",
            "nombre": "Controller",
            "operaciones": ["envio:crear", "bitacora:consultar"],
        },
    )
    assert respuesta.status_code == 400
    assert "bitacora" in respuesta.json()["mensaje"]


def test_una_cuenta_no_puede_ser_operador_y_auditor(pila, sesion_admin):
    """La misma regla sobre la suma de los roles de la cuenta.

    Sin esto, un administrador podria anadirse el rol de auditor: ningun rol
    rompe la regla por separado, y la suma si.
    """
    respuesta = pila["auth"].post(
        "/usuarios/admin@andes.test",
        headers=_cabeceras(sesion_admin),
        json={"grupos": ["administrador", "auditor"]},
    )
    assert respuesta.status_code == 400
    assert "auditar" in respuesta.json()["mensaje"]
