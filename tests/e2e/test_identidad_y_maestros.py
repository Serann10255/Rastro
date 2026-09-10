"""Autenticacion real, administracion de cuentas, datos maestros y tablero.

Lo que se comprueba aqui no es que las pantallas funcionen, sino que las
promesas de seguridad se sostienen: que la contrasena nunca se almacena en
claro, que un fallo de credenciales no permite enumerar cuentas, que un token de
refresco no sirve para operar, y que ninguna de las funciones nuevas abre una
via para saltarse el aislamiento entre organizaciones.
"""

from __future__ import annotations

import pytest

from rastro_core.passwords import derivar, necesita_rederivar, verificar


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
def sesion_otra_org(pila):
    return _entrar(pila, "despacho@sabana.test", "Prueba.Sabana.2026").json()


# --------------------------------------------------------------------------- #
# Contrasenas
# --------------------------------------------------------------------------- #


def test_la_contrasena_nunca_se_almacena_en_claro(maestros):
    registro = maestros.buscar_usuario_por_correo("admin@andes.test")
    almacenado = registro["hash_clave"]

    assert "Prueba.Admin.2026" not in almacenado
    assert almacenado.startswith("pbkdf2_sha256$")
    assert verificar("Prueba.Admin.2026", almacenado)
    assert not verificar("Prueba.Admin.2027", almacenado)


def test_dos_usuarios_con_la_misma_clave_tienen_hashes_distintos():
    """Cada derivacion usa su propia sal.

    Sin sal, dos contrasenas iguales producirian el mismo hash y una tabla
    precalculada las revelaria las dos de una vez.
    """
    assert derivar("la-misma-contrasena") != derivar("la-misma-contrasena")


def test_un_hash_con_parametros_debiles_se_marca_para_rederivar():
    """Permite subir el coste con el tiempo sin invalidar lo ya almacenado."""
    debil = derivar("contrasena-de-prueba", iteraciones=1_000)
    assert necesita_rederivar(debil, iteraciones=600_000)
    assert not necesita_rederivar(debil, iteraciones=1_000)


def test_un_hash_corrupto_no_lanza_sino_que_falla():
    """Un registro corrupto no debe distinguirse de una clave incorrecta."""
    for basura in ("", "no-es-un-hash", "pbkdf2_sha256$mal", "otro$1$2$3"):
        assert verificar("cualquier-cosa", basura) is False


# --------------------------------------------------------------------------- #
# Inicio de sesion
# --------------------------------------------------------------------------- #


def test_el_inicio_de_sesion_devuelve_usuario_y_su_organizacion(pila):
    respuesta = _entrar(pila, "despacho@andes.test", "Prueba.Despacho.2026")

    assert respuesta.status_code == 200
    sesion = respuesta.json()
    assert sesion["usuario"]["org_id"] == "org-andes"
    assert sesion["usuario"]["grupos"] == ["despachador"]
    assert sesion["token"] and sesion["refresco"]
    assert "hash_clave" not in str(sesion)


def test_el_correo_no_distingue_mayusculas(pila):
    """La misma persona no debe poder tener dos cuentas por escribirlo distinto."""
    assert _entrar(pila, "Despacho@Andes.Test", "Prueba.Despacho.2026").status_code == 200


def test_una_cuenta_desactivada_no_puede_entrar(pila, sesion_admin):
    pila["auth"].post(
        "/usuarios/carlos@andes.test",
        headers=_cabeceras(sesion_admin),
        json={"activo": False},
    )
    respuesta = _entrar(pila, "carlos@andes.test", "Prueba.Carlos.2026")

    assert respuesta.status_code == 401
    # El mismo mensaje que una clave incorrecta: decir "cuenta desactivada"
    # confirmaria que la cuenta existe.
    assert respuesta.json()["mensaje"] == "Correo o clave incorrectos."


def test_un_intento_fallido_queda_en_la_bitacora(pila, repositorio):
    _entrar(pila, "despacho@andes.test", "clave-que-no-sirve")

    registros = repositorio.listar_bitacora("org-andes", limite=100)
    fallidos = [
        r
        for r in registros
        if r["accion"] == "sesion:iniciar" and r["resultado"] == "DENY"
    ]
    assert fallidos, "sin este registro, un ataque por fuerza bruta no deja rastro"
    assert fallidos[-1]["detalle"]["motivo"] == "clave_incorrecta"


# --------------------------------------------------------------------------- #
# Sesion: acceso, refresco y cierre
# --------------------------------------------------------------------------- #


def test_el_token_de_refresco_no_sirve_para_operar(pila, sesion_despachador):
    """Si sirviera, robarlo equivaldria a una sesion permanente: vive doce horas."""
    cabecera = {"Authorization": f"Bearer {sesion_despachador['refresco']}"}
    assert pila["shipments"].get("/envios", headers=cabecera).status_code == 401


def test_el_refresco_se_rota_y_el_anterior_deja_de_valer(pila, sesion_despachador):
    """Asi, si alguien roba uno y lo usa, el legitimo deja de funcionar y el
    robo se nota en lugar de convivir en silencio."""
    primero = sesion_despachador["refresco"]

    renovada = pila["auth"].post("/auth/refrescar", json={"refresco": primero})
    assert renovada.status_code == 200
    assert renovada.json()["token"] != sesion_despachador["token"]

    reutilizado = pila["auth"].post("/auth/refrescar", json={"refresco": primero})
    assert reutilizado.status_code == 401


def test_cerrar_sesion_la_revoca_en_el_servidor(pila, sesion_despachador):
    """Borrar el token del navegador basta para el uso normal, pero no si el
    token ya se copio. Revocar es lo que hace que el cierre signifique algo."""
    pila["auth"].post("/auth/salir", headers=_cabeceras(sesion_despachador))

    reutilizado = pila["auth"].post(
        "/auth/refrescar", json={"refresco": sesion_despachador["refresco"]}
    )
    assert reutilizado.status_code == 401


def test_cambiar_la_clave_cierra_las_demas_sesiones(pila):
    """Si se cambia porque se sospecha que alguien la conoce, dejar sus sesiones
    abiertas no serviria de nada."""
    primera = _entrar(pila, "carlos@andes.test", "Prueba.Carlos.2026").json()
    segunda = _entrar(pila, "carlos@andes.test", "Prueba.Carlos.2026").json()

    cambio = pila["auth"].post(
        "/auth/clave",
        headers=_cabeceras(segunda),
        json={"clave_actual": "Prueba.Carlos.2026", "clave_nueva": "Carlos.Nueva.2026"},
    )
    assert cambio.status_code == 200

    assert pila["auth"].post("/auth/refrescar", json={"refresco": primera["refresco"]}).status_code == 401
    assert _entrar(pila, "carlos@andes.test", "Carlos.Nueva.2026").status_code == 200
    assert _entrar(pila, "carlos@andes.test", "Prueba.Carlos.2026").status_code == 401


def test_no_se_cambia_la_clave_sin_saber_la_actual(pila, sesion_despachador):
    respuesta = pila["auth"].post(
        "/auth/clave",
        headers=_cabeceras(sesion_despachador),
        json={"clave_actual": "no-es-la-actual", "clave_nueva": "Otra.Clave.Larga.2026"},
    )
    assert respuesta.status_code == 401


def test_la_sesion_expone_la_empresa_del_usuario(pila, sesion_despachador):
    cuerpo = pila["auth"].get("/auth/yo", headers=_cabeceras(sesion_despachador)).json()

    assert cuerpo["empresa"]["org_id"] == "org-andes"
    assert cuerpo["empresa"]["nombre"] == "Mensajeria Andes S.A.S."
    assert cuerpo["usuario"]["correo"] == "despacho@andes.test"


# --------------------------------------------------------------------------- #
# Administracion de cuentas
# --------------------------------------------------------------------------- #


def test_solo_el_administrador_crea_cuentas(pila, sesion_despachador):
    """Quien puede crear usuarios puede concederse cualquier permiso: es la
    operacion mas sensible del sistema."""
    respuesta = pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_despachador),
        json={
            "correo": "intruso@andes.test",
            "nombre": "Intruso Test",
            "clave": "Clave.Suficientemente.Larga",
            "grupos": ["administrador"],
        },
    )
    assert respuesta.status_code == 403


def test_el_usuario_creado_puede_entrar(pila, sesion_admin):
    creado = pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_admin),
        json={
            "correo": "nuevo@andes.test",
            "nombre": "Nuevo Operario",
            "clave": "Nuevo.Operario.2026",
            "grupos": ["conductor"],
        },
    )
    assert creado.status_code == 201

    sesion = _entrar(pila, "nuevo@andes.test", "Nuevo.Operario.2026")
    assert sesion.status_code == 200
    assert sesion.json()["usuario"]["org_id"] == "org-andes"


def test_una_cuenta_se_crea_siempre_en_la_organizacion_de_quien_la_crea(pila, sesion_admin):
    """Aceptar la organizacion como dato de entrada permitiria crear cuentas en
    otra empresa."""
    pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_admin),
        json={
            "correo": "colado@sabana.test",
            "nombre": "Colado Test",
            "clave": "Colado.Test.2026",
            "grupos": ["administrador"],
            "org_id": "org-sabana",
        },
    )
    sesion = _entrar(pila, "colado@sabana.test", "Colado.Test.2026").json()
    assert sesion["usuario"]["org_id"] == "org-andes"


def test_un_correo_no_se_registra_dos_veces(pila, sesion_admin):
    assert (
        pila["auth"]
        .post(
            "/usuarios",
            headers=_cabeceras(sesion_admin),
            json={
                "correo": "despacho@andes.test",
                "nombre": "Duplicado Test",
                "clave": "Duplicado.Test.2026",
                "grupos": ["conductor"],
            },
        )
        .status_code
        == 409
    )


def test_una_clave_corta_se_rechaza(pila, sesion_admin):
    respuesta = pila["auth"].post(
        "/usuarios",
        headers=_cabeceras(sesion_admin),
        json={
            "correo": "corta@andes.test",
            "nombre": "Clave Corta",
            "clave": "corta",
            "grupos": ["conductor"],
        },
    )
    assert respuesta.status_code == 422


def test_no_se_puede_dejar_la_organizacion_sin_administrador(pila, sesion_admin):
    """Sin esta comprobacion, quitarse a uno mismo el rol deja la empresa sin
    nadie que pueda crear usuarios, y solo se arregla desde la base de datos."""
    respuesta = pila["auth"].post(
        "/usuarios/admin@andes.test",
        headers=_cabeceras(sesion_admin),
        json={"grupos": ["conductor"]},
    )
    assert respuesta.status_code == 409
    assert "administrador" in respuesta.json()["mensaje"]


# --------------------------------------------------------------------------- #
# Datos maestros
# --------------------------------------------------------------------------- #


def test_el_despachador_consulta_maestros_pero_no_los_edita(pila, sesion_despachador):
    """Elegir tienda al registrar un envio es operacion; cambiar su direccion
    afecta a toda la empresa."""
    cabecera = _cabeceras(sesion_despachador)
    assert pila["masters"].get("/tiendas", headers=cabecera).status_code == 200

    respuesta = pila["masters"].post(
        "/tiendas",
        headers=cabecera,
        json={
            "nombre": "Tienda Nueva",
            "ciudad": "Bogota",
            "departamento": "Cundinamarca",
        },
    )
    assert respuesta.status_code == 403


def test_el_administrador_crea_y_edita_maestros(pila, sesion_admin):
    cabecera = _cabeceras(sesion_admin)

    creada = pila["masters"].post(
        "/tiendas",
        headers=cabecera,
        json={
            "nombre": "Punto Kennedy",
            "codigo": "and-ken",
            "tipo": "tienda",
            "ciudad": "Bogota",
            "departamento": "Cundinamarca",
        },
    )
    assert creada.status_code == 201
    tienda = creada.json()["tienda"]
    assert tienda["codigo"] == "AND-KEN", "el codigo se normaliza a mayusculas"

    actualizada = pila["masters"].post(
        f"/tiendas/{tienda['tienda_id']}",
        headers=cabecera,
        json={
            "nombre": "Punto Kennedy Sur",
            "ciudad": "Bogota",
            "departamento": "Cundinamarca",
        },
    )
    assert actualizada.json()["tienda"]["nombre"] == "Punto Kennedy Sur"
    assert actualizada.json()["tienda"]["tienda_id"] == tienda["tienda_id"]


@pytest.mark.parametrize("recurso", ["tiendas", "clientes", "transportistas"])
def test_los_maestros_no_cruzan_la_frontera_de_organizacion(
    pila, sesion_despachador, sesion_otra_org, recurso
):
    propios = pila["masters"].get(f"/{recurso}", headers=_cabeceras(sesion_despachador)).json()
    ajenos = pila["masters"].get(f"/{recurso}", headers=_cabeceras(sesion_otra_org)).json()

    assert propios["total"] >= 1
    assert ajenos["total"] == 0, "la otra organizacion no tiene maestros sembrados"


def test_el_catalogo_de_estados_se_sirve_desde_el_servidor(pila):
    """Para que la interfaz no lo duplique y se desincronice al anadir estados."""
    estados = pila["masters"].get("/catalogos/estados").json()["estados"]

    codigos = [e["codigo"] for e in estados]
    assert codigos == sorted(codigos)
    assert len(codigos) == len(set(codigos))
    assert {e["estado"] for e in estados} >= {"CREADO", "ENTREGADO", "DEVUELTO", "CANCELADO"}


# --------------------------------------------------------------------------- #
# Tablero
# --------------------------------------------------------------------------- #


def test_el_tablero_lleva_los_datos_de_la_empresa(pila, sesion_despachador, envio_creado):
    cuerpo = pila["dashboard"].get("/tablero", headers=_cabeceras(sesion_despachador)).json()

    assert cuerpo["empresa"]["nombre"] == "Mensajeria Andes S.A.S."
    assert cuerpo["totales"]["envios"] >= 1
    assert cuerpo["alcance"] == "organizacion"


def test_el_tablero_incluye_los_estados_en_cero(pila, sesion_despachador, envio_creado):
    """Mostrar solo los que tienen envios haria que el tablero cambiara de forma
    entre una carga y otra, y que un estado en cero pasara inadvertido."""
    cuerpo = pila["dashboard"].get("/tablero", headers=_cabeceras(sesion_despachador)).json()

    estados = {e["estado"]: e["cantidad"] for e in cuerpo["por_estado"]}
    assert len(estados) == 9
    assert estados["ENTREGADO"] == 0


def test_el_conductor_ve_el_tablero_acotado_a_sus_envios(pila, sesion_conductor, envio_creado):
    cuerpo = pila["dashboard"].get("/tablero", headers=_cabeceras(sesion_conductor)).json()

    assert cuerpo["alcance"] == "propios"
    assert cuerpo["totales"]["envios"] == 0, "el envio creado no le fue asignado"
    assert cuerpo["equipo"] is None, "la composicion del equipo no es asunto del conductor"


def test_el_tablero_de_una_organizacion_no_cuenta_envios_de_otra(
    pila, sesion_otra_org, envio_creado
):
    """Un total tambien es informacion: no puede incluir envios ajenos."""
    cuerpo = pila["dashboard"].get("/tablero", headers=_cabeceras(sesion_otra_org)).json()

    assert cuerpo["empresa"]["org_id"] == "org-sabana"
    assert cuerpo["totales"]["envios"] == 0


def test_la_serie_diaria_incluye_los_dias_sin_movimiento(
    pila, sesion_despachador, envio_creado
):
    """Omitirlos comprime el eje y hace parecer continua una operacion que tuvo
    un fin de semana en medio."""
    cuerpo = pila["dashboard"].get(
        "/tablero?dias=7", headers=_cabeceras(sesion_despachador)
    ).json()

    assert len(cuerpo["serie_diaria"]) == 7
    fechas = [d["fecha"] for d in cuerpo["serie_diaria"]]
    assert fechas == sorted(fechas)
