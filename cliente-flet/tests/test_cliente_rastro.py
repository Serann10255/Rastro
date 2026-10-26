"""Cliente de Rastro: renovación de la sesión y traducción de errores.

Son las reglas de `web/src/api/cliente.ts`, probadas contra un servidor
simulado con `httpx.MockTransport`.
"""

import asyncio
import json

import httpx
import pytest

from comun import http
from comun.http import ErrorApi
from rastro_app.api import ClienteRastro

SESION = {"token": "viejo", "refresco": "refresco-1", "usuario": {"sub": "u-1"}}


def instalar(manejador):
    http._cliente = httpx.AsyncClient(transport=httpx.MockTransport(manejador))


@pytest.fixture(autouse=True)
def limpiar():
    yield
    http._cliente = None


def cliente_con_sesion():
    cliente = ClienteRastro({"url_publica_api": "http://api"})
    cliente.sesion = dict(SESION)
    return cliente


def test_un_401_renueva_la_sesion_y_repite_la_peticion():
    llamadas = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        llamadas.append((peticion.url.path, peticion.headers.get("authorization")))
        if peticion.url.path == "/auth/refrescar":
            return httpx.Response(200, json={"token": "nuevo", "refresco": "refresco-2", "usuario": {"sub": "u-1"}})
        if peticion.headers.get("authorization") == "Bearer viejo":
            return httpx.Response(401, json={"codigo": "NO_AUTENTICADO", "mensaje": "Token caducado."})
        return httpx.Response(200, json={"envios": [], "total": 0})

    instalar(manejador)
    cliente = cliente_con_sesion()
    cambios = []
    cliente.al_cambiar_sesion = cambios.append

    resultado = asyncio.run(cliente.listar_envios())

    assert resultado == {"envios": [], "total": 0}
    assert [ruta for ruta, _ in llamadas] == ["/envios", "/auth/refrescar", "/envios"]
    assert cliente.sesion["token"] == "nuevo"
    assert cambios and cambios[-1]["token"] == "nuevo"


def test_varias_peticiones_caducadas_comparten_una_sola_renovacion():
    """El refresco se rota: diez renovaciones simultáneas dejarían nueve
    inválidas y cerrarían la sesión de alguien que no hizo nada malo."""
    renovaciones = 0

    async def manejador(peticion: httpx.Request) -> httpx.Response:
        nonlocal renovaciones
        if peticion.url.path == "/auth/refrescar":
            renovaciones += 1
            await asyncio.sleep(0.05)
            return httpx.Response(200, json={"token": "nuevo", "refresco": "r2", "usuario": {"sub": "u-1"}})
        if peticion.headers.get("authorization") == "Bearer viejo":
            return httpx.Response(401, json={"codigo": "NO_AUTENTICADO", "mensaje": "Token caducado."})
        return httpx.Response(200, json={"ok": True})

    instalar(manejador)
    cliente = cliente_con_sesion()

    async def cinco_a_la_vez():
        return await asyncio.gather(*(cliente.listar_envios() for _ in range(5)))

    assert asyncio.run(cinco_a_la_vez()) == [{"ok": True}] * 5
    assert renovaciones == 1


def test_si_la_renovacion_falla_la_sesion_se_cierra():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"codigo": "NO_AUTENTICADO", "mensaje": "La sesión fue cerrada."})

    instalar(manejador)
    cliente = cliente_con_sesion()
    cambios = []
    cliente.al_cambiar_sesion = cambios.append

    with pytest.raises(ErrorApi) as error:
        asyncio.run(cliente.tablero())

    assert error.value.codigo == "NO_AUTENTICADO"
    assert cliente.sesion is None
    assert cambios == [None]


def test_credenciales_rechazadas_no_cierran_una_sesion_abierta():
    """Un 401 de una ruta abierta dice que el servidor rechazó unas
    credenciales, no que la sesión guardada caducó."""

    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"codigo": "NO_AUTENTICADO", "mensaje": "Correo o contraseña incorrectos."})

    instalar(manejador)
    cliente = cliente_con_sesion()

    with pytest.raises(ErrorApi) as error:
        asyncio.run(cliente.entrar("x@y.z", "mala"))

    assert error.value.mensaje == "Correo o contraseña incorrectos."
    assert cliente.sesion is not None


def test_un_fallo_de_red_es_sin_conexion():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=peticion)

    instalar(manejador)
    with pytest.raises(ErrorApi) as error:
        asyncio.run(cliente_con_sesion().tablero())
    assert error.value.codigo == "SIN_CONEXION" and error.value.estado == 0


def test_validacion_de_fastapi_nombra_el_campo():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        detalle = [{"loc": ["body", "destino", "linea"], "msg": "Field required"}]
        return httpx.Response(422, content=json.dumps({"detail": detalle}))

    instalar(manejador)
    with pytest.raises(ErrorApi) as error:
        asyncio.run(cliente_con_sesion().crear_envio({}))
    assert error.value.codigo == "SOLICITUD_INVALIDA"
    assert "«linea»" in error.value.mensaje


def test_transiciones_permitidas_del_error():
    error = ErrorApi(400, "TRANSICION_INVALIDA", "No.", {"permitidas": ["ASIGNADO", "INCIDENCIA"]})
    assert error.transiciones_permitidas == ["ASIGNADO", "INCIDENCIA"]
