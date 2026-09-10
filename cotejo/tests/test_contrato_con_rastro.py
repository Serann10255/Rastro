"""El contrato entre Cotejo y el servicio de identidad de Rastro.

Estas pruebas existen por un defecto real: al sustituir el emisor de
demostracion por un servicio de identidad, el campo del inicio de sesion paso de
``usuario`` a ``correo`` y ``/auth/yo`` paso a devolver el usuario anidado. Cotejo
siguio compilando y siguio pasando sus 23 pruebas; lo que dejo de funcionar fue
la autenticacion contra el sistema auditado, y eso solo se vio al ejecutarlo
contra la pila levantada.

Un programa de auditoria que no puede autenticarse no reporta un problema del
sistema auditado: reporta controles no ejecutados, que es la peor forma de
fallar, porque se parece a un resultado.

Por eso aqui no se copia la forma esperada del contrato: se levanta el servicio
de identidad real y se le habla con el mismo codigo con el que Cotejo habla al
sistema desplegado.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

RAIZ_COTEJO = Path(__file__).resolve().parents[1]
RAIZ_PROYECTO = RAIZ_COTEJO.parent

os.environ.setdefault("RASTRO_ENTORNO", "memoria")
os.environ.setdefault("RASTRO_JWT_EMISOR", "http://auth.pruebas")
os.environ.setdefault("RASTRO_JWT_AUDIENCIA", "rastro-web")
os.environ.setdefault("RASTRO_JWT_SECRETO", "secreto-de-pruebas-con-longitud-suficiente")
os.environ.setdefault("RASTRO_TABLA_MAESTROS", "rastro-maestros-pruebas")
# Mismo motivo que en las pruebas de Rastro: con el coste de produccion, derivar
# las contrasenas de esta preparacion tarda mas que toda la suite.
os.environ.setdefault("RASTRO_PBKDF2_ITERACIONES", "1000")

from fastapi.testclient import TestClient  # noqa: E402

from cotejo.contexto import Contexto, UsuarioDePrueba  # noqa: E402
from cotejo.pruebas.sustantiva import _sub_de  # noqa: E402
from rastro_core.http import fijar_dependencias  # noqa: E402
from rastro_core.maestros import repositorio_maestros_en_memoria  # noqa: E402
from rastro_core.passwords import derivar  # noqa: E402
from rastro_core.repository import RepositorioMemoria  # noqa: E402

CLAVE = "Contrato.Pruebas.2026"
CORREO = "auditor@andes.test"


def _cargar_auth():
    ruta = RAIZ_PROYECTO / "services" / "auth" / "main.py"
    especificacion = importlib.util.spec_from_file_location("servicio_auth_contrato", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules[especificacion.name] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def identidad():
    """El servicio de identidad real, sobre datos en memoria."""
    fijar_dependencias(repositorio=RepositorioMemoria(), almacen=None)

    maestros = repositorio_maestros_en_memoria()
    maestros.guardar_empresa({"org_id": "org-andes", "nombre": "Mensajeria Andes S.A.S."})
    maestros.guardar_usuario(
        {
            "correo": CORREO,
            "nombre": "Alicia Auditora",
            "org_id": "org-andes",
            "grupos": ["auditor"],
            "hash_clave": derivar(CLAVE),
        }
    )

    modulo = _cargar_auth()
    modulo.fijar_maestros(maestros)
    return modulo


@pytest.fixture
def contexto(identidad) -> Contexto:
    """Un contexto de Cotejo cuyo cliente habla con el servicio real."""
    ctx = Contexto(
        entorno="local",
        url_api="http://identidad.pruebas",
        region="us-east-1",
        bucket_evidencias="rastro-evidencias-local",
        alias_llave="alias/rastro",
        nombre_registro="rastro-actividad",
        tabla_bitacora="rastro-bitacora",
        usuarios=[UsuarioDePrueba("auditor_a", CORREO, CLAVE, "org-andes", "auditor")],
    )
    # ``TestClient`` es un cliente httpx sincrono sobre la aplicacion real, de
    # modo que Cotejo habla con el servicio de identidad por su propio codigo.
    ctx._cliente = TestClient(identidad.app, base_url="http://identidad.pruebas")
    return ctx


def test_cotejo_se_autentica_contra_el_servicio_de_identidad_real(contexto):
    """Es la prueba que faltaba: fija el nombre del campo de credenciales."""
    token = contexto.token("auditor_a")
    assert token


def test_el_sujeto_se_lee_de_la_forma_que_devuelve_la_sesion(contexto):
    """``/auth/yo`` devuelve el usuario anidado; leerlo plano da cadena vacia.

    Y una cadena vacia no falla: hace que la comparacion de C-05 y C-06 no
    encuentre el registro y el control se reporte como no ejecutado.
    """
    sub = _sub_de(contexto, "auditor_a")
    assert sub
    assert sub != ""


def test_una_clave_incorrecta_se_reporta_como_error_de_contexto(contexto):
    """Sin credenciales validas no hay prueba sustantiva que ejecutar, y el
    programa debe decirlo en lugar de continuar con un token vacio."""
    from cotejo.contexto import ErrorContexto

    contexto.usuarios[0] = UsuarioDePrueba(
        "auditor_a", CORREO, "clave que no es la suya", "org-andes", "auditor"
    )
    with pytest.raises(ErrorContexto):
        contexto.token("auditor_a")


def test_las_claves_se_pueden_dar_por_entorno(monkeypatch):
    """En un despliegue con datos reales las claves de la semilla no valen, y el
    programa de auditoria no deberia tener que editarse para poder ejecutarse."""
    from cotejo.contexto import _claves_conocidas

    monkeypatch.setenv("COTEJO_CLAVES", '{"Auditor@Andes.test": "otra clave distinta"}')
    claves = _claves_conocidas("aws")

    # El correo se normaliza igual que en el sistema auditado: si no, la clave
    # estaria y aun asi no se encontraria.
    assert claves == {"auditor@andes.test": "otra clave distinta"}


def test_sin_claves_declaradas_no_se_inventan(monkeypatch):
    """Fuera del entorno local y sin COTEJO_CLAVES no hay credenciales.

    El programa se queda sin usuarios de prueba y las pruebas sustantivas se
    reportan como no ejecutadas. Es la conducta correcta: una prueba que no se
    pudo hacer no es una prueba conforme.
    """
    from cotejo.contexto import _claves_conocidas

    monkeypatch.delenv("COTEJO_CLAVES", raising=False)
    assert _claves_conocidas("aws") == {}


def test_en_local_las_claves_salen_de_la_semilla_del_sistema_auditado(monkeypatch):
    """No se copian en el programa de auditoria: se leen de donde se crearon."""
    from cotejo.contexto import _claves_conocidas

    monkeypatch.delenv("COTEJO_CLAVES", raising=False)
    claves = _claves_conocidas("local")

    assert claves, "la semilla del repositorio debe aportar las claves en local"
    assert all(correo == correo.lower() for correo in claves)
