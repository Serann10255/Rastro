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
            "ts": self.ts,
            "nota": self.nota,
            "tiene_evidencia": self.evidencia_id is not None,
        }


class Envio(BaseModel):
    envio_id: str
    org_id: str
    estado: Estado
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

    def vista_publica(self) -> dict:
        return {
            "envio_id": self.envio_id,
            "estado": str(self.estado),
            "creado_en": self.creado_en,
            "actualizado_en": self.actualizado_en,
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
