"""Cliente de Cotejo: la revisión encargada en AWS y la sesión del auditor."""

import asyncio

import httpx
import pytest

from comun import http
from comun.http import ErrorApi
from cotejo_app import api as modulo_api
from cotejo_app.api import ClienteCotejo


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    # La espera real es de tres segundos entre consultas; aquí no hace falta.
    original = asyncio.sleep
    monkeypatch.setattr(modulo_api.asyncio, "sleep", lambda _s: original(0))
    yield
    http._cliente = None


def cliente(manejador) -> ClienteCotejo:
    http._cliente = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    c = ClienteCotejo({"url_cotejo": "http://cotejo", "url_rastro": "http://rastro"})
    c.sesion = {"token": "t", "usuario": {"grupos": ["auditor"]}}
    return c


def test_la_revision_encargada_se_espera_hasta_que_esta_lista():
    estados = iter(["en_curso", "en_curso", "lista"])
    consultas = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        consultas.append(peticion.url.path)
        return httpx.Response(200, json={"ejecucion_id": "e1", "estado": next(estados)})

    asyncio.run(cliente(manejador).esperar_ejecucion("e1"))
    assert consultas == ["/ejecuciones/e1/estado"] * 3


def test_una_revision_fallida_dice_por_que():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ejecucion_id": "e1", "estado": "fallida", "motivo": "Sin acceso a Rastro."})

    with pytest.raises(ErrorApi) as error:
        asyncio.run(cliente(manejador).esperar_ejecucion("e1"))
    assert error.value.codigo == "EJECUCION_FALLIDA" and error.value.mensaje == "Sin acceso a Rastro."


def test_un_401_cierra_la_sesion_del_auditor():
    def manejador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"codigo": "NO_AUTENTICADO", "mensaje": "Token caducado."})

    c = cliente(manejador)
    cambios = []
    c.al_cambiar_sesion = cambios.append
    with pytest.raises(ErrorApi):
        asyncio.run(c.catalogo())
    assert c.sesion is None and cambios == [None]
