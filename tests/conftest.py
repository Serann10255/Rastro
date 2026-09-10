"""Configuracion comun de las pruebas.

Las pruebas corren contra el repositorio en memoria y un almacen de evidencias
simulado, de modo que se ejecutan sin infraestructura y sin consumir el
presupuesto del laboratorio. Lo que verifican es la logica de los controles, que
es donde viven los requisitos: aislamiento, autorizacion, maquina de estados y
encadenamiento de la bitacora.

Las pruebas que exigen infraestructura real -cifrado con llave administrada,
registro de actividad, versionado del contenedor- no se simulan aqui: son
pruebas de cumplimiento y las ejecuta Cotejo contra la cuenta desplegada.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

os.environ.setdefault("RASTRO_ENTORNO", "memoria")
os.environ.setdefault("RASTRO_JWT_EMISOR", "http://auth.pruebas")
os.environ.setdefault("RASTRO_JWT_AUDIENCIA", "rastro-web")
os.environ.setdefault("RASTRO_JWT_SECRETO", "secreto-de-pruebas-con-longitud-suficiente")
os.environ.setdefault("RASTRO_SEMILLA_USUARIOS", str(RAIZ / "seed" / "usuarios.json"))

from fastapi.testclient import TestClient  # noqa: E402

from rastro_core.config import cargar_config, reiniciar_config  # noqa: E402
from rastro_core.http import fijar_dependencias  # noqa: E402
from rastro_core.repository import RepositorioMemoria  # noqa: E402
from rastro_core.security import emitir_token_local  # noqa: E402


class AlmacenSimulado:
    """Sustituto del almacenamiento de objetos para las pruebas.

    Reproduce lo unico que el dominio le pide: emitir un enlace acotado al
    prefijo de la organizacion y responder si el objeto existe. No reproduce el
    cifrado, porque simular un control equivale a no verificarlo.
    """

    def __init__(self) -> None:
        self.objetos: dict[str, dict] = {}
        self.config = cargar_config()

    def enlace_de_carga(self, *, org_id, envio_id, tipo_contenido, evidencia_id=None):
        from rastro_core.storage import construir_clave, nuevo_id_evidencia

        evidencia_id = evidencia_id or nuevo_id_evidencia()
        clave = construir_clave(org_id, envio_id, evidencia_id, tipo_contenido)
        return {
            "evidencia_id": evidencia_id,
            "clave": clave,
            "url": f"https://almacen.pruebas/{clave}?firma=simulada",
            "metodo": "PUT",
            "vigencia_segundos": self.config.vigencia_enlace_segundos,
            "encabezados": {"Content-Type": tipo_contenido},
        }

    def cargar(self, clave: str, tamano: int = 1024) -> None:
        """Simula la carga que el dispositivo hace contra el enlace prefirmado."""
        self.objetos[clave] = {
            "clave": clave,
            "tamano": tamano,
            "tipo_contenido": "image/jpeg",
            "cifrado": "aws:kms",
            "llave_kms": "alias/rastro",
            "version_id": "1",
            "modificado_en": "2026-09-10T00:00:00Z",
        }

    def existe(self, *, org_id, clave):
        from rastro_core.storage import prefijo_organizacion

        return clave.startswith(prefijo_organizacion(org_id)) and clave in self.objetos

    def describir_objeto(self, *, org_id, clave):
        from rastro_core.errors import NoEncontradoError
        from rastro_core.storage import prefijo_organizacion

        if not clave.startswith(prefijo_organizacion(org_id)) or clave not in self.objetos:
            raise NoEncontradoError("La evidencia no existe.")
        return dict(self.objetos[clave])

    def enlace_de_descarga(self, *, org_id, clave):
        self.describir_objeto(org_id=org_id, clave=clave)
        return f"https://almacen.pruebas/{clave}?firma=lectura"


def _cargar_servicio(nombre: str):
    """Importa ``services/<nombre>/main.py`` sin que colisionen los modulos."""
    ruta = RAIZ / "services" / nombre / "main.py"
    especificacion = importlib.util.spec_from_file_location(f"servicio_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules[especificacion.name] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def repositorio() -> RepositorioMemoria:
    return RepositorioMemoria()


@pytest.fixture
def almacen() -> AlmacenSimulado:
    return AlmacenSimulado()


@pytest.fixture
def pila(repositorio, almacen):
    """Levanta los seis microservicios sobre el mismo almacen de datos.

    Comparten repositorio porque en el sistema desplegado comparten las tablas:
    lo que se aisla no son los servicios entre si, sino los datos de cada
    organizacion.
    """
    reiniciar_config()
    fijar_dependencias(repositorio=repositorio, almacen=almacen)

    clientes = {
        nombre: TestClient(_cargar_servicio(nombre).app, raise_server_exceptions=False)
        for nombre in ("auth", "shipments", "tracking", "evidence", "public", "audit")
    }
    yield clientes
    for cliente in clientes.values():
        cliente.close()


@pytest.fixture
def token():
    """Emite un token para cualquier combinacion de organizacion y grupos."""

    def _token(sub: str, org_id: str, grupos: list[str], email: str = "") -> str:
        return emitir_token_local(
            sub=sub, email=email or f"{sub}@pruebas.test", org_id=org_id, grupos=grupos
        )

    return _token


@pytest.fixture
def cabeceras(token):
    def _cabeceras(sub: str, org_id: str, grupos: list[str]) -> dict:
        return {"Authorization": f"Bearer {token(sub, org_id, grupos)}"}

    return _cabeceras


@pytest.fixture
def despachador(cabeceras):
    return cabeceras("u-desp-a", "org-andes", ["despachador"])


@pytest.fixture
def conductor(cabeceras):
    return cabeceras("u-cond-a", "org-andes", ["conductor"])


@pytest.fixture
def auditor(cabeceras):
    return cabeceras("u-audit-a", "org-andes", ["auditor"])


@pytest.fixture
def despachador_otra_org(cabeceras):
    return cabeceras("u-desp-b", "org-sabana", ["despachador"])


@pytest.fixture
def envio_creado(pila, despachador) -> dict:
    """Un envio en estado CREADO listo para el resto del ciclo de vida."""
    respuesta = pila["shipments"].post(
        "/envios",
        headers=despachador,
        json={
            "origen": {"linea": "Calle 100 #15-20", "ciudad": "Bogota"},
            "destino": {"linea": "Carrera 7 #32-16", "ciudad": "Bogota"},
            "destinatario": {"nombre": "Laura Mejia Rios", "telefono": "3000000000"},
            "descripcion": "Sobre con documentos",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["envio"]
