"""Modelos de dominio y contratos de entrada de los microservicios."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authz import Grupo
from .state_machine import Estado

# --------------------------------------------------------------------------- #
# Identidad de la sesion
# --------------------------------------------------------------------------- #


class Identidad(BaseModel):
    """Datos que el token de sesion aporta a cada operacion.

    ``org_id`` viaja en el token y nunca en el cuerpo de la peticion: es el
    filtro obligatorio de toda consulta (riesgo R-05).
    """

    model_config = ConfigDict(frozen=True)

    sub: str
    email: str = ""
    org_id: str
    grupos: tuple[str, ...] = ()
    #: Identificador de la sesion que emitio el token. Permite revocarla y
    #: distinguirla de las demas sesiones abiertas del mismo usuario.
    sid: str = ""

    @property
    def grupos_validos(self) -> frozenset[Grupo]:
        from .authz import normalizar_grupos

        return normalizar_grupos(self.grupos)


# --------------------------------------------------------------------------- #
# Envio y eventos
# --------------------------------------------------------------------------- #


class Direccion(BaseModel):
    linea: str = Field(min_length=3, max_length=200)
    ciudad: str = Field(default="Bogota", max_length=80)
    referencia: str = Field(default="", max_length=200)


class Destinatario(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: str = Field(default="", max_length=40)


class CrearEnvioSolicitud(BaseModel):
    """REQ-01. La organizacion no se recibe aqui: se toma del token."""

    origen: Direccion
    destino: Direccion
    destinatario: Destinatario
    descripcion: str = Field(default="", max_length=300)

    # -- Datos de operacion -------------------------------------------------
    #: Referencia del cliente. No la genera el sistema y puede repetirse entre
    #: clientes distintos, de modo que no sirve como identificador: sirve para
    #: que el cliente encuentre su envio con el numero que el maneja.
    orden_compra: str = Field(default="", max_length=80)
    tienda_id: str = Field(default="", max_length=40)
    cliente_id: str = Field(default="", max_length=40)
    transportista_id: str = Field(default="", max_length=40)
    peso_kg: float = Field(default=0, ge=0, le=5000)
    valor_declarado: float = Field(default=0, ge=0)
    bultos: int = Field(default=1, ge=1, le=500)
    #: Fecha comprometida con el cliente. El sistema no la calcula: la fija
    #: quien vende el servicio, y sirve para saber que envios van tarde.
    fecha_estimada: str = Field(default="", max_length=32)
    observaciones: str = Field(default="", max_length=500)


class CrearLoteSolicitud(BaseModel):
    """Registro masivo. Es la operacion habitual de un cliente corporativo,
    que despacha decenas de envios de una vez y no uno a uno."""

    envios: list[CrearEnvioSolicitud] = Field(min_length=1, max_length=500)


class AsignarConductorSolicitud(BaseModel):
    conductor_sub: str = Field(min_length=1, max_length=120)
    conductor_nombre: str = Field(default="", max_length=120)


class Ubicacion(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    def as_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon}


class RegistrarEventoSolicitud(BaseModel):
    """REQ-02. La marca de tiempo la pone el servidor, no el cliente."""

    estado: Estado
    ubicacion: Ubicacion | None = None
    nota: str = Field(default="", max_length=300)
    evidencia_id: str | None = None


class SolicitarEvidenciaSolicitud(BaseModel):
    """REQ-05. Solicitud del enlace prefirmado de carga."""

    nombre_archivo: str = Field(min_length=1, max_length=160)
    tipo_contenido: Literal[
        "image/jpeg", "image/png", "image/webp", "application/pdf"
    ] = "image/jpeg"


class Evento(BaseModel):
    evento_id: str
    envio_id: str
    org_id: str
    estado: Estado
    codigo_estado: int = 10
    estado_anterior: Estado | None = None
    ts: str
    actor_sub: str
    actor_email: str = ""
    actor_grupos: tuple[str, ...] = ()
    ubicacion: dict | None = None
    nota: str = ""
    evidencia_id: str | None = None

    def vista_publica(self) -> dict:
        """REQ-04: el destinatario ve el avance, no la identidad del operario."""
        return {
            "estado": str(self.estado),
            "codigo_estado": self.codigo_estado,
            "ts": self.ts,
            "nota": self.nota,
            "tiene_evidencia": self.evidencia_id is not None,
        }


class Envio(BaseModel):
    envio_id: str
    org_id: str
    estado: Estado
    #: Codigo numerico del estado. Se guarda ademas del nombre porque es lo que
    #: viaja en los archivos de intercambio, donde un nombre en texto es fragil.
    codigo_estado: int = 10
    estado_previo_incidencia: Estado | None = None
    creado_en: str
    actualizado_en: str
    creado_por: str
    conductor_sub: str | None = None
    conductor_nombre: str = ""
    origen: Direccion
    destino: Direccion
    destinatario: Destinatario
    descripcion: str = ""
    evidencias: tuple[str, ...] = ()

    # -- Datos de operacion -------------------------------------------------
    orden_compra: str = ""
    tienda_id: str = ""
    tienda_nombre: str = ""
    cliente_id: str = ""
    cliente_nombre: str = ""
    transportista_id: str = ""
    transportista_nombre: str = ""
    estacion_actual: str = ""
    peso_kg: float = 0
    valor_declarado: float = 0
    bultos: int = 1
    fecha_estimada: str = ""
    observaciones: str = ""

    def vista_publica(self) -> dict:
        return {
            "envio_id": self.envio_id,
            "estado": str(self.estado),
            "codigo_estado": self.codigo_estado,
            "creado_en": self.creado_en,
            "actualizado_en": self.actualizado_en,
            "fecha_estimada": self.fecha_estimada,
            "destino_ciudad": self.destino.ciudad,
            "destinatario_nombre": _enmascarar_nombre(self.destinatario.nombre),
        }


def _enmascarar_nombre(nombre: str) -> str:
    """Minimizacion de datos en el punto de consulta publico (Ley 1581).

    Se conserva lo suficiente para que el destinatario se reconozca y no lo
    suficiente para construir un directorio de clientes de la empresa.
    """
    partes = [p for p in nombre.strip().split() if p]
    if not partes:
        return ""
    return " ".join([partes[0]] + [f"{p[0]}." for p in partes[1:]])
