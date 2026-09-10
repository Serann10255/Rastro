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
os.environ.setdefault("RASTRO_TABLA_MAESTROS", "rastro-maestros-pruebas")
# Coste de derivacion reducido: con el valor de produccion, derivar las
# contrasenas de cada prueba lleva la suite de segundos a minutos y nadie la
# ejecuta. Lo que se verifica es el mecanismo, no el coste.
os.environ.setdefault("RASTRO_PBKDF2_ITERACIONES", "1000")

from fastapi.testclient import TestClient  # noqa: E402

from rastro_core.config import cargar_config, reiniciar_config  # noqa: E402
from rastro_core.http import fijar_dependencias  # noqa: E402
from rastro_core.maestros import repositorio_maestros_en_memoria  # noqa: E402
from rastro_core.passwords import derivar  # noqa: E402
from rastro_core.repository import RepositorioMemoria  # noqa: E402
from rastro_core.security import emitir_token_local  # noqa: E402

#: Usuarios reales de las pruebas, con su contrasena. Se derivan al preparar el
#: repositorio: ni siquiera en pruebas se guarda una contrasena en claro.
USUARIOS_DE_PRUEBA = [
    ("admin@andes.test", "Prueba.Admin.2026", "Ana Admin", "org-andes", ["administrador"]),
    ("despacho@andes.test", "Prueba.Despacho.2026", "Diego Despacho", "org-andes", ["despachador"]),
    ("carlos@andes.test", "Prueba.Carlos.2026", "Carlos Conductor", "org-andes", ["conductor"]),
    ("auditor@andes.test", "Prueba.Auditor.2026", "Alicia Auditora", "org-andes", ["auditor"]),
    ("despacho@sabana.test", "Prueba.Sabana.2026", "Sofia Sabana", "org-sabana", ["despachador"]),
]


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
def maestros():
    """Empresas, usuarios, tiendas, clientes y transportistas de las pruebas.

    Los usuarios se crean con su contrasena derivada, de modo que las pruebas
    de inicio de sesion ejercitan el mismo camino que la operacion real.
    """
    repositorio = repositorio_maestros_en_memoria()

    for org_id, nombre in (("org-andes", "Mensajeria Andes S.A.S."), ("org-sabana", "Envios Sabana Ltda.")):
        repositorio.guardar_empresa(
            {"org_id": org_id, "nombre": nombre, "nit": "900.000.000-0", "ciudad": "Bogota"}
        )

    for correo, clave, nombre, org_id, grupos in USUARIOS_DE_PRUEBA:
        repositorio.guardar_usuario(
            {
                "correo": correo,
                "nombre": nombre,
                "org_id": org_id,
                "grupos": grupos,
                # Derivar cuesta cientos de milisegundos por usuario: es el
                # proposito de PBKDF2 y el motivo de que esta preparacion tarde.
                "hash_clave": derivar(clave),
            }
        )

    repositorio.guardar_tienda(
        "org-andes",
        {"tienda_id": "tienda-andes-1", "nombre": "Centro de acopio", "ciudad": "Bogota", "departamento": "Cundinamarca"},
    )
    repositorio.guardar_cliente(
        "org-andes", {"cliente_id": "cliente-andes-1", "nombre": "Distribuidora Kuma"}
    )
    repositorio.guardar_transportista(
        "org-andes", {"transportista_id": "transp-andes-1", "nombre": "Flota propia"}
    )
    return repositorio


@pytest.fixture
def almacen() -> AlmacenSimulado:
    return AlmacenSimulado()


@pytest.fixture
def pila(repositorio, almacen, maestros):
    """Levanta los ocho microservicios sobre el mismo almacen de datos.

    Comparten repositorio porque en el sistema desplegado comparten las tablas:
    lo que se aisla no son los servicios entre si, sino los datos de cada
    organizacion.
    """
    reiniciar_config()
    fijar_dependencias(repositorio=repositorio, almacen=almacen, maestros=maestros)

    modulos = {
        nombre: _cargar_servicio(nombre)
        for nombre in (
            "auth",
            "shipments",
            "tracking",
            "evidence",
            "public",
            "audit",
            "masters",
            "dashboard",
        )
    }
    # Los servicios que consultan datos maestros reciben el mismo repositorio:
    # si cada uno creara el suyo, un usuario creado en uno no existiria en otro.
    for modulo in modulos.values():
        if hasattr(modulo, "fijar_maestros"):
            modulo.fijar_maestros(maestros)

    clientes = {
        nombre: TestClient(modulo.app, raise_server_exceptions=False)
        for nombre, modulo in modulos.items()
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
def coordinador(cabeceras):
    """Mas alcance que un despachador y menos que un administrador."""
    return cabeceras("u-coord-a", "org-andes", ["coordinador"])


@pytest.fixture
def administrador(cabeceras):
    return cabeceras("u-admin-a", "org-andes", ["administrador"])


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
