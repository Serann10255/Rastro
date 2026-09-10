"""Errores de dominio con su traduccion a codigo HTTP."""

from __future__ import annotations


class RastroError(Exception):
    """Base de los errores de dominio."""

    status_code = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje: str, detalle: dict | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle or {}


class ValidacionError(RastroError):
    status_code = 400
    codigo = "SOLICITUD_INVALIDA"


class TransicionInvalidaError(ValidacionError):
    """REQ-03: la transicion solicitada no existe en la maquina de estados."""

    codigo = "TRANSICION_INVALIDA"


class NoAutenticadoError(RastroError):
    status_code = 401
    codigo = "NO_AUTENTICADO"


class NoAutorizadoError(RastroError):
    """REQ-07: el grupo del usuario no puede ejecutar la operacion."""

    status_code = 403
    codigo = "NO_AUTORIZADO"


class NoEncontradoError(RastroError):
    """REQ-06: tambien se usa para responder a un acceso entre organizaciones.

    El acceso a un recurso de otra organizacion no responde 403 sino 404, para
    no confirmar la existencia del recurso al solicitante.
    """

    status_code = 404
    codigo = "NO_ENCONTRADO"


class ConflictoError(RastroError):
    status_code = 409
    codigo = "CONFLICTO"
