"""Plomeria HTTP comun a todos los microservicios.

Concentra tres cosas que ningun servicio debe reimplementar: la traduccion de
errores de dominio a codigos HTTP, la obtencion de la identidad desde el token,
y la comprobacion de autorizacion que deja constancia en la bitacora tanto de
las operaciones permitidas como de las rechazadas (REQ-07).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .audit import Resultado
from .authz import DefinicionRol, Operacion, exige_envio_propio, esta_autorizado
from .config import Config, cargar_config
from .errors import NoAutorizadoError, RastroError
from .ids import marca_tiempo
from .models import Identidad
from .repository import Repositorio, construir_repositorio
from .security import extraer_token, identidad_desde_token
from .storage import AlmacenEvidencias

_repositorio: Repositorio | None = None
_almacen: AlmacenEvidencias | None = None
_maestros = None


def obtener_repositorio() -> Repositorio:
    """Instancia unica por proceso; en Lambda sobrevive entre invocaciones."""
    global _repositorio
    if _repositorio is None:
        _repositorio = construir_repositorio()
    return _repositorio


def obtener_almacen() -> AlmacenEvidencias:
    global _almacen
    if _almacen is None:
        _almacen = AlmacenEvidencias()
    return _almacen


def obtener_maestros():
    """Repositorio de datos maestros. Aqui se usa solo para resolver roles.

    Cada servicio necesita saber que concede cada rol de la organizacion, y esa
    definicion vive en la tabla de maestros. Se instancia una vez por proceso.
    """
    global _maestros
    if _maestros is None:
        from .maestros import RepositorioMaestros

        _maestros = RepositorioMaestros()
    return _maestros


def fijar_dependencias(
    repositorio: Repositorio | None = None,
    almacen: AlmacenEvidencias | None = None,
    maestros=None,
) -> None:
    """Sustituye las instancias compartidas. Lo usan las pruebas."""
    global _repositorio, _almacen, _maestros
    if repositorio is not None:
        _repositorio = repositorio
    if almacen is not None:
        _almacen = almacen
    if maestros is not None:
        _maestros = maestros


# --------------------------------------------------------------------------- #
# Identidad y autorizacion
# --------------------------------------------------------------------------- #


async def identidad_actual(authorization: str | None = Header(default=None)) -> Identidad:
    """Valida el token en el propio servicio, no solo en la puerta de enlace."""
    return identidad_desde_token(extraer_token(authorization))


@dataclass
class Contexto:
    """Lo que toda operacion necesita: quien pide, contra que datos y con que reglas."""

    identidad: Identidad
    repositorio: Repositorio
    config: Config
    #: Los roles de la organizacion, resueltos una sola vez por peticion. Se
    #: consultan de forma perezosa: la mayoria de las operaciones comprueban
    #: varios permisos y seria una lectura por comprobacion.
    _roles: dict[str, DefinicionRol] | None = None

    @property
    def org_id(self) -> str:
        return self.identidad.org_id

    @property
    def roles(self) -> dict[str, DefinicionRol] | None:
        """Definiciones de rol de la organizacion, o None si no se alcanzan.

        Si la tabla no responde se devuelve None y la autorizacion cae a los
        roles de fabrica. Es deliberado: un fallo al leer la configuracion no
        puede dejar sin operar a una empresa, y los roles de fabrica son mas
        restrictivos que cualquier personalizacion razonable.
        """
        if self._roles is None:
            try:
                self._roles = obtener_maestros().definiciones_de_rol(self.org_id)
            except Exception:  # noqa: BLE001 - se cae a los roles de fabrica
                self._roles = {}
        return self._roles or None

    def registrar(
        self,
        *,
        accion: Operacion | str,
        recurso: str,
        resultado: Resultado | str,
        detalle: dict[str, Any] | None = None,
    ) -> dict:
        """Escribe un eslabon en la bitacora de la organizacion."""
        return self.repositorio.registrar_bitacora(
            org_id=self.org_id,
            actor_sub=self.identidad.sub,
            actor_email=self.identidad.email,
            actor_grupos=self.identidad.grupos,
            accion=str(accion),
            recurso=recurso,
            resultado=resultado,
            detalle=detalle or {},
        )

    def exigir(
        self,
        operacion: Operacion,
        *,
        recurso: str = "-",
        detalle: dict[str, Any] | None = None,
    ) -> None:
        """Comprueba el grupo y deja constancia del rechazo antes de lanzarlo.

        El orden importa: primero se registra y despues se lanza el error, para
        que un intento no autorizado quede en la bitacora aunque la respuesta
        del servicio se pierda.
        """
        if esta_autorizado(self.identidad.grupos, operacion, self.roles):
            return
        self.registrar(
            accion=operacion,
            recurso=recurso,
            resultado=Resultado.DENY,
            detalle={
                **(detalle or {}),
                "motivo": "grupo_no_autorizado",
                "grupos_presentados": sorted(self.identidad.grupos),
            },
        )
        raise NoAutorizadoError(
            f"El grupo del usuario no puede ejecutar la operacion {operacion}.",
            {"operacion": str(operacion)},
        )

    def exige_envio_propio(self, operacion: Operacion) -> bool:
        return exige_envio_propio(self.identidad.grupos, operacion, self.roles)

    def puede(self, operacion: Operacion) -> bool:
        """Comprueba sin registrar ni lanzar. Para decidir que ofrecer."""
        return esta_autorizado(self.identidad.grupos, operacion, self.roles)


async def contexto_actual(identidad: Identidad = Depends(identidad_actual)) -> Contexto:
    return Contexto(identidad=identidad, repositorio=obtener_repositorio(), config=cargar_config())


# --------------------------------------------------------------------------- #
# Aplicacion
# --------------------------------------------------------------------------- #


def crear_app(titulo: str, descripcion: str, version: str = "0.1.0") -> FastAPI:
    """Construye un microservicio con el manejo de errores ya cableado."""
    app = FastAPI(title=titulo, description=descripcion, version=version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # La interfaz se sirve como sitio estatico aparte.
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RastroError)
    async def _manejar_error_dominio(_request: Request, exc: RastroError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"codigo": exc.codigo, "mensaje": exc.mensaje, "detalle": exc.detalle},
        )

    @app.get("/salud", tags=["operacion"], summary="Estado del servicio")
    async def _salud() -> dict:
        config = cargar_config()
        return {
            "servicio": titulo,
            "version": version,
            "entorno": config.entorno,
            "region": config.region,
            "ts": marca_tiempo(),
        }

    return app


def adaptador_lambda(app: FastAPI) -> Callable:
    """Adapta la aplicacion a un manejador de AWS Lambda.

    El mismo codigo corre como contenedor en local y como funcion en AWS: es lo
    que permite probar la logica sin consumir el presupuesto del laboratorio.
    """
    try:
        from mangum import Mangum
    except ImportError as exc:  # pragma: no cover - solo aplica en el empaquetado
        raise RuntimeError(
            "El despliegue en Lambda requiere el paquete 'mangum' en la capa comun."
        ) from exc
    return Mangum(app, lifespan="off")
