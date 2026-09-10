"""Generacion de identificadores y marcas de tiempo.

El identificador de rastreo es un UUID version 4 y no un consecutivo. La razon
es un control de seguridad y no una convencion: con numeracion secuencial
cualquiera podria recorrer identificadores contiguos desde el punto de consulta
publico y obtener los envios de toda la empresa, que es la referencia directa
insegura a objetos incluida en A01:2021 de OWASP.
"""

from __future__ import annotations

import datetime as _dt
import uuid


def nuevo_id_envio() -> str:
    """Identificador de envio no predecible (UUID v4)."""
    return str(uuid.uuid4())


def nuevo_id_evento() -> str:
    """Sufijo corto para desempatar eventos con la misma marca de tiempo."""
    return uuid.uuid4().hex[:8]


def ahora_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def marca_tiempo() -> str:
    """Marca de tiempo del servidor en ISO-8601 UTC, ordenable lexicograficamente.

    Se usa la del servidor y nunca la del cliente: la del dispositivo del
    mensajero es manipulable y no sirve como evidencia (REQ-02).
    """
    return ahora_utc().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
